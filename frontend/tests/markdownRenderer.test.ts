// Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu.
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { marked } from 'marked'
import baseline from './fixtures/markdown-golden.json'
import * as renderer from '../src/utils/markdownRenderer'
import MarkdownViewer from '../src/components/MarkdownViewer.vue'
import { useAuthStore } from '../src/stores/authStore'

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
  document.body.innerHTML = ''
})

describe('Markdown rendering equivalence', () => {
  for (const sample of baseline.cases) {
    it(`preserves baseline HTML: ${sample.name}`, () => {
      expect(renderer.renderMarkdown(sample.markdown)).toBe(sample.html)
    })
  }

  it('does not mutate the global marked renderer', () => {
    const before = marked.parse('```python\nx = 1\n```')
    renderer.renderMarkdown('```python\nx = 1\n```')
    expect(marked.parse('```python\nx = 1\n```')).toBe(before)
  })

  it('reuses sanitized HTML when only the image authentication token changes', async () => {
    const spy = vi.spyOn(renderer, 'renderMarkdown')
    const pinia = createPinia()
    setActivePinia(pinia)
    const auth = useAuthStore()
    auth.token = 'first-token'
    const host = document.createElement('div')
    document.body.append(host)
    const app = createApp(MarkdownViewer, { content: '![图片](/api/v1/files/output/test/a.png)' })
    app.use(pinia)
    app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': {} } }))
    try {
      app.mount(host)
      expect(spy).toHaveBeenCalledTimes(1)
      expect(host.querySelector('img')?.getAttribute('src')).toContain('token=first-token')
      auth.token = 'second-token'
      await nextTick()
      expect(host.querySelector('img')?.getAttribute('src')).toContain('token=second-token')
      expect(spy).toHaveBeenCalledTimes(1)
    } finally {
      app.unmount()
    }
  })
})
