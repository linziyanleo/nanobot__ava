#!/usr/bin/env node
/**
 * page-agent-runner.mjs
 *
 * 常驻 Node 进程，通过 stdin/stdout JSON-RPC 与 Python PageAgentTool 通信。
 * 负责：Playwright 浏览器管理、page-agent 注入与执行、CDP screencast、activity 事件转发。
 *
 * 通信协议：
 *   stdin  → 每行一个 JSON（RPC 请求，带 id + method + params）
 *   stdout → 每行一个 JSON
 *            - RPC 响应：{ id, success, result/error }
 *            - 推送事件：{ type: "frame"/"activity"/"status", session_id, ... }（无 id）
 *   stderr → 心跳和日志（不影响 RPC）
 */

import { createInterface } from "node:readline";
import { chromium, firefox, webkit } from "playwright";

// ---------------------------------------------------------------------------
// 全局状态
// ---------------------------------------------------------------------------

/** @type {import('playwright').Browser | null} */
let browser = null;

/** @type {Map<string, { page: import('playwright').Page, cdp: any | null, screencastActive: boolean }>} */
const sessions = new Map();

/** 启动时从 init 命令接收的配置 */
let config = {
  headless: true,
  browserType: "chromium",
  viewportWidth: 1280,
  viewportHeight: 720,
  // page-agent LLM 配置
  apiBase: "",
  apiKey: "",
  model: "",
  maxSteps: 40,
  stepDelay: 0.4,
  language: "zh-CN",
};

const MAX_SESSIONS = 5;

// ---------------------------------------------------------------------------
// 工具函数
// ---------------------------------------------------------------------------

function send(obj) {
  process.stdout.write(JSON.stringify(obj) + "\n");
}

function log(msg) {
  process.stderr.write(`[runner] ${new Date().toISOString()} ${msg}\n`);
}

function reply(id, success, data) {
  if (success) {
    send({ id, success: true, result: data });
  } else {
    send({ id, success: false, error: data });
  }
}

function pushEvent(type, sessionId, payload) {
  send({ type, session_id: sessionId, ...payload });
}

// ---------------------------------------------------------------------------
// 浏览器管理
// ---------------------------------------------------------------------------

async function ensureBrowser() {
  if (browser && browser.isConnected()) return browser;

  const launchers = { chromium, firefox, webkit };
  const launcher = launchers[config.browserType] || chromium;

  browser = await launcher.launch({ headless: config.headless });
  log(`browser launched (${config.browserType}, headless=${config.headless})`);
  return browser;
}

async function getOrCreateSession(sessionId) {
  if (sessions.has(sessionId)) return sessions.get(sessionId);

  if (sessions.size >= MAX_SESSIONS) {
    throw new Error(`session limit reached (max ${MAX_SESSIONS})`);
  }

  const b = await ensureBrowser();
  const context = await b.newContext({
    viewport: { width: config.viewportWidth, height: config.viewportHeight },
  });
  const page = await context.newPage();
  const session = { page, cdp: null, screencastActive: false };
  sessions.set(sessionId, session);
  log(`session created: ${sessionId}`);
  return session;
}

// ---------------------------------------------------------------------------
// page-agent 注入与执行
// ---------------------------------------------------------------------------

/**
 * 在页面中注入 page-agent 并执行指令。
 * page-agent 是纯前端库，必须在浏览器页面上下文中运行。
 */
async function executePageAgent(page, instruction) {
  // 注入 page-agent（如果尚未注入）
  const alreadyInjected = await page.evaluate(() => !!window.__pageAgentInjected);

  if (!alreadyInjected) {
    // 通过 CDN 注入 page-agent IIFE bundle
    await page.addScriptTag({
      url: "https://cdn.jsdelivr.net/npm/page-agent@1.7.0/dist/iife/page-agent.js",
    });
    await page.evaluate(() => {
      window.__pageAgentInjected = true;
    });
    log("page-agent injected via CDN");
  }

  // 在页面上下文中创建 PageAgentCore 并执行
  const result = await page.evaluate(
    async ({ instruction, cfg }) => {
      // page-agent IIFE 挂载到 window.PageAgent
      const { PageAgentCore } = window.PageAgent || {};
      if (!PageAgentCore) {
        // 降级尝试：可能挂载路径不同
        throw new Error("PageAgent not found on window after injection");
      }

      const { PageController } = window.PageAgent;

      // 每次执行复用或新建 agent
      if (!window.__paAgent) {
        const pageController = new PageController({
          enableMask: true,
          viewportExpansion: 0,
        });
        window.__paAgent = new PageAgentCore({
          pageController,
          baseURL: cfg.apiBase || undefined,
          apiKey: cfg.apiKey || undefined,
          model: cfg.model || undefined,
          maxSteps: cfg.maxSteps || 40,
          stepDelay: cfg.stepDelay || 0.4,
          language: cfg.language || "zh-CN",
        });
      }

      const agent = window.__paAgent;
      const executionResult = await agent.execute(instruction);
      return {
        success: executionResult.success,
        data: executionResult.data || "",
        steps: executionResult.history
          ? executionResult.history.filter((e) => e.type === "step").length
          : 0,
      };
    },
    {
      instruction,
      cfg: {
        apiBase: config.apiBase,
        apiKey: config.apiKey,
        model: config.model,
        maxSteps: config.maxSteps,
        stepDelay: config.stepDelay,
        language: config.language,
      },
    }
  );

  return result;
}

