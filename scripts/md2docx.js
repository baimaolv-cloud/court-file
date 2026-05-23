#!/usr/bin/env node
/**
 * md2docx.js — 将中文法律文书 Markdown 转为 Word (.docx)
 * 用法: node md2docx.js <input.md> [output.docx]
 *
 * 特性：
 * - 中文字体：宋体(正文) + 黑体(标题)
 * - 西文字体：Times New Roman
 * - A4 页面，1英寸边距
 * - 支持表格、有序/无序列表、引用块
 * - 表格首行浅蓝底色
 */
const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, HeadingLevel,
        AlignmentType, BorderStyle, WidthType, ShadingType, VerticalAlign,
        LevelFormat } = require('docx');

const FONT_BODY = { ascii: 'Times New Roman', eastAsia: '宋体', hAnsi: 'Times New Roman', cs: 'Times New Roman' };
const FONT_HEAD = { ascii: 'Times New Roman', eastAsia: '黑体', hAnsi: 'Times New Roman', cs: 'Times New Roman' };

function mkRun(text, opts = {}) {
  return new TextRun({
    text,
    bold: opts.bold || false,
    italics: opts.italic || false,
    font: opts.font || FONT_BODY,
    size: opts.size || 24,
    color: opts.color
  });
}

function parseInline(text, defaultOpts = {}) {
  const runs = [];
  let i = 0, buf = '', bold = false;
  while (i < text.length) {
    if (text[i] === '*' && text[i + 1] === '*') {
      if (buf) { runs.push(mkRun(buf, { ...defaultOpts, bold })); buf = ''; }
      bold = !bold; i += 2;
    } else { buf += text[i]; i++; }
  }
  if (buf) runs.push(mkRun(buf, { ...defaultOpts, bold }));
  return runs.length ? runs : [mkRun(text, defaultOpts)];
}

function mkPara(runs, opts = {}) {
  const p = { children: runs };
  if (opts.heading) p.heading = opts.heading;
  if (opts.align) p.alignment = opts.align;
  if (opts.spacing) p.spacing = opts.spacing;
  if (opts.indent) p.indent = opts.indent;
  if (opts.border) p.border = opts.border;
  if (opts.numbering) p.numbering = opts.numbering;
  return new Paragraph(p);
}

function makeTable(rows, aligns) {
  if (!rows.length) return mkPara([mkRun('')]);
  const cols = rows[0].length;
  const totalW = 9360;
  const colW = Math.floor(totalW / cols);
  const brd = { style: BorderStyle.SINGLE, size: 1, color: '999999' };
  const borders = { top: brd, bottom: brd, left: brd, right: brd };
  return new Table({
    width: { size: totalW, type: WidthType.DXA },
    rows: rows.map((cells, ri) => new TableRow({
      children: cells.map((c, ci) => new TableCell({
        children: [mkPara(parseInline(c), { align: aligns[ci] || AlignmentType.LEFT, spacing: { before: 40, after: 40 } })],
        borders,
        width: { size: colW, type: WidthType.DXA },
        verticalAlign: VerticalAlign.CENTER,
        shading: ri === 0 ? { fill: 'E8F0FE', type: ShadingType.CLEAR } : undefined,
      }))
    }))
  });
}

function convert(md) {
  const lines = md.split('\n');
  const out = [];
  let i = 0, tableBuf = [], tableAlign = [];

  function flushTable() {
    if (tableBuf.length) { out.push(makeTable(tableBuf, tableAlign)); tableBuf = []; tableAlign = []; }
  }

  while (i < lines.length) {
    const t = lines[i].trim();
    if (t === '---') { flushTable(); i++; continue; }

    const hm = t.match(/^(#{1,4})\s+(.+)/);
    if (hm) {
      flushTable();
      const lv = hm[1].length, title = hm[2];
      const headMap = { 1: HeadingLevel.HEADING_1, 2: HeadingLevel.HEADING_2, 3: HeadingLevel.HEADING_3, 4: HeadingLevel.HEADING_4 };
      const sizeMap = { 1: 36, 2: 30, 3: 28, 4: 26 };
      const spMap = { 1: { before: 480, after: 240 }, 2: { before: 360, after: 180 }, 3: { before: 240, after: 120 }, 4: { before: 180, after: 80 } };
      out.push(mkPara([mkRun(title, { bold: true, font: FONT_HEAD, size: sizeMap[lv] })], { heading: headMap[lv], align: lv === 1 ? AlignmentType.CENTER : undefined, spacing: spMap[lv] }));
      i++; continue;
    }

    if (t.startsWith('> ')) {
      flushTable();
      out.push(mkPara([mkRun(t.slice(2), { italic: true, size: 22, color: '444444' })], { indent: { left: 480 }, border: { left: { style: BorderStyle.SINGLE, size: 6, color: 'AAAAAA', space: 6 } } }));
      i++; continue;
    }

    if (t.startsWith('|')) {
      const cells = t.split('|').slice(1, -1).map(c => c.trim());
      if (cells.length === 0 || cells.every(c => /^[-:\s]+$/.test(c))) {
        tableAlign = cells.map(c => /^:-+:$/.test(c) ? AlignmentType.CENTER : /^-+:$/.test(c) ? AlignmentType.RIGHT : AlignmentType.LEFT);
      } else { tableBuf.push(cells); }
      i++;
      if (i >= lines.length || !lines[i].trim().startsWith('|')) flushTable();
      continue;
    }

    flushTable();
    if (t === '') { out.push(mkPara([mkRun('')])); i++; continue; }

    const numMatch = t.match(/^(\d+)[.．、]\s+(.+)/);
    if (numMatch) {
      out.push(mkPara(parseInline(numMatch[2]), { numbering: { reference: 'legal-num', level: 0 }, spacing: { before: 60, after: 60 } }));
      i++; continue;
    }

    if (/^[-•]\s/.test(t)) {
      out.push(mkPara(parseInline(t.replace(/^[-•]\s/, '')), { numbering: { reference: 'bullets', level: 0 }, spacing: { before: 60, after: 60 } }));
      i++; continue;
    }

    out.push(mkPara(parseInline(t), { spacing: { before: 60, after: 60 } }));
    i++;
  }
  flushTable();
  return out;
}

// === Main ===
const mdPath = process.argv[2];
const outPath = process.argv[3] || mdPath.replace(/\.md$/i, '.docx');

if (!mdPath) { console.error('Usage: node md2docx.js <input.md> [output.docx]'); process.exit(1); }

const md = fs.readFileSync(mdPath, 'utf8');
const children = convert(md);

const doc = new Document({
  styles: { default: { document: { run: { font: FONT_BODY, size: 24 } } } },
  numbering: {
    config: [
      { reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 840, hanging: 420 } } } }] },
      { reference: 'legal-num', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 840, hanging: 420 } } } }] }
    ]
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    children
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf);
  console.log(`✅ ${outPath}  (${(buf.length/1024).toFixed(0)}KB)`);
}).catch(e => { console.error(e); process.exit(1); });
