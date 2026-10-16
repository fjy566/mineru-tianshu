// Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
/** Markdown 渲染与视图状态、鉴权链接分离。 */
import { Marked } from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import katex from 'katex'

const parser = new Marked({ breaks: true, gfm: true })
parser.use({
  renderer: {
    code({ text, lang }) {
      const language = lang && hljs.getLanguage(lang) ? lang : undefined
      const highlighted = language ? hljs.highlight(text, { language }).value : hljs.highlightAuto(text).value
      return `<pre><code class="hljs">${highlighted}</code></pre>`
    }
  }
})


export function renderMarkdown(content: string): string {
  if (!content) return ''
  let html = parser.parse(content, { async: false })

  // 先渲染块级公式 $$...$$ (支持多行)
  html = html.replace(/\$\$([\s\S]+?)\$\$/g, (match, formula) => {
    try {
      return katex.renderToString(formula.trim(), {
        throwOnError: false,
        displayMode: true
      })
    } catch (e) {
      console.error('KaTeX block error:', e)
      return match
    }
  })

  // 再渲染行内公式 $...$
  html = html.replace(/\$([^\$\n]+?)\$/g, (match, formula) => {
    try {
      return katex.renderToString(formula, {
        throwOnError: false,
        displayMode: false
      })
    } catch (e) {
      console.error('KaTeX inline error:', e)
      return match
    }
  })

  // 处理 \[...\] 和 \(...\) 格式
  html = html.replace(/\\\[([\s\S]+?)\\\]/g, (match, formula) => {
    try {
      return katex.renderToString(formula.trim(), {
        throwOnError: false,
        displayMode: true
      })
    } catch (e) {
      return match
    }
  })

  html = html.replace(/\\\(([^\)]+?)\\\)/g, (match, formula) => {
    try {
      return katex.renderToString(formula, {
        throwOnError: false,
        displayMode: false
      })
    } catch (e) {
      return match
    }
  })

  // 文档中的 HTML 属于不可信输入，保留表格与公式，移除脚本、事件和危险链接。
  return DOMPurify.sanitize(html, { ADD_ATTR: ['target'] })
}