// ---------------------------------------------------------------------------
// Activity 事件监听（通过 page.exposeFunction 桥接）
// ---------------------------------------------------------------------------

async function setupActivityBridge(sessionId, page) {
  // 检查是否已设置
  const bridged = await page.evaluate(() => !!window.__paActivityBridged);
  if (bridged) return;

  // 暴露回调到页面上下文
  await page.exposeFunction("__paOnActivity", (activityJson) => {
    try {
      const activity = JSON.parse(activityJson);
      pushEvent("activity", sessionId, { activity });
    } catch { /* ignore parse errors */ }
  });

  await page.exposeFunction("__paOnStatus", (status) => {
    pushEvent("status", sessionId, { status });
  });

  // 在页面中挂载监听器
  await page.evaluate(() => {
    window.__paActivityBridged = true;

    // 轮询等待 agent 实例化后挂载监听
    const poll = setInterval(() => {
      const agent = window.__paAgent;
      if (!agent) return;
      clearInterval(poll);

      agent.addEventListener("activity", (e) => {
        window.__paOnActivity(JSON.stringify(e.detail || e.data || {}));
      });
      agent.addEventListener("statuschange", (e) => {
        window.__paOnStatus(e.detail || e.data || "unknown");
      });
    }, 200);

    // 30 秒后停止轮询
    setTimeout(() => clearInterval(poll), 30000);
  });
}

// ---------------------------------------------------------------------------
// CDP Screencast
// ---------------------------------------------------------------------------

async function startScreencast(session, sessionId, params) {
  if (session.screencastActive) return;

  // CDP 只在 Chromium 上可用
  if (config.browserType !== "chromium") {
    throw new Error("screencast requires chromium browser");
  }

  const context = session.page.context();
  session.cdp = await context.newCDPSession(session.page);

  session.cdp.on("Page.screencastFrame", async (frame) => {
    pushEvent("frame", sessionId, {
      data: frame.data,
      metadata: { timestamp: frame.metadata?.timestamp },
    });
    // ack 以触发下一帧
    try {
      await session.cdp.send("Page.screencastFrameAck", {
        sessionId: frame.sessionId,
      });
    } catch { /* session 可能已关闭 */ }
  });

  await session.cdp.send("Page.startScreencast", {
    format: "jpeg",
    quality: params?.quality || 60,
    maxWidth: params?.maxWidth || config.viewportWidth,
    maxHeight: params?.maxHeight || config.viewportHeight,
    everyNthFrame: params?.everyNthFrame || 2,
  });

  session.screencastActive = true;
  log(`screencast started for ${sessionId}`);
}

async function stopScreencast(session, sessionId) {
  if (!session.screencastActive || !session.cdp) return;

  try {
    await session.cdp.send("Page.stopScreencast");
    await session.cdp.detach();
  } catch { /* ignore */ }

  session.cdp = null;
  session.screencastActive = false;
  log(`screencast stopped for ${sessionId}`);
}

// ---------------------------------------------------------------------------
// RPC Method Handlers
// ---------------------------------------------------------------------------

