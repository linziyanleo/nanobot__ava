#!/usr/bin/env python3
"""Patch tech-sharing-slides.html with 8 modifications."""

import base64
import re
import sys

HTML_PATH = '/Users/fanghu/Documents/Test/nanobot__ava/docs/tech-sharing-slides.html'

def read_image_base64(path):
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')

def main():
    with open(HTML_PATH, 'r', encoding='utf-8') as f:
        html = f.read()

    original_len = len(html)

    # =========================================================================
    # 改动 1 & 2: Page 3 (龙虾悖论) - 左右两栏 + OpenClaw图片 + 94%数据块
    # =========================================================================
    openclaw_img_b64 = read_image_base64(
        '/Users/fanghu/Documents/Test/nanobot__ava/docs/media/openclaw安全风险.png'
    )

    # Find the 10.8% stat block and its parent flex container
    old_page3_content = '''<div style="margin-top: 32px; display: flex; gap: 40px; align-items: center;">
      <div>
        <div class="stat-num">10.8%</div>
        <p style="font-size: 1.1rem;">OpenClaw 3000+ 插件中<br>包含恶意代码的比例</p>
      </div>
      <div style="flex: 1;">
        <p style="font-size: 1.15rem; line-height: 1.9;">
          用户账户被盗刷、文件被一键清空——这些不是假设，是真实发生过的事件。<br><br>
          我们日常用 Cursor、Claude Code、Codex 写代码时，面临着同样的困境。
        </p>
      </div>
    </div>'''

    new_page3_content = f'''<div style="margin-top: 32px; display: flex; gap: 40px; align-items: flex-start;">
      <div style="flex: 1;">
        <div>
          <div class="stat-num">10.8%</div>
          <p style="font-size: 1.1rem;">OpenClaw 3000+ 插件中<br>包含恶意代码的比例</p>
        </div>
        <div class="stat-highlight" style="margin-top: 24px; padding: 20px; background: rgba(245,158,11,0.1); border-radius: 12px; border: 1px solid rgba(245,158,11,0.3);">
          <span class="stat-number" style="display: block; font-size: 4rem; font-weight: 800; color: #f59e0b; line-height: 1;">94%</span>
          <span class="stat-label" style="display: block; font-size: 1.2rem; color: #fde68a; margin-top: 8px;">的AI Agent存在可被利用的漏洞</span>
          <span class="stat-source" style="display: block; font-size: 0.85rem; color: #a78bfa; margin-top: 4px;">— 2025年安全研究报告</span>
        </div>
        <p style="font-size: 1.05rem; line-height: 1.9; margin-top: 20px;">
          用户账户被盗刷、文件被一键清空——这些不是假设，是真实发生过的事件。<br>
          我们日常用 Cursor、Claude Code、Codex 写代码时，面临着同样的困境。
        </p>
      </div>
      <div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 12px;">
        <img src="data:image/png;base64,{openclaw_img_b64}" alt="OpenClaw安全风险" style="max-width: 100%; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.3);">
        <p style="font-size: 0.9rem; color: #94a3b8; text-align: center;">Meta安全总监邮件被删事件</p>
      </div>
    </div>'''

    if old_page3_content not in html:
        print("ERROR: Cannot find Page 3 content for modification 1&2")
        sys.exit(1)
    html = html.replace(old_page3_content, new_page3_content)
    print("✓ 改动 1&2: Page 3 左右两栏 + OpenClaw图片 + 94%数据块")

    # =========================================================================
    # 改动 3: Page 5 - 加超链接
    # =========================================================================
    link_style = 'style="color:#a78bfa;text-decoration:underline" target="_blank"'

    old_openai = '<strong>OpenAI Codex：</strong>Humans steer, Agents execute —— 人类掌舵，Agent 执行'
    new_openai = f'<strong><a href="https://openai.com/index/harness-engineering/" {link_style}>OpenAI Codex</a>：</strong>Humans steer, Agents execute —— 人类掌舵，Agent 执行'

    old_anthropic = '<strong>Anthropic：</strong>长时程 Agent 必须靠机制才能跨 context 推进'
    new_anthropic = f'<strong><a href="https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents" {link_style}>Anthropic</a>：</strong>长时程 Agent 必须靠机制才能跨 context 推进'

    if old_openai not in html:
        print("ERROR: Cannot find OpenAI text for modification 3")
        sys.exit(1)
    html = html.replace(old_openai, new_openai)
    html = html.replace(old_anthropic, new_anthropic)
    print("✓ 改动 3: Page 5 加超链接")

    # =========================================================================
    # 改动 4: Page 6 (Harness = AI 的游乐场) - 替换五子系统ASCII图为信息图
    # =========================================================================
    harness_img_b64 = read_image_base64(
        '/Users/fanghu/.nanobot/media/generated/7d348e34cef2_5.png'
    )

    # Match the ASCII art block inside the "Harness = AI 的游乐场" slide
    old_harness_content = '''<div style="margin-top: 40px;">
      <pre style="max-width: 700px; font-size: 0.95rem;"><span class="code-comment">┌─────────────────────────────────────────────────┐</span>
<span class="code-comment">│</span>                  <span class="code-keyword">THE HARNESS</span>                     <span class="code-comment">│</span>
<span class="code-comment">│</span>                                                  <span class="code-comment">│</span>
<span class="code-comment">│</span>  <span class="code-func">Instructions</span>    <span class="code-func">State</span>         <span class="code-func">Verification</span>      <span class="code-comment">│</span>
<span class="code-comment">│</span>  <span class="code-string">(做什么)</span>        <span class="code-string">(做到哪了)</span>     <span class="code-string">(做对了吗)</span>         <span class="code-comment">│</span>
<span class="code-comment">│</span>                                                  <span class="code-comment">│</span>
<span class="code-comment">│</span>  <span class="code-func">Scope</span>           <span class="code-func">Session Lifecycle</span>               <span class="code-comment">│</span>
<span class="code-comment">│</span>  <span class="code-string">(一次只做一件事)</span>  <span class="code-string">(开始初始化、结束清理)</span>            <span class="code-comment">│</span>
<span class="code-comment">└─────────────────────────────────────────────────┘</span></pre>
    </div>'''

    new_harness_content = f'''<div class="img-container full-width" style="margin-top: 24px;">
      <img src="data:image/png;base64,{harness_img_b64}" alt="Harness五子系统信息图" style="max-width: 90%; border-radius: 12px;">
      <p style="margin-top: 12px; font-size: 1rem; color: #c4b5fd;">SpecAnchor 同时承担 State + Scope 两个子系统</p>
    </div>'''

    if old_harness_content not in html:
        print("ERROR: Cannot find Harness ASCII art for modification 4")
        sys.exit(1)
    html = html.replace(old_harness_content, new_harness_content)
    print("✓ 改动 4: Page 6 Harness五子系统替换为信息图")

    # =========================================================================
    # 改动 5: 在 Nanobot/Ava 第一页前插入 Nanobot 介绍页
    # =========================================================================
    nanobot_intro_slide = '''
  <section class="slide" id="slide-nanobot-intro" data-chapter="Nanobot / Ava">
    <div class="slide-header"><span class="chapter">三、Nanobot/Ava</span></div>
    <div class="slide-content" style="display:flex;align-items:center;gap:3rem">
      <div style="flex:1">
        <h2 style="font-size:2.2rem;margin-bottom:1rem">Nanobot<br><span style="color:#a78bfa;font-size:1.4rem">Inspired by OpenClaw, 99% fewer lines</span></h2>
        <ul class="feature-list">
          <li>🪶 <strong>轻量</strong>：核心约 23,000 行，个人开发者可完全掌控</li>
          <li>⚡ <strong>能力完整</strong>：工具调用 / 记忆 / 多轮对话 / 多通道接入</li>
          <li>🔧 <strong>为什么选它</strong>：足够轻、足够可读，让 Harness 实验真正可行</li>
        </ul>
        <blockquote style="border-left:3px solid #a78bfa;padding-left:1rem;margin-top:2rem;color:#c4b5fd;font-style:italic">
          "就像自己组装台式电脑 vs 买 Mac Studio——<br>自己拧每颗螺丝，才能真正理解构成"
        </blockquote>
      </div>
    </div>
  </section>

'''

    # The first Nanobot/Ava slide starts with "为什么选 Sidecar 而不是 Fork"
    nanobot_first_marker = '  <section class="slide" data-chapter="Nanobot / Ava">\n    <h2>为什么选 Sidecar 而不是 Fork</h2>'
    if nanobot_first_marker not in html:
        print("ERROR: Cannot find Nanobot/Ava first slide for modification 5")
        sys.exit(1)
    html = html.replace(nanobot_first_marker, nanobot_intro_slide + nanobot_first_marker)
    print("✓ 改动 5: 插入 Nanobot 介绍页")

    # =========================================================================
    # 改动 6: 半闭环信息图替换
    # =========================================================================
    semiclosed_img_b64 = read_image_base64(
        '/Users/fanghu/.nanobot/media/generated/66b230742e1d_5.png'
    )

    # The 半闭环 slide has an img with alt="半闭环示意图"
    # Use regex to replace the img tag's src while keeping the rest
    pattern_semiclosed = r'(<img\s[^>]*alt="半闭环示意图"[^>]*src=")data:image/png;base64,[A-Za-z0-9+/=]+'
    replacement_semiclosed = f'\\1data:image/png;base64,{semiclosed_img_b64}'

    if not re.search(pattern_semiclosed, html):
        # Try alternative: src before alt
        pattern_semiclosed = r'(<img\s[^>]*src=")data:image/png;base64,[A-Za-z0-9+/=]+("[^>]*alt="半闭环示意图")'
        replacement_semiclosed = f'\\1data:image/png;base64,{semiclosed_img_b64}\\2'

    html_new = re.sub(pattern_semiclosed, replacement_semiclosed, html, count=1)
    if html_new == html:
        print("ERROR: Cannot find 半闭环 image for modification 6")
        sys.exit(1)
    html = html_new
    print("✓ 改动 6: 半闭环信息图替换")

    # =========================================================================
    # 改动 7: 约束分层图幻灯片移到故事3后面
    # =========================================================================
    # Find the story 1 (约束分层) slide: starts with <!-- Slide 13: 故事一 约束分层 -->
    # and ends before the next <section class="slide"
    story1_comment = '<!-- Slide 13: 故事一 约束分层 -->'
    story1_start = html.find(story1_comment)
    if story1_start == -1:
        print("ERROR: Cannot find story 1 comment for modification 7")
        sys.exit(1)

    # Find the start of the <section> tag (it may start right after the comment or with whitespace)
    section_start = html.find('<section class="slide"', story1_start)
    # Find the closing </section> for this slide
    section_end = html.find('</section>', section_start)
    section_end = section_end + len('</section>')

    # Extract the full slide (including the comment before it)
    # Include any whitespace before the comment
    line_start = html.rfind('\n', 0, story1_start) + 1
    story1_block = html[line_start:section_end]

    # Remove it from original position
    html = html[:line_start] + html[section_end:]

    # Now find story 3 (前端改了但没有效果) and insert after it
    story3_marker = '<h2>故事 3：前端改了但没有效果</h2>'
    story3_pos = html.find(story3_marker)
    if story3_pos == -1:
        print("ERROR: Cannot find story 3 for modification 7")
        sys.exit(1)

    # Find the </section> closing this story 3 slide
    story3_section_end = html.find('</section>', story3_pos)
    story3_section_end = story3_section_end + len('</section>')

    # Insert story 1 after story 3
    html = html[:story3_section_end] + '\n\n' + story1_block + html[story3_section_end:]
    print("✓ 改动 7: 约束分层图移到故事3后面")

    # =========================================================================
    # 改动 8: 新增 SpecAnchor 故事页（在移动后的约束分层图页后面）
    # =========================================================================
    specanchor_img_b64 = read_image_base64(
        '/Users/fanghu/.nanobot/media/generated/def5dd46ef2a_5.png'
    )

    specanchor_slide = f'''
  <section class="slide" id="slide-specanchor" data-chapter="三个真实故事">
    <div class="slide-header"><span class="chapter">四、三个真实故事（延伸）</span><span class="page-num"></span></div>
    <div class="slide-content" style="display:flex;gap:3rem;align-items:flex-start">
      <div style="flex:1">
        <h2>番外：SpecAnchor</h2>
        <p style="color:#c4b5fd;font-size:1.1rem;margin-bottom:1.5rem">从故事里长出来的 Skill</p>
        <blockquote style="border-left:3px solid #f59e0b;padding-left:1rem;margin-bottom:1.5rem;color:#fde68a;font-style:italic">
          "光靠 CLAUDE.md 写'禁止改 nanobot/'是不够的——<br>AI 需要具体到模块粒度的契约"
        </blockquote>
        <ul class="feature-list">
          <li>🌐 <strong>Global Spec</strong>：项目级约束，对所有AI任务生效</li>
          <li>📦 <strong>Module Spec</strong>：模块级契约，动手前先加载边界</li>
          <li>📝 <strong>Task Spec</strong>：单次任务上下文 + 经验回流</li>
        </ul>
        <div style="margin-top:1.5rem;padding:1rem;background:rgba(167,139,250,0.1);border-radius:8px">
          <p style="margin:0;color:#a78bfa">在 Harness 中同时承担：<strong>State 子系统</strong> + <strong>Scope 子系统</strong></p>
        </div>
        <p style="margin-top:1.5rem;font-size:1.2rem;color:#e2e8f0;font-weight:600">
          💡 上下文的质量决定了 AI 决策的质量
        </p>
      </div>
      <div style="flex:1">
        <img src="data:image/png;base64,{specanchor_img_b64}" alt="SpecAnchor信息图" style="max-width:100%;border-radius:12px;">
      </div>
    </div>
  </section>
'''

    # Find the moved story1 block (约束分层) - now after story 3
    # Look for it by the unique marker
    moved_story1_marker = '故事 1：AI 越过边界改了上游代码'
    moved_pos = html.find(moved_story1_marker)
    if moved_pos == -1:
        print("ERROR: Cannot find moved story 1 for modification 8")
        sys.exit(1)

    # Find the </section> closing this moved slide
    moved_section_end = html.find('</section>', moved_pos)
    moved_section_end = moved_section_end + len('</section>')

    # Insert SpecAnchor slide after the moved 约束分层 slide
    html = html[:moved_section_end] + '\n' + specanchor_slide + html[moved_section_end:]
    print("✓ 改动 8: 新增 SpecAnchor 故事页")

    # =========================================================================
    # Write back
    # =========================================================================
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n完成！文件大小: {original_len} → {len(html)} bytes (+{len(html)-original_len})")

if __name__ == '__main__':
    main()
