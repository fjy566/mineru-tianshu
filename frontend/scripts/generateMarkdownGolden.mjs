// Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
// 从重构前的受跟踪组件生成固定 HTML 基线，避免用新实现生成自己的预期值。
import { execFileSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { marked } from 'marked'
import createDOMPurify from 'dompurify'
import hljs from 'highlight.js'
import katex from 'katex'
import { JSDOM } from 'jsdom'

const baseline = process.argv[2]
if (!baseline) throw new Error('Usage: node scripts/generateMarkdownGolden.mjs <baseline-commit>')
const source = execFileSync('git', ['show', `${baseline}:frontend/src/components/MarkdownViewer.vue`], { encoding: 'utf8' })
const config = source.slice(source.indexOf('marked.setOptions'), source.indexOf('const renderedContent = computed'))
const body = source.slice(source.indexOf('    let html = marked.parse'), source.indexOf('    return withAuthToken(DOMPurify.sanitize'))
  .replaceAll('props.content', 'content')
const legacy = new Function('marked', 'DOMPurify', 'hljs', 'katex', 'content',
  `${config}\n${body}\nreturn DOMPurify.sanitize(html, { ADD_ATTR: ['target'] })`)
const purifier = createDOMPurify(new JSDOM('').window)
const samples = [
  ['', 'empty'],
  ['# 中文标题\n\n完整段落\n换行。\n\n- [x] 已完成\n- 保留内容', 'text-lists'],
  ['| 项目 | 值 |\n|---|---|\n| 长度 | 12 mm |\n| 范围 | 3–8 |', 'table'],
  ['```python\ndef hello():\n    return "你好"\n```\n\n```unknown\nconst x = 42\n```', 'code'],
  ['$$x^2 + y^2 = z^2$$\n\n行内 $E=mc^2$。\n\n\\[\\frac{a}{b}\\]\n\n\\(x+y\\)', 'math'],
  ['<script>alert(1)</script><img src="/api/v1/files/output/x/a.png" onerror="alert(2)"><a href="javascript:alert(3)">链接</a>', 'unsafe-html'],
  ['![图片](/api/v1/files/output/test/a.png)\n\n[外部链接](https://example.com)\n\n> 引用 **文字**', 'links-images'],
  ['<table><tr><td>原生 HTML 表格</td></tr></table><details><summary>展开</summary>内容</details>', 'html'],
]
const cases = samples.map(([markdown, name]) => ({ name, markdown, html: legacy(marked, purifier, hljs, katex, markdown) }))
mkdirSync('tests/fixtures', { recursive: true })
writeFileSync('tests/fixtures/markdown-golden.json', JSON.stringify({ baseline, cases }, null, 2) + '\n')
console.log(`Generated ${cases.length} baseline cases from ${baseline}`)
