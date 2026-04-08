const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

// ── Color Palette ──
const C = {
  teal:       "0D9488",
  tealDark:   "0F766E",
  tealDeep:   "134E4A",
  mint:       "5EEAD4",
  mintLight:  "CCFBF1",
  seafoam:    "99F6E4",
  white:      "FFFFFF",
  offWhite:   "F0FDFA",
  warmGray:   "57534E",
  coolGray:   "6B7280",
  slate:      "334155",
  lightGray:  "F1F5F9",
  borderGray: "E2E8F0",
  red:        "EF4444",
  green:      "10B981",
  amber:      "F59E0B",
  orange:     "F97316",
};

const F = {
  head: "Trebuchet MS",
  body: "Calibri",
  mono: "Consolas",
};

// ── Image paths ──
const IMG = {
  threeCol:       "/Users/fanghu/.nanobot/media/generated/154e944e940b_7.png",  // 三栏对比
  fiveSub:        "/Users/fanghu/.nanobot/media/generated/cf5c1765b0b4_4.png",  // 五子系统映射表
  codeLines:      "/Users/fanghu/.nanobot/media/generated/d01a0cef237a_6.png",  // 代码行数统计
  archOverview:   "/Users/fanghu/.nanobot/media/generated/049b8ad8702f_0.png",  // 架构全景图
  semiLoop:       "/Users/fanghu/.nanobot/media/generated/1af453364115_4.png",  // 半闭环示意图
  constraintLayer:"/Users/fanghu/.nanobot/media/generated/192bd644c88b_5.png",  // 约束分层图 (竖版)
  contBudget:     "/Users/fanghu/.nanobot/media/generated/3397269641fa_5.png",  // Continuation Budget
  autoRebuild:    "/Users/fanghu/.nanobot/media/generated/9674503c138d_6.png",  // 前端 auto-rebuild
};

const mkShadow = () => ({
  type: "outer", color: "000000", blur: 4, offset: 1, angle: 135, opacity: 0.08,
});

// ── Slide helpers ──
function addBg(s, color) { s.background = { color }; }
function freshSlide(pres) { const s = pres.addSlide(); addBg(s, C.offWhite); return s; }
function whiteSlide(pres) { const s = pres.addSlide(); addBg(s, C.white); return s; }
function tealSlide(pres) { const s = pres.addSlide(); addBg(s, C.tealDeep); return s; }

const TOTAL = 23;

function pageNum(s, n) {
  s.addText(`${n} / ${TOTAL}`, {
    x: 8.5, y: 5.15, w: 1.2, h: 0.3,
    fontSize: 8, fontFace: F.body, color: C.coolGray, align: "right", margin: 0,
  });
}

// Section header
function sectionNum(s, num) {
  s.addText(num, {
    x: 0.6, y: 0.35, w: 1, h: 0.35,
    fontSize: 12, fontFace: F.head, color: C.teal, bold: true, margin: 0,
  });
}

function slideTitle(s, text, y = 0.65) {
  s.addText(text, {
    x: 0.6, y, w: 8.5, h: 0.6,
    fontSize: 24, fontFace: F.head, color: C.slate, bold: true, margin: 0,
  });
}

function slideSubtitle(s, text, y = 1.2) {
  s.addText(text, {
    x: 0.6, y, w: 8.5, h: 0.3,
    fontSize: 12, fontFace: F.body, color: C.coolGray, margin: 0,
  });
}

// Full-width horizontal image (1376x768)
function addHImage(s, imgPath, y = 1.5, h = 3.5) {
  const maxW = 8.8;
  const imgRatio = 1376 / 768;
  let w = maxW;
  let ih = w / imgRatio;
  if (ih > h) { ih = h; w = ih * imgRatio; }
  const x = 0.6 + (maxW - w) / 2;
  s.addImage({ path: imgPath, x, y, w, h: ih });
}

// Vertical image (768x1376) - special layout
function addVImage(s, imgPath, x = 3.2, y = 0.5, maxH = 4.8) {
  const imgRatio = 768 / 1376;
  let h = maxH;
  let w = h * imgRatio;
  s.addImage({ path: imgPath, x, y, w, h });
}

function topStripe(s, color = C.teal) {
  s.addShape(pres.shapes ? "rect" : "rect", {
    x: 0, y: 0, w: 10, h: 0.04, fill: { color },
  });
}