const handlers = {
  async init(id, params) {
    Object.assign(config, params);
    reply(id, true, { message: "config updated" });
    log(`config updated: browserType=${config.browserType}, headless=${config.headless}, model=${config.model}`);
  },

  async execute(id, params) {
    const { url, instruction, session_id: sid } = params;
    if (!instruction) {
      return reply(id, false, { code: "MISSING_PARAM", message: "instruction is required" });
    }

    const sessionId = sid || `s_${Date.now().toString(36)}`;

    try {
      const session = await getOrCreateSession(sessionId);

      // 如果提供了 URL，先导航
      if (url) {
        await session.page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
      }

      // 设置 activity 桥接
      await setupActivityBridge(sessionId, session.page);

      // 执行 page-agent 指令
      const result = await executePageAgent(session.page, instruction);

      // 获取当前页面信息
      const pageUrl = session.page.url();
      const pageTitle = await session.page.title();

      reply(id, true, {
        session_id: sessionId,
        data: result.data,
        success: result.success,
        steps: result.steps,
        page_url: pageUrl,
        page_title: pageTitle,
      });
    } catch (err) {
      reply(id, false, { code: "EXECUTION_FAILED", message: err.message });
    }
  },

  async screenshot(id, params) {
    const { session_id: sid, path: savePath } = params;
    if (!sid || !sessions.has(sid)) {
      return reply(id, false, { code: "NO_SESSION", message: `session ${sid} not found` });
    }

    try {
      const session = sessions.get(sid);
      const buffer = await session.page.screenshot({
        type: "png",
        fullPage: false,
      });

      if (savePath) {
        const { writeFileSync } = await import("node:fs");
        writeFileSync(savePath, buffer);
        reply(id, true, { path: savePath, size: buffer.length });
      } else {
        // 返回 base64
        reply(id, true, { data: buffer.toString("base64"), size: buffer.length });
      }
    } catch (err) {
      reply(id, false, { code: "SCREENSHOT_FAILED", message: err.message });
    }
  },

  async get_page_info(id, params) {
    const { session_id: sid } = params;
    if (!sid || !sessions.has(sid)) {
      return reply(id, false, { code: "NO_SESSION", message: `session ${sid} not found` });
    }

    const session = sessions.get(sid);
    const pageUrl = session.page.url();
    const pageTitle = await session.page.title();
    const viewport = session.page.viewportSize();

    reply(id, true, {
      page_url: pageUrl,
      page_title: pageTitle,
      viewport: viewport ? `${viewport.width}x${viewport.height}` : "unknown",
    });
  },

  async list_sessions(id) {
    reply(id, true, {
      sessions: Array.from(sessions.keys()),
    });
  },

  async close_session(id, params) {
    const { session_id: sid } = params;
    if (!sid || !sessions.has(sid)) {
      return reply(id, true, { message: `session ${sid} already closed` });
    }

    const session = sessions.get(sid);
    await stopScreencast(session, sid);

    try {
      await session.page.context().close();
    } catch { /* ignore */ }

    sessions.delete(sid);
    log(`session closed: ${sid}`);
    reply(id, true, { message: `session ${sid} closed` });
  },

  async start_screencast(id, params) {
    const { session_id: sid } = params;
    if (!sid || !sessions.has(sid)) {
      return reply(id, false, { code: "NO_SESSION", message: `session ${sid} not found` });
    }

    try {
      await startScreencast(sessions.get(sid), sid, params);
      reply(id, true, { message: "screencast started" });
    } catch (err) {
      reply(id, false, { code: "SCREENCAST_FAILED", message: err.message });
    }
  },

  async stop_screencast(id, params) {
    const { session_id: sid } = params;
    if (!sid || !sessions.has(sid)) {
      return reply(id, true, { message: "no active screencast" });
    }

    await stopScreencast(sessions.get(sid), sid);
    reply(id, true, { message: "screencast stopped" });
  },

  async shutdown(id) {
    log("shutdown requested");

    // 关闭所有会话
    for (const [sid, session] of sessions) {
      await stopScreencast(session, sid);
      try { await session.page.context().close(); } catch { /* ignore */ }
    }
    sessions.clear();

    // 关闭浏览器
    if (browser) {
      try { await browser.close(); } catch { /* ignore */ }
      browser = null;
    }

    reply(id, true, { message: "shutdown complete" });

    // 延迟退出，确保响应已写入 stdout
    setTimeout(() => process.exit(0), 100);
  },
};

// ---------------------------------------------------------------------------
// stdin RPC 循环
// ---------------------------------------------------------------------------

const rl = createInterface({ input: process.stdin, terminal: false });

rl.on("line", async (line) => {
  let msg;
  try {
    msg = JSON.parse(line.trim());
  } catch {
    log(`invalid JSON: ${line}`);
    return;
  }

  const { id, method, params } = msg;
  if (!id || !method) {
    log(`malformed RPC: missing id or method`);
    return;
  }

  const handler = handlers[method];
  if (!handler) {
    reply(id, false, { code: "UNKNOWN_METHOD", message: `unknown method: ${method}` });
    return;
  }

  try {
    await handler(id, params || {});
  } catch (err) {
    reply(id, false, { code: "INTERNAL_ERROR", message: err.message });
  }
});

rl.on("close", () => {
  log("stdin closed, shutting down");
  process.exit(0);
});

// ---------------------------------------------------------------------------
// 心跳
// ---------------------------------------------------------------------------

setInterval(() => {
  log(`heartbeat sessions=${sessions.size} browser=${browser?.isConnected() ?? false}`);
}, 30000);

log("runner started, waiting for commands...");
