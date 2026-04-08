#!/usr/bin/env python3
"""Patch tech-sharing-slides.html - fix layout issues (batch 2)."""

import re
import sys

HTML_PATH = '/Users/fanghu/Documents/Test/nanobot__ava/docs/tech-sharing-slides.html'


def main():
    with open(HTML_PATH, 'r', encoding='utf-8') as f:
        html = f.read()

    original_len = len(html)
    changes = []

    # =========================================================================
    # 问题1: Page 3 (龙虾悖论/OpenClaw安全风险) - 简化右侧图片区域
    # 右侧 div 中的 img 样式替换为指定样式，保留单张图片和标注
    # =========================================================================
    old_right_div = (
        '<div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 12px;">\n'
        '        <img src="data:image/png;base64,'
    )
    if old_right_div in html:
        # Extract the base64 data for the image
        right_div_start = html.index(old_right_div)
        # Find the closing </div> of this right column
        # Pattern: from the div start to the next </div>\n    </div>\n  </section>
        right_section_pattern = re.compile(
            r'<div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 12px;">\s*'
            r'<img src="(data:image/png;base64,[^"]+)" alt="[^"]*"[^>]*>\s*'
            r'<p style="[^"]*">([^<]*)</p>\s*'
            r'</div>',
            re.DOTALL
        )
        m = right_section_pattern.search(html)
        if m:
            img_src = m.group(1)
            new_right_div = (
                '<div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 12px;">\n'
                f'        <img src="{img_src}" alt="OpenClaw安全风险" '
                'style="max-width:100%; max-height:60vh; object-fit:contain; border-radius:8px;">\n'
                '        <p style="font-size: 0.9rem; color: #94a3b8; text-align: center;">'
                'Meta安全总监邮件被删事件（2024）</p>\n'
                '      </div>'
            )
            html = html[:m.start()] + new_right_div + html[m.end():]
            changes.append("问题1: 简化Page3右侧图片区域，统一图片样式，更新标注文字")
        else:
            changes.append("问题1: 未找到右侧图片区域的完整匹配，跳过")
    else:
        changes.append("问题1: 未找到右侧div起始标记，跳过")

    # =========================================================================
    # 问题2: Page 6 (Harness五子系统) - 删除重复的SpecAnchor文字
    # 删除 line 826 附近的 <p>SpecAnchor 同时承担 State + Scope 两个子系统</p>
    # =========================================================================
    old_specanchor_p = '      <p style="margin-top: 12px; font-size: 1rem; color: #c4b5fd;">SpecAnchor 同时承担 State + Scope 两个子系统</p>\n'
    if old_specanchor_p in html:
        html = html.replace(old_specanchor_p, '', 1)
        changes.append("问题2: 删除Harness游乐场页中重复的SpecAnchor文字")
    else:
        changes.append("问题2: 未找到SpecAnchor重复文字，跳过")

    # =========================================================================
    # 问题3: Page 8 (nanobot-intro) - 改为单栏居中布局
    # 移除 slide-header（JS会自动生成），将 flex 两栏改为单栏居中
    # =========================================================================
    old_nanobot = (
        '<section class="slide" id="slide-nanobot-intro" data-chapter="Nanobot / Ava">\n'
        '    <div class="slide-header"><span class="chapter">三、Nanobot/Ava</span></div>\n'
        '    <div class="slide-content" style="display:flex;align-items:center;gap:3rem">\n'
        '      <div style="flex:1">\n'
        '        <h2 style="font-size:2.2rem;margin-bottom:1rem">Nanobot<br><span style="color:#a78bfa;font-size:1.4rem">Inspired by OpenClaw, 99% fewer lines</span></h2>\n'
        '        <ul class="feature-list">\n'
        '          <li>🪶 <strong>轻量</strong>：核心约 23,000 行，个人开发者可完全掌控</li>\n'
        '          <li>⚡ <strong>能力完整</strong>：工具调用 / 记忆 / 多轮对话 / 多通道接入</li>\n'
        '          <li>🔧 <strong>为什么选它</strong>：足够轻、足够可读，让 Harness 实验真正可行</li>\n'
        '        </ul>\n'
        '        <blockquote style="border-left:3px solid #a78bfa;padding-left:1rem;margin-top:2rem;color:#c4b5fd;font-style:italic">\n'
        '          "就像自己组装台式电脑 vs 买 Mac Studio——<br>自己拧每颗螺丝，才能真正理解构成"\n'
        '        </blockquote>\n'
        '      </div>\n'
        '    </div>\n'
        '  </section>'
    )

    new_nanobot = (
        '<section class="slide" id="slide-nanobot-intro" data-chapter="Nanobot / Ava">\n'
        '    <h2 style="font-size:2.2rem;margin-bottom:1rem;text-align:center">Nanobot<br><span style="color:#a78bfa;font-size:1.4rem">Inspired by OpenClaw, 99% fewer lines</span></h2>\n'
        '    <div style="max-width:720px;margin:0 auto">\n'
        '      <ul class="feature-list">\n'
        '        <li>🪶 <strong>轻量</strong>：核心约 23,000 行，个人开发者可完全掌控</li>\n'
        '        <li>⚡ <strong>能力完整</strong>：工具调用 / 记忆 / 多轮对话 / 多通道接入</li>\n'
        '        <li>🔧 <strong>为什么选它</strong>：足够轻、足够可读，让 Harness 实验真正可行</li>\n'
        '      </ul>\n'
        '      <blockquote style="border-left:3px solid #a78bfa;padding-left:1rem;margin-top:2rem;color:#c4b5fd;font-style:italic">\n'
        '        "就像自己组装台式电脑 vs 买 Mac Studio——<br>自己拧每颗螺丝，才能真正理解构成"\n'
        '      </blockquote>\n'
        '    </div>\n'
        '  </section>'
    )

    if old_nanobot in html:
        html = html.replace(old_nanobot, new_nanobot, 1)
        changes.append("问题3: nanobot-intro页改为单栏居中布局，移除多余slide-header")
    else:
        changes.append("问题3: 未找到nanobot-intro精确匹配，跳过")

    # =========================================================================
    # 改动6 + 问题4/5: 故事顺序调整 (故事2→故事3→故事1 改为 故事1→故事2→故事3)
    # 提取三个故事的 section，按正确顺序重组
    # =========================================================================
    # 故事2: 从 <section class="slide" data-chapter="三个真实故事"> 第一个
    #         到其 </section>
    # 故事3: 第二个
    # 故事1: 第三个 (<!-- Slide 13: 故事一 约束分层 --> 之后)

    # Find all three story sections by their markers
    story2_marker = '<h2>故事 2：后台任务完成但 Agent 不继续</h2>'
    story3_marker = '<h2>故事 3：前端改了但没有效果</h2>'
    story1_marker = '<h2>故事 1：AI 越过边界改了上游代码</h2>'

    # Find the section containing each story
    def extract_section(html, marker):
        """Extract the full <section>...</section> containing the marker."""
        pos = html.find(marker)
        if pos == -1:
            return None, -1, -1
        # Find the <section that starts before this marker
        section_start = html.rfind('<section class="slide"', 0, pos)
        if section_start == -1:
            return None, -1, -1
        # Find the </section> after the marker
        section_end = html.find('</section>', pos)
        if section_end == -1:
            return None, -1, -1
        section_end += len('</section>')
        return html[section_start:section_end], section_start, section_end

    story2_html, s2_start, s2_end = extract_section(html, story2_marker)
    story3_html, s3_start, s3_end = extract_section(html, story3_marker)
    story1_html, s1_start, s1_end = extract_section(html, story1_marker)

    if all([story1_html, story2_html, story3_html]):
        # Also capture the comment before 故事1 section
        # Current order in file: story2 (first), story3 (second), story1 (third)
        # We need: story1, story2, story3

        # Find the comment before story3
        comment_before_story3 = '\n\n  <!-- Slide 15: 故事三 前端 auto-rebuild -->\n'
        # Find the comment before story1
        comment_before_story1 = '\n\n  <!-- Slide 13: 故事一 约束分层 -->\n'

        # The region to replace: from story2 start to story1 end
        # This includes: story2 + comment + story3 + comment + story1
        region_start = s2_start
        region_end = s1_end

        # Build new region: story1 + story2 + story3 (with appropriate comments)
        new_region = (
            '  <!-- Slide 13: 故事一 约束分层 -->\n'
            f'  {story1_html}\n'
            '\n'
            f'  {story2_html}\n'
            '\n'
            '  <!-- Slide 15: 故事三 前端 auto-rebuild -->\n'
            f'  {story3_html}'
        )

        # Find what's before region_start (whitespace/comments)
        # Look backwards from region_start to find the comment for story2
        pre_region = html[max(0, region_start - 200):region_start]
        # Check if there's a comment right before
        comment_match = re.search(r'\n\n  <!-- [^>]+ -->\n  $', pre_region)
        if comment_match:
            # Include the comment in the replacement
            actual_start = region_start - (len(pre_region) - comment_match.start())
            old_region = html[actual_start:region_end]
            html = html[:actual_start] + '\n\n' + new_region + html[region_end:]
        else:
            old_region = html[region_start:region_end]
            html = html[:region_start] + new_region + html[region_end:]

        changes.append("改动6: 调整故事顺序为 故事1→故事2→故事3")
    else:
        missing = []
        if not story1_html:
            missing.append("故事1")
        if not story2_html:
            missing.append("故事2")
        if not story3_html:
            missing.append("故事3")
        changes.append(f"改动6: 未找到故事section: {', '.join(missing)}，跳过")

    # =========================================================================
    # Write result
    # =========================================================================
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

    new_len = len(html)
    print(f"原始大小: {original_len:,} 字符")
    print(f"修改后大小: {new_len:,} 字符")
    print(f"差异: {new_len - original_len:+,} 字符")
    print()
    for i, c in enumerate(changes, 1):
        print(f"  {i}. {c}")


if __name__ == '__main__':
    main()