// ── Build ──
async function build() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";  // 13.33in x 7.5in = ~33.867cm x 19.05cm
  pres.author = "Fanghu";
  pres.title = "怎么让 AI 帮你改代码，但不把项目改坏";
  let pn = 0;

  // ═══════════════════════════════════════════
  // Slide 1 — 封面
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = tealSlide(pres);
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.33, h: 0.06, fill: { color: C.mint } });

    s.addText("怎么让 AI 帮你改代码\n但不把项目改坏", {
      x: 0.8, y: 1.5, w: 7, h: 2.0,
      fontSize: 40, fontFace: F.head, color: C.white, bold: true, lineSpacingMultiple: 1.3, margin: 0,
    });
    s.addText("从 OpenClaw 的困境到 Nanobot/Ava 的 Harness 实践", {
      x: 0.8, y: 3.6, w: 7, h: 0.5,
      fontSize: 16, fontFace: F.body, color: C.seafoam, margin: 0,
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.8, y: 4.3, w: 2.0, h: 0.03, fill: { color: C.mint } });
    s.addText("方壶  |  预计时长 60 分钟  |  2026.04", {
      x: 0.8, y: 4.55, w: 6, h: 0.4,
      fontSize: 14, fontFace: F.body, color: C.seafoam, margin: 0,
    });
    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 2 — 龙虾悖论
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = freshSlide(pres);
    sectionNum(s, "01");
    slideTitle(s, "龙虾悖论");

    // Quote card
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.5, w: 7.5, h: 1.5, fill: { color: C.white }, shadow: mkShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.5, w: 0.08, h: 1.5, fill: { color: C.teal } });
    s.addText([
      { text: "你想让 AI 做的事情越多，给它的权限就必须越大；\n", options: { fontSize: 16, bold: true, color: C.slate } },
      { text: "权限越大，安全风险就越高。", options: { fontSize: 16, bold: true, color: C.teal } },
    ], { x: 1.0, y: 1.6, w: 6.8, h: 1.2, fontFace: F.body, margin: 0, lineSpacingMultiple: 1.5 });

    s.addText("OpenClaw 3000+ 插件中约 10.8% 包含恶意代码\n用户账户被盗刷、文件被一键清空真实发生过", {
      x: 0.6, y: 3.3, w: 7.5, h: 0.6, fontSize: 12, fontFace: F.body, color: C.warmGray, margin: 0, lineSpacingMultiple: 1.4,
    });

    // Right: key takeaway
    s.addShape(pres.shapes.RECTANGLE, { x: 8.8, y: 1.5, w: 4.0, h: 2.4, fill: { color: C.tealDeep } });
    s.addText("能力越大\n↓\n权限越大\n↓\n风险越大", {
      x: 8.8, y: 1.5, w: 4.0, h: 2.4,
      fontSize: 20, fontFace: F.head, color: C.white, bold: true, align: "center", valign: "middle", margin: 0, lineSpacingMultiple: 1.2,
    });

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 3 — AI 像没边界感的实习生
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = freshSlide(pres);
    slideTitle(s, "AI = 能力极强但没有边界感的实习生", 0.4);

    const cards = [
      { title: "让它修 bug", desc: "可能直接改上游源码", color: C.red },
      { title: "让它改按钮颜色", desc: "可能顺手重构组件库", color: C.amber },
      { title: "让它加个功能", desc: "可能改了数据库 schema", color: C.orange },
    ];
    cards.forEach((c, i) => {
      const cx = 0.6 + i * 4.1;
      s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 1.3, w: 3.8, h: 1.8, fill: { color: C.white }, shadow: mkShadow() });
      s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 1.3, w: 3.8, h: 0.06, fill: { color: c.color } });
      s.addText(c.title, { x: cx + 0.2, y: 1.55, w: 3.4, h: 0.4, fontSize: 16, fontFace: F.body, color: C.slate, bold: true, margin: 0 });
      s.addText(c.desc, { x: cx + 0.2, y: 2.05, w: 3.4, h: 0.8, fontSize: 14, fontFace: F.body, color: C.warmGray, margin: 0 });
    });

    // Takeaway bar
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 3.5, w: 12.0, h: 0.7, fill: { color: C.teal, transparency: 10 } });
    s.addText("核心问题：怎么给 AI 设计边界？", {
      x: 0.6, y: 3.5, w: 12.0, h: 0.7,
      fontSize: 20, fontFace: F.head, color: C.tealDeep, bold: true, align: "center", valign: "middle", margin: 0,
    });

    s.addText('AI 足够聪明，但\u201C聪明\u201D恰恰是问题的一部分\n\u2014\u2014它会自己决定改哪里、怎么改、什么时候算\u201C完成了\u201D', {
      x: 0.6, y: 4.5, w: 12.0, h: 0.6, fontSize: 12, fontFace: F.body, color: C.coolGray, align: "center", margin: 0, lineSpacingMultiple: 1.4,
    });

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 4 — Harness Engineering 概念
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = freshSlide(pres);
    sectionNum(s, "02");
    slideTitle(s, "Harness Engineering");
    slideSubtitle(s, "三个来源，一个共识");

    // 嵌入三栏对比信息图
    addHImage(s, IMG.threeCol, 1.7, 3.8);

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 5 — Harness 是什么（类比）
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = freshSlide(pres);
    slideTitle(s, "Harness 是什么？", 0.4);

    // CI/CD analogy
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.2, w: 5.8, h: 1.6, fill: { color: C.white }, shadow: mkShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.2, w: 0.08, h: 1.6, fill: { color: C.teal } });
    s.addText("CI/CD 类比", { x: 1.0, y: 1.3, w: 5.2, h: 0.35, fontSize: 14, fontFace: F.body, color: C.teal, bold: true, margin: 0 });
    s.addText("CI/CD 不让你代码写得更好，但确保提交的代码\n必须通过 lint、测试、review 才能上线\n\nHarness 做的是同样的事，对象从人变成 AI", {
      x: 1.0, y: 1.7, w: 5.2, h: 1.0, fontSize: 12, fontFace: F.body, color: C.warmGray, margin: 0, lineSpacingMultiple: 1.4,
    });

    // Playground analogy
    s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 1.2, w: 5.8, h: 1.6, fill: { color: C.white }, shadow: mkShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 1.2, w: 0.08, h: 1.6, fill: { color: C.mint } });
    s.addText("游乐场类比", { x: 7.2, y: 1.3, w: 5.2, h: 0.35, fontSize: 14, fontFace: F.body, color: C.tealDark, bold: true, margin: 0 });
    s.addText(`给 AI 这个新生宝宝准备的铺满软垫的游乐场\n\n不管 AI 在里面怎么玩，但确保 AI 不会玩出圈\n游乐场不让你玩得更好，但让你的\u201C好\u201D更可靠`, {
      x: 7.2, y: 1.7, w: 5.2, h: 1.0, fontSize: 12, fontFace: F.body, color: C.warmGray, margin: 0, lineSpacingMultiple: 1.4,
    });

    // Core formula
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 3.2, w: 12.0, h: 0.6, fill: { color: C.tealDeep } });
    s.addText("模型决定写什么代码。Harness 治理何时、何地、怎么写。", {
      x: 0.6, y: 3.2, w: 12.0, h: 0.6,
      fontSize: 18, fontFace: F.head, color: C.white, bold: true, align: "center", valign: "middle", margin: 0,
    });

    // Five subsystems brief
    const subs = ["Instructions\n做什么", "State\n做到哪了", "Verification\n做对了吗", "Scope\n只做一件事", "Lifecycle\n开始 & 结束"];
    subs.forEach((sub, i) => {
      const cx = 0.6 + i * 2.45;
      s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 4.1, w: 2.2, h: 1.1, fill: { color: C.white }, shadow: mkShadow() });
      s.addText(sub, { x: cx, y: 4.1, w: 2.2, h: 1.1, fontSize: 12, fontFace: F.body, color: C.slate, bold: true, align: "center", valign: "middle", margin: 0, lineSpacingMultiple: 1.3 });
    });

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 6 — Ava Harness 五子系统映射表 (KEY SLIDE)
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = whiteSlide(pres);
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.33, h: 0.06, fill: { color: C.teal } });
    s.addText("Ava Harness 五子系统映射", {
      x: 0.6, y: 0.2, w: 12, h: 0.5, fontSize: 22, fontFace: F.head, color: C.slate, bold: true, margin: 0,
    });
    s.addText("⭐ 全场最重要的一页", {
      x: 0.6, y: 0.7, w: 12, h: 0.3, fontSize: 12, fontFace: F.body, color: C.teal, bold: true, margin: 0,
    });

    // 嵌入五子系统映射表信息图
    addHImage(s, IMG.fiveSub, 1.2, 4.2);

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 7 — 为什么选 Nanobot
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = freshSlide(pres);
    sectionNum(s, "03");
    slideTitle(s, "为什么选择 Nanobot");

    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.4, w: 5.8, h: 2.0, fill: { color: C.white }, shadow: mkShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.4, w: 0.08, h: 2.0, fill: { color: C.teal } });
    s.addText('"Inspired by OpenClaw, 99% fewer lines"', {
      x: 1.0, y: 1.5, w: 5.2, h: 0.4, fontSize: 14, fontFace: F.body, color: C.teal, bold: true, italic: true, margin: 0,
    });
    s.addText("核心能力一个不少：工具调用、记忆、多轮对话、多通道接入\n但规模让个人开发者能真正理解和掌控", {
      x: 1.0, y: 2.0, w: 5.2, h: 0.6, fontSize: 12, fontFace: F.body, color: C.warmGray, margin: 0, lineSpacingMultiple: 1.4,
    });
    s.addText("台式电脑类比", { x: 1.0, y: 2.8, w: 5.2, h: 0.3, fontSize: 12, fontFace: F.body, color: C.slate, bold: true, margin: 0 });
    s.addText(`Mac Studio 是通用工业流水线作品\n自己组装一台台式电脑让你拧到每一颗螺丝\n如果目标是"理解电脑的构成"，台式电脑是更好的选择`, {
      x: 1.0, y: 3.1, w: 5.2, h: 0.8, fontSize: 11, fontFace: F.body, color: C.warmGray, margin: 0, lineSpacingMultiple: 1.4,
    });

    // Sidecar concept
    s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 1.4, w: 5.8, h: 2.0, fill: { color: C.white }, shadow: mkShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 1.4, w: 0.08, h: 2.0, fill: { color: C.mint } });
    s.addText("Ava 不是 Fork，是 Sidecar", {
      x: 7.2, y: 1.5, w: 5.2, h: 0.4, fontSize: 14, fontFace: F.body, color: C.tealDark, bold: true, margin: 0,
    });
    s.addText("Fork = 把别人的房子图纸抄过来拆了重建\nSidecar = 在旁边搭了一个连廊\n\n房子（nanobot/）保持原样\n连廊（ava/）可以任意装修\n上游更新只刷新房子，连廊不受影响", {
      x: 7.2, y: 2.0, w: 5.2, h: 1.2, fontSize: 11, fontFace: F.body, color: C.warmGray, margin: 0, lineSpacingMultiple: 1.4,
    });

    // Code lines stats
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 4.0, w: 5.8, h: 1.2, fill: { color: C.tealDeep } });
    s.addText("nanobot/ ~23,000 行", {
      x: 0.8, y: 4.1, w: 5.4, h: 0.5, fontSize: 20, fontFace: F.head, color: C.white, bold: true, margin: 0,
    });
    s.addText("上游框架代码（保持纯净）", {
      x: 0.8, y: 4.6, w: 5.4, h: 0.3, fontSize: 11, fontFace: F.body, color: C.seafoam, margin: 0,
    });

    s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 4.0, w: 5.8, h: 1.2, fill: { color: C.teal } });
    s.addText("ava/ ~16,000 行", {
      x: 7.0, y: 4.1, w: 5.4, h: 0.5, fontSize: 20, fontFace: F.head, color: C.white, bold: true, margin: 0,
    });
    s.addText("Sidecar 扩展", {
      x: 7.0, y: 4.6, w: 5.4, h: 0.3, fontSize: 11, fontFace: F.body, color: C.mintLight, margin: 0,
    });

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 8 — 代码行数统计对比图
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = whiteSlide(pres);
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.33, h: 0.06, fill: { color: C.teal } });
    slideTitle(s, "代码行数统计对比", 0.2);
    addHImage(s, IMG.codeLines, 1.0, 4.5);
    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 9 — Ava 架构全景图
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = whiteSlide(pres);
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.33, h: 0.06, fill: { color: C.teal } });
    slideTitle(s, "Ava 架构全景图", 0.2);
    slideSubtitle(s, "Nanobot 核心 + Ava Sidecar + Console + Tools", 0.75);
    addHImage(s, IMG.archOverview, 1.2, 4.3);
    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 10 — 已有能力一览
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = whiteSlide(pres);
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.33, h: 0.06, fill: { color: C.teal } });
    slideTitle(s, "已有能力一览", 0.2);

    const caps = [
      { title: "14 Monkey Patches", desc: "配置扩展 / 消息总线 / 上下文压缩\n核心循环注入 / 技能发现 / SQLite", color: C.teal },
      { title: "9 自定义工具", desc: "Claude Code / Codex CLI\n图片生成 / 视觉识别 / Page Agent\n记忆系统 / 网关控制", color: C.tealDark },
      { title: "Web Console", desc: "实时聊天 / 后台任务监控\nToken 统计 / 记忆 / 用户管理\n主题 / 版本检测 + 一键重建", color: C.green },
      { title: "后台任务 + Lifecycle", desc: "异步编码 → 通知 → 自动续跑\nsupervisor / 优雅关闭\n启动代次追踪", color: C.amber },
    ];
    caps.forEach((cap, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const cx = 0.6 + col * 6.2, cy = 1.0 + row * 2.4;
      s.addShape(pres.shapes.RECTANGLE, { x: cx, y: cy, w: 5.8, h: 2.1, fill: { color: C.offWhite }, shadow: mkShadow() });
      s.addShape(pres.shapes.RECTANGLE, { x: cx, y: cy, w: 5.8, h: 0.06, fill: { color: cap.color } });
      s.addText(cap.title, { x: cx + 0.2, y: cy + 0.2, w: 5.4, h: 0.4, fontSize: 16, fontFace: F.body, color: C.slate, bold: true, margin: 0 });
      s.addText(cap.desc, { x: cx + 0.2, y: cy + 0.7, w: 5.4, h: 1.2, fontSize: 12, fontFace: F.body, color: C.warmGray, margin: 0, lineSpacingMultiple: 1.4 });
    });
    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 11 — 半闭环示意图
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = freshSlide(pres);
    slideTitle(s, "带人工监督的研发半闭环", 0.3);

    // Pipeline steps
    const steps = [
      { label: "任务委托", color: C.green },
      { label: "后台执行", color: C.green },
      { label: "自动续跑", color: C.green },
      { label: "前端重建", color: C.green },
      { label: "Commit", color: C.amber },
      { label: "PR/Deploy", color: C.amber },
    ];
    steps.forEach((st, i) => {
      const cx = 0.6 + i * 2.1;
      s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 1.1, w: 1.85, h: 0.7, fill: { color: st.color, transparency: 15 } });
      s.addText(st.label, { x: cx, y: 1.1, w: 1.85, h: 0.7, fontSize: 12, fontFace: F.body, color: C.slate, bold: true, align: "center", valign: "middle", margin: 0 });
      if (i < steps.length - 1) s.addText("→", { x: cx + 1.85, y: 1.1, w: 0.25, h: 0.7, fontSize: 14, color: C.coolGray, align: "center", valign: "middle", margin: 0 });
    });

    // Legend
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 2.0, w: 0.3, h: 0.25, fill: { color: C.green, transparency: 15 } });
    s.addText("已打通", { x: 1.0, y: 2.0, w: 1, h: 0.25, fontSize: 10, color: C.green, fontFace: F.body, margin: 0, valign: "middle" });
    s.addShape(pres.shapes.RECTANGLE, { x: 2.2, y: 2.0, w: 0.3, h: 0.25, fill: { color: C.amber, transparency: 15 } });
    s.addText("待人工", { x: 2.6, y: 2.0, w: 1, h: 0.25, fontSize: 10, color: C.amber, fontFace: F.body, margin: 0, valign: "middle" });

    // 嵌入半闭环信息图
    addHImage(s, IMG.semiLoop, 2.5, 3.2);

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 12 — 故事1 标题页
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = freshSlide(pres);
    sectionNum(s, "04");
    slideTitle(s, "故事 1：改错地方");
    slideSubtitle(s, "AI 越过边界改了上游代码");

    // Problem card
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.8, w: 5.8, h: 2.0, fill: { color: C.white }, shadow: mkShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.8, w: 0.08, h: 2.0, fill: { color: C.red } });
    s.addText("症状", { x: 1.0, y: 1.9, w: 5.2, h: 0.35, fontSize: 14, fontFace: F.body, color: C.red, bold: true, margin: 0 });
    s.addText(`CLAUDE.md 明确写了 \"禁止修改 nanobot/\"\n但 AI 觉得改上游更快，就直接改了`, {
      x: 1.0, y: 2.3, w: 5.2, h: 0.5, fontSize: 12, fontFace: F.body, color: C.warmGray, margin: 0, lineSpacingMultiple: 1.4,
    });
    s.addText("规则在提示词里，不在架构里 — AI 有能力违反", {
      x: 1.0, y: 3.0, w: 5.2, h: 0.4, fontSize: 13, fontFace: F.body, color: C.amber, bold: true, margin: 0,
    });

    // Solution card
    s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 1.8, w: 5.8, h: 2.0, fill: { color: C.white }, shadow: mkShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 1.8, w: 0.08, h: 2.0, fill: { color: C.green } });
    s.addText("三层防御", { x: 7.2, y: 1.9, w: 5.2, h: 0.35, fontSize: 14, fontFace: F.body, color: C.green, bold: true, margin: 0 });

    const layers = [
      { l: "Layer 1  Instructions", d: "CLAUDE.md + SpecAnchor 模块契约" },
      { l: "Layer 2  Verification", d: "Guardrail 测试自动检测" },
      { l: "Layer 3  Scope", d: "pre-commit Hook 硬拦截" },
    ];
    layers.forEach((ly, i) => {
      const cy = 2.4 + i * 0.45;
      s.addText(ly.l, { x: 7.2, y: cy, w: 5.2, h: 0.22, fontSize: 11, fontFace: F.body, color: C.teal, bold: true, margin: 0 });
      s.addText(ly.d, { x: 7.2, y: cy + 0.2, w: 5.2, h: 0.22, fontSize: 10, fontFace: F.body, color: C.warmGray, margin: 0 });
    });

    // Bottom takeaway
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 4.1, w: 12.0, h: 0.6, fill: { color: C.teal, transparency: 10 } });
    s.addText("文档告诉 AI 不该做，测试发现 AI 做了，Hook 阻止 AI 的结果进入代码库", {
      x: 0.6, y: 4.1, w: 12.0, h: 0.6, fontSize: 14, fontFace: F.head, color: C.tealDeep, bold: true, align: "center", valign: "middle", margin: 0,
    });

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 13 — 约束分层图 (竖版图)
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = whiteSlide(pres);
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.33, h: 0.06, fill: { color: C.teal } });
    slideTitle(s, "约束的分层设计", 0.2);
    slideSubtitle(s, "瑞士奶酪模型 — 每一层不需要 100% 可靠，四层组合覆盖面就够了", 0.75);

    // Left side: text layers
    const ld = [
      { label: "Layer 4: CI / Guardrail Tests", desc: "最终兜底", color: C.tealDeep },
      { label: "Layer 3: Post-task Hooks", desc: "auto rebuild / auto continue", color: C.tealDark },
      { label: "Layer 2: Tool Description + Spec", desc: "委托优先 / SpecAnchor", color: C.teal },
      { label: "Layer 1: CLAUDE.md / AGENTS.md", desc: "文档规范", color: "66BFB8" },
    ];
    ld.forEach((ly, i) => {
      const cy = 1.2 + i * 0.9;
      s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: cy, w: 6.0, h: 0.75, fill: { color: ly.color } });
      s.addText(ly.label, { x: 0.8, y: cy, w: 4.0, h: 0.75, fontSize: 13, fontFace: F.body, color: C.white, bold: true, valign: "middle", margin: 0 });
      s.addText(ly.desc, { x: 4.8, y: cy, w: 1.7, h: 0.75, fontSize: 10, fontFace: F.body, color: C.white, align: "right", valign: "middle", margin: 0 });
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 4.85, w: 6.0, h: 0.4, fill: { color: C.warmGray } });
    s.addText("+ Sidecar 架构约束（结构性保障）", {
      x: 0.6, y: 4.85, w: 6.0, h: 0.4, fontSize: 10, fontFace: F.body, color: C.white, align: "center", valign: "middle", margin: 0,
    });

    // Right side: 竖版约束分层图
    addVImage(s, IMG.constraintLayer, 7.5, 0.5, 5.0);

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 14 — 故事2：改完不收尾
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = freshSlide(pres);
    slideTitle(s, "故事 2：改完不收尾", 0.35);
    slideSubtitle(s, "后台任务完成但 Agent 不继续 — 像员工做完任务发封邮件就下班了", 0.9);

    // auto_continue card
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.5, w: 5.8, h: 2.0, fill: { color: C.white }, shadow: mkShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.5, w: 0.08, h: 2.0, fill: { color: C.teal } });
    s.addText("auto_continue 机制", { x: 1.0, y: 1.6, w: 5.2, h: 0.35, fontSize: 14, fontFace: F.body, color: C.teal, bold: true, margin: 0 });
    s.addText(`1. 后台任务完成 → 自动注入结果到原会话\n2. 提示 Agent \"请继续处理后续步骤\"\n3. Agent 自动续跑：检查结果 → 后续处理`, {
      x: 1.0, y: 2.1, w: 5.2, h: 0.8, fontSize: 12, fontFace: F.body, color: C.warmGray, margin: 0, lineSpacingMultiple: 1.5,
    });

    // Budget card
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 3.0, w: 5.2, h: 0.06, fill: { color: C.amber } });
    s.addText("Continuation Budget — 加班额度", { x: 0.6, y: 3.1, w: 5.2, h: 0.35, fontSize: 13, fontFace: F.body, color: C.amber, bold: true, margin: 0 });
    s.addText("• 每个会话最多自动续跑 5 次\n• 防止 AI 陷入无限循环\n• 用户发新消息时 budget 自动重置", {
      x: 0.6, y: 3.5, w: 5.2, h: 0.8, fontSize: 11, fontFace: F.body, color: C.warmGray, margin: 0, lineSpacingMultiple: 1.4,
    });

    // Right: Continuation Budget 流程图
    s.addImage({ path: IMG.contBudget, x: 6.8, y: 1.3, w: 5.8, h: 5.8 * (768/1376) });

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 15 — Continuation Budget 工作流程图 (全幅)
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = whiteSlide(pres);
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.33, h: 0.06, fill: { color: C.teal } });
    slideTitle(s, "Continuation Budget 工作流程", 0.2);
    addHImage(s, IMG.contBudget, 1.0, 4.5);
    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 16 — 故事3：改完看不到
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = freshSlide(pres);
    slideTitle(s, "故事 3：改完看不到", 0.35);
    slideSubtitle(s, "前端改了但没有效果 — confidence ≠ correctness", 0.9);

    // Before/After cards
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.5, w: 5.5, h: 1.5, fill: { color: C.white }, shadow: mkShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.5, w: 5.5, h: 0.06, fill: { color: C.red } });
    s.addText("Before", { x: 0.8, y: 1.65, w: 5.1, h: 0.3, fontSize: 13, fontFace: F.body, color: C.red, bold: true, margin: 0 });
    s.addText("AI 改了 TypeScript 源码，没有 npm run build\n页面毫无变化\n\n类比：设计师改了 Figma 稿，但忘了导出切图给开发", {
      x: 0.8, y: 2.0, w: 5.1, h: 0.9, fontSize: 11, fontFace: F.body, color: C.warmGray, margin: 0, lineSpacingMultiple: 1.4,
    });

    s.addShape(pres.shapes.RECTANGLE, { x: 6.6, y: 1.5, w: 6.0, h: 1.5, fill: { color: C.white }, shadow: mkShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: 6.6, y: 1.5, w: 6.0, h: 0.06, fill: { color: C.green } });
    s.addText("After: post-task hook", { x: 6.8, y: 1.65, w: 5.6, h: 0.3, fontSize: 13, fontFace: F.body, color: C.green, bold: true, margin: 0 });
    s.addText("编码任务完成后自动检测前端产物新鲜度：\nsrc/ 修改时间 > dist/ 修改时间 → 自动 npm run build\n构建完成写入 dist/version.json 追踪版本", {
      x: 6.8, y: 2.0, w: 5.6, h: 0.9, fontSize: 11, fontFace: F.body, color: C.warmGray, margin: 0, lineSpacingMultiple: 1.4,
    });

    // Takeaway
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 3.3, w: 12.0, h: 0.5, fill: { color: C.teal, transparency: 10 } });
    s.addText("不需要 AI 记住每一个流程步骤 — 需要系统级兜底", {
      x: 0.6, y: 3.3, w: 12.0, h: 0.5, fontSize: 15, fontFace: F.head, color: C.tealDeep, bold: true, align: "center", valign: "middle", margin: 0,
    });

    // 嵌入 auto-rebuild 信息图
    addHImage(s, IMG.autoRebuild, 4.0, 2.5);

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 17 — 前端 auto-rebuild 逻辑示意图 (全幅)
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = whiteSlide(pres);
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.33, h: 0.06, fill: { color: C.teal } });
    slideTitle(s, "前端 auto-rebuild 逻辑", 0.2);
    addHImage(s, IMG.autoRebuild, 1.0, 4.5);
    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 18 — Sidecar 架构
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = freshSlide(pres);
    sectionNum(s, "05");
    slideTitle(s, "Sidecar 架构");
    slideSubtitle(s, "上游代码一个字不改，所有定制通过运行时注入");

    // Four guarantee cards
    const gs = [
      { label: "Guard 检查", desc: "先确认拦截点存在\n上游可能改了", color: C.teal },
      { label: "跳过逻辑", desc: "目标不在了不报错\n只告警并跳过", color: C.tealDark },
      { label: "幂等保证", desc: "同一个 patch\n执行两次 = 第二次跳过", color: C.green },
      { label: "自注册", desc: "每个 patch 末尾\nregister_patch() 自动注册", color: C.amber },
    ];
    gs.forEach((g, i) => {
      const cx = 0.6 + i * 3.15;
      s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 1.7, w: 2.9, h: 1.6, fill: { color: C.white }, shadow: mkShadow() });
      s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 1.7, w: 2.9, h: 0.06, fill: { color: g.color } });
      s.addText(g.label, { x: cx + 0.15, y: 1.9, w: 2.6, h: 0.35, fontSize: 14, fontFace: F.body, color: C.slate, bold: true, align: "center", margin: 0 });
      s.addText(g.desc, { x: cx + 0.15, y: 2.3, w: 2.6, h: 0.8, fontSize: 11, fontFace: F.body, color: C.warmGray, align: "center", margin: 0, lineSpacingMultiple: 1.4 });
    });

    // Patch map excerpt
    s.addText("Patch 风险热区图", { x: 0.6, y: 3.6, w: 12.0, h: 0.35, fontSize: 14, fontFace: F.body, color: C.slate, bold: true, margin: 0 });
    const rH = { fill: { color: C.teal }, color: C.white, bold: true, fontSize: 10, fontFace: F.body, align: "center", valign: "middle" };
    const rC = { fontSize: 10, fontFace: F.body, color: C.warmGray, valign: "middle" };
    const rA = { fill: { color: C.offWhite } };
    const rRows = [
      [{ text: "Patch", options: rH }, { text: "风险", options: rH }, { text: "说明", options: rH }],
      [{ text: "a_schema_patch", options: { ...rC, bold: true } }, { text: "CRITICAL", options: { ...rC, color: C.red, bold: true } }, { text: "上游 schema 大改需要同步 fork", options: rC }],
      [{ text: "loop_patch", options: { ...rC, bold: true, ...rA } }, { text: "HIGH", options: { ...rC, color: C.orange, bold: true, ...rA } }, { text: "核心枢纽，影响面最大", options: { ...rC, ...rA } }],
      [{ text: "context_patch", options: { ...rC, bold: true } }, { text: "HIGH", options: { ...rC, color: C.orange, bold: true } }, { text: "依赖 loop_patch 注入的组件", options: rC }],
      [{ text: "channel_patch", options: { ...rC, bold: true, ...rA } }, { text: "MEDIUM", options: { ...rC, color: C.amber, bold: true, ...rA } }, { text: "平台相关，变化频率中等", options: { ...rC, ...rA } }],
      [{ text: "其余 10 个 patch", options: { ...rC, bold: true } }, { text: "LOW", options: { ...rC, color: C.green, bold: true } }, { text: "接口稳定，独立模块", options: rC }],
    ];
    s.addTable(rRows, {
      x: 0.6, y: 4.0, w: 12.0, colW: [3.0, 1.2, 7.8],
      border: { pt: 0.5, color: C.borderGray }, rowH: [0.3, 0.3, 0.3, 0.3, 0.3, 0.3],
    });

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 19 — 14 Patches 执行顺序
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = whiteSlide(pres);
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.33, h: 0.06, fill: { color: C.teal } });
    slideTitle(s, "14 Patches 执行顺序", 0.2);
    slideSubtitle(s, "按字母序加载 — 命名就是依赖管理", 0.75);

    // Flow chart text
    s.addText(
      "a_schema → b_config (互斥：a 成功则 b 跳过) → c_onboard\n" +
      "       ↓\n" +
      "  bus → channel → console → context\n" +
      "       ↓\n" +
      "  loop (核心枢纽：注入数据库、Token统计、后台任务、生命周期管理)\n" +
      "       ↓\n" +
      "  provider_prefix → skills → storage → templates → tools → transcription",
      {
        x: 0.6, y: 1.3, w: 12.0, h: 2.5,
        fontSize: 13, fontFace: F.mono, color: C.warmGray, margin: 10,
        lineSpacingMultiple: 1.6,
        fill: { color: C.offWhite },
      }
    );

    // Key insight
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 4.2, w: 12.0, h: 0.6, fill: { color: C.teal, transparency: 10 } });
    s.addText("Sidecar 的代价：每次上游大改需检查拦截点 → 但比 fork 的全量合并可控得多", {
      x: 0.6, y: 4.2, w: 12.0, h: 0.6,
      fontSize: 14, fontFace: F.head, color: C.tealDeep, bold: true, align: "center", valign: "middle", margin: 0,
    });

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 20 — 三个核心洞察
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = freshSlide(pres);
    sectionNum(s, "06");
    slideTitle(s, "三个核心洞察");

    const insights = [
      {
        title: "架构判断",
        desc: "判断\u201C不做什么\u201D比\u201C做什么\u201D更难\n什么放 patch、什么放 fork、什么该提 PR 给上游\n\u2014\u2014这个边界的把握是最重要的一课",
        color: C.teal,
      },
      {
        title: "治理意识",
        desc: "Prompt 是软护栏，影响 AI \u201C想做什么\u201D\n但 AI 有能力不做你想让它做的事\n把 prompt 失效的地方变成硬护栏：测试、Hook、运行时控制",
        color: C.tealDark,
      },
      {
        title: "闭环思维",
        desc: "看到问题不难，难的是把问题变成代码\n\u201C不舒服\u201D \u2192 \u201C自动化\u201D\n持续地将手工操作转化为系统机制",
        color: C.tealDeep,
      },
    ];
    insights.forEach((ins, i) => {
      const cx = 0.6 + i * 4.1;
      s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 1.4, w: 3.8, h: 3.0, fill: { color: C.white }, shadow: mkShadow() });
      s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 1.4, w: 3.8, h: 0.06, fill: { color: ins.color } });
      s.addText(ins.title, { x: cx + 0.2, y: 1.65, w: 3.4, h: 0.4, fontSize: 18, fontFace: F.head, color: C.slate, bold: true, margin: 0 });
      s.addText(ins.desc, { x: cx + 0.2, y: 2.2, w: 3.4, h: 2.0, fontSize: 12, fontFace: F.body, color: C.warmGray, margin: 0, lineSpacingMultiple: 1.5 });
    });

    // Bottom note
    s.addText("上下文的质量决定了 AI 决策的质量 — SpecAnchor 通过三级 Spec 按需加载最新项目上下文", {
      x: 0.6, y: 4.8, w: 12.0, h: 0.4, fontSize: 11, fontFace: F.body, color: C.coolGray, italic: true, align: "center", margin: 0,
    });

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 21 — 三个可复用模式
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = freshSlide(pres);
    slideTitle(s, "你今天就能带走的三个模式", 0.35);

    const pats = [
      {
        title: "Sidecar 扩展",
        desc: "依赖开源项目但需要深度定制？\n不要 fork，在旁边扩展\n\n前提：上游有可 patch 点\n成本：patch 维护 + 上游变更追踪\n收益：日常同步冲突从结构上降到最小",
        color: C.teal,
      },
      {
        title: "软硬护栏组合",
        desc: "软护栏（提示词/Spec）决定 AI \"想做什么\"\n硬护栏（测试/CI/Hook）决定 AI \"能做什么\"\n\n两者缺一不可\n你不需要每层 100% 可靠\n但至少需要两层——任何单层都有盲区",
        color: C.tealDark,
      },
      {
        title: "Post-task 自动化",
        desc: "AI 改完代码后有固定后续步骤？\n不依赖 AI 记住，用 Hook 系统级兜底\n\n特别适合：改完要 build、跑 visual regression\n改完 API 要更新 SDK\nHook 永远不会忘",
        color: C.tealDeep,
      },
    ];
    pats.forEach((p, i) => {
      const cx = 0.6 + i * 4.1;
      s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 1.2, w: 3.8, h: 4.0, fill: { color: C.white }, shadow: mkShadow() });
      s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 1.2, w: 3.8, h: 0.06, fill: { color: p.color } });
      s.addText(p.title, { x: cx + 0.2, y: 1.45, w: 3.4, h: 0.45, fontSize: 18, fontFace: F.head, color: C.slate, bold: true, margin: 0 });
      s.addText(p.desc, { x: cx + 0.2, y: 2.0, w: 3.4, h: 3.0, fontSize: 11, fontFace: F.body, color: C.warmGray, margin: 0, lineSpacingMultiple: 1.5 });
    });

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 22 — 下一步
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = freshSlide(pres);
    slideTitle(s, "接下来打算做的事", 0.4);

    const plans = [
      { num: "1", title: "发布闭环", desc: "自动 commit / PR / 部署\n真正实现从\u201C收到需求\u201D到\u201C上线\u201D的全流程" },
      { num: "2", title: "SpecAnchor 完善", desc: "Task Spec 知识回流到 Module Spec\n自动化程度更高" },
      { num: "3", title: "多 Agent 协同", desc: "一个写代码，一个 review，一个测试\n从单 Agent 到协作 Agent" },
    ];
    plans.forEach((p, i) => {
      const cx = 0.6 + i * 4.1;
      s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 1.2, w: 3.8, h: 2.5, fill: { color: C.white }, shadow: mkShadow() });
      s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 1.2, w: 0.5, h: 0.5, fill: { color: C.teal } });
      s.addText(p.num, { x: cx, y: 1.2, w: 0.5, h: 0.5, fontSize: 18, fontFace: F.head, color: C.white, bold: true, align: "center", valign: "middle", margin: 0 });
      s.addText(p.title, { x: cx + 0.6, y: 1.25, w: 3.0, h: 0.45, fontSize: 16, fontFace: F.head, color: C.slate, bold: true, valign: "middle", margin: 0 });
      s.addText(p.desc, { x: cx + 0.2, y: 1.9, w: 3.4, h: 1.5, fontSize: 12, fontFace: F.body, color: C.warmGray, margin: 0, lineSpacingMultiple: 1.5 });
    });

    // Core message
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 4.2, w: 12.0, h: 0.8, fill: { color: C.tealDeep } });
    s.addText("在 AI Coding 中，给 AI 设计边界\n——把约束从提示词变成架构、测试和自动化——对团队和个人都有很高的价值", {
      x: 0.6, y: 4.2, w: 12.0, h: 0.8,
      fontSize: 14, fontFace: F.head, color: C.white, bold: true, align: "center", valign: "middle", margin: 0, lineSpacingMultiple: 1.3,
    });

    pageNum(s, pn);
  }

  // ═══════════════════════════════════════════
  // Slide 23 — Q&A
  // ═══════════════════════════════════════════
  {
    pn++;
    const s = tealSlide(pres);
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.33, h: 0.06, fill: { color: C.mint } });

    s.addText("Q & A", {
      x: 0.6, y: 1.5, w: 12.0, h: 1.0,
      fontSize: 48, fontFace: F.head, color: C.white, bold: true, align: "center", margin: 0,
    });
    s.addShape(pres.shapes.RECTANGLE, { x: 5.5, y: 2.6, w: 2.3, h: 0.04, fill: { color: C.mint } });
    s.addText([
      { text: "AI 越来越强，但 \"强\" 不等于 \"可靠\"\n", options: { bold: true, color: C.white, fontSize: 18 } },
      { text: "让 AI 的输出更可靠，可能比让 AI 更强更重要", options: { color: C.seafoam, fontSize: 15 } },
    ], { x: 0.6, y: 2.9, w: 12.0, h: 1.2, fontFace: F.head, align: "center", margin: 0, lineSpacingMultiple: 1.6 });

    s.addText("方壶  |  2026.04", {
      x: 0.6, y: 5.0, w: 12.0, h: 0.3,
      fontSize: 12, fontFace: F.body, color: C.seafoam, align: "center", margin: 0,
    });
    pageNum(s, pn);
  }

  // ── Save ──
  const out = "/Users/fanghu/Documents/Test/nanobot__ava/docs/tech-sharing-slides.pptx";
  await pres.writeFile({ fileName: out });
  const stats = fs.statSync(out);
  console.log(`Generated: ${out}`);
  console.log(`Slides: ${TOTAL}`);
  console.log(`File size: ${(stats.size / 1024 / 1024).toFixed(2)} MB`);
}

build().catch((err) => {
  console.error("Build failed:", err);
  process.exit(1);
});
