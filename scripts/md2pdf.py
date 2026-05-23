#!/usr/bin/env python3
"""
md2pdf.py — 将中文法律文书 Markdown 转为 PDF
用法: python3 md2pdf.py <input.md> [output.pdf]

依赖: pip install PyMuPDF
字体: 使用 PyMuPDF 内置 CJK 字体 (china-s 宋体, china-ss 黑体)
页面: A4, 1英寸边距
"""
import fitz
import re
import os
import sys


def convert(md_path, pdf_path):
    with open(md_path, "r", encoding="utf-8") as f:
        md = f.read()

    lines = md.split("\n")
    doc = fitz.open()

    PW, PH = 595.28, 841.89
    MARGIN = 72
    CW = PW - 2 * MARGIN
    FN_SONG = "china-s"
    FN_HEI = "china-ss"
    SZ_TITLE, SZ_H2, SZ_H3, SZ_H4, SZ_BODY = 20, 16, 14, 12.5, 11

    class Renderer:
        def __init__(self):
            self._new_page()

        def _new_page(self):
            self.page = doc.new_page(width=PW, height=PH)
            self.y = MARGIN

        def _check(self, h):
            if self.y + h > PH - MARGIN:
                self._new_page()

        def text(self, txt, sz, fn, align="left"):
            tw = fitz.get_text_length(txt, fontname=fn, fontsize=sz)
            if align == "center":
                tx = (PW - tw) / 2
            elif align == "right":
                tx = PW - MARGIN - tw
            else:
                tx = MARGIN
            self._check(sz + 4)
            self.page.insert_text(fitz.Point(tx, self.y + sz), txt, fontname=fn, fontsize=sz)
            self.y += sz + 4

        def wrapped(self, txt, sz, fn, indent=0):
            max_w = CW - indent
            buf = ""
            first = True
            for ch in txt:
                test = buf + ch
                tw = fitz.get_text_length(test, fontname=fn, fontsize=sz)
                limit = max_w if first else CW
                if tw > limit:
                    if buf:
                        self._check(sz + 2)
                        tx = MARGIN + (indent if first else 0)
                        self.page.insert_text(fitz.Point(tx, self.y + sz), buf, fontname=fn, fontsize=sz)
                        self.y += sz + 2
                    buf = ch
                    first = False
                else:
                    buf = test
            if buf:
                self._check(sz + 2)
                tx = MARGIN + (indent if first else 0)
                self.page.insert_text(fitz.Point(tx, self.y + sz), buf, fontname=fn, fontsize=sz)
                self.y += sz + 2

    r = Renderer()
    i = 0
    while i < len(lines):
        s = lines[i].strip()

        if s == "---":
            r.y += 8; i += 1; continue
        if s == "":
            r.y += 6; i += 1; continue

        # 标题（清除markdown标记）
        if s.startswith("# ") and not s.startswith("## "):
            r.text(s[2:].replace("**", ""), SZ_TITLE, FN_HEI, align="center"); r.y += 10; i += 1; continue
        if s.startswith("## "):
            r.y += 12; r.text(s[3:].replace("**", ""), SZ_H2, FN_HEI); r.y += 6; i += 1; continue
        if s.startswith("### "):
            r.y += 8; r.text(s[4:].replace("**", ""), SZ_H3, FN_HEI); r.y += 4; i += 1; continue
        if s.startswith("#### "):
            r.y += 6; r.text(s[5:].replace("**", ""), SZ_H4, FN_HEI); r.y += 2; i += 1; continue

        # 引用块（清除markdown标记）
        if s.startswith("> "):
            r.wrapped(s[2:].replace("**", ""), SZ_BODY - 1, FN_SONG, indent=24); i += 1; continue

        # 表格（简化处理）
        if s.startswith("|"):
            cells = [c.strip() for c in s.split("|")[1:-1]]
            if cells and not all(re.match(r'^[-:\s]+$', c) for c in cells):
                r.wrapped(" | ".join(c.replace("**", "") for c in cells), SZ_BODY - 1, FN_SONG)
            i += 1; continue

        # 有序列表（清除markdown标记）
        m = re.match(r'^(\d+)[.．、]\s+(.+)', s)
        if m:
            content = m.group(2).replace("**", "")
            r.wrapped(f"{m.group(1)}. {content}", SZ_BODY, FN_SONG, indent=20)
            i += 1; continue

        # 无序列表（清除markdown标记）
        if re.match(r'^[-•]\s', s):
            content = re.sub(r'^[-•]\s+', '', s).replace("**", "")
            r.wrapped(f"• {content}", SZ_BODY, FN_SONG, indent=20)
            i += 1; continue

        # 普通段落（清除markdown标记）
        r.wrapped(s.replace("**", ""), SZ_BODY, FN_SONG)
        i += 1

    doc.save(pdf_path, garbage=4)
    doc.close()
    print(f"✅ {pdf_path} ({os.path.getsize(pdf_path)/1024:.0f}KB)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 md2pdf.py <input.md> [output.pdf]", file=sys.stderr)
        sys.exit(1)
    md_path = sys.argv[1]
    pdf_path = sys.argv[2] if len(sys.argv) > 2 else md_path.replace(".md", ".pdf")
    convert(md_path, pdf_path)
