<!-- Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu. -->
<template>
  <div class="markdown-viewer prose prose-sm max-w-none">
    <div v-if="loading" class="text-center py-8">
      <LoadingSpinner :text="$t('common.loading')" />
    </div>
    <div v-else-if="error" class="text-center py-8 text-red-600">
      <p>{{ error }}</p>
    </div>
    <div v-else-if="!content" class="text-center py-8 text-gray-500">
      <p>{{ $t('common.noData') }}</p>
    </div>
    <div v-else v-html="renderedContent" class="markdown-content"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from '@/utils/markdownRenderer'
import { useI18n } from 'vue-i18n'
import 'highlight.js/styles/github.css'
import 'katex/dist/katex.min.css'
import LoadingSpinner from './LoadingSpinner.vue'
import { useAuthStore } from '@/stores'

const authStore = useAuthStore()
const { t } = useI18n()

// 文件服务接口需要鉴权，<img> 无法携带请求头，为内部文件链接追加 token 查询参数
const withAuthToken = (html: string): string => {
  const token = authStore.token
  if (!token) return html
  return html.replace(
    /(<img\b[^>]*?\bsrc=")(\/api\/v1\/files\/[^"]*)(")/g,
    (_match, prefix, src, suffix) => {
      const sep = src.includes('?') ? '&' : '?'
      return `${prefix}${src}${sep}token=${encodeURIComponent(token)}${suffix}`
    }
  )
}

const props = defineProps<{
  content: string
  loading?: boolean
  error?: string
}>()

const renderedBase = computed(() => {
  try {
    return renderMarkdown(props.content)
  } catch (err) {
    console.error('Markdown parse error:', err)
    return `<p class="text-red-600">${t('markdownViewer.parseError')}</p>`
  }
})

const renderedContent = computed(() => withAuthToken(renderedBase.value))

</script>

<style scoped>
.markdown-viewer {
  width: 100%;
}

.markdown-content :deep(pre) {
  @apply bg-gray-800 text-gray-100 rounded-lg p-4 overflow-x-auto;
}

.markdown-content :deep(code) {
  @apply bg-gray-100 text-red-600 px-1 py-0.5 rounded text-sm;
}

.markdown-content :deep(pre code) {
  @apply bg-transparent text-gray-100 p-0;
}

.markdown-content :deep(img) {
  @apply max-w-full h-auto rounded-lg shadow-md;
}

.markdown-content :deep(table) {
  @apply w-full border-collapse;
}

.markdown-content :deep(th) {
  @apply bg-gray-100 border border-gray-300 px-4 py-2 text-left;
}

.markdown-content :deep(td) {
  @apply border border-gray-300 px-4 py-2;
}

.markdown-content :deep(blockquote) {
  @apply border-l-4 border-gray-300 pl-4 italic text-gray-700;
}

.markdown-content :deep(a) {
  @apply text-primary-600 hover:underline;
}

/* KaTeX 公式样式 */
.markdown-content :deep(.katex) {
  font-size: 1.1em;
}

.markdown-content :deep(.katex-display) {
  @apply my-4 overflow-x-auto;
}

.markdown-content :deep(h1) {
  @apply text-2xl font-bold mt-6 mb-4;
}

.markdown-content :deep(h2) {
  @apply text-xl font-bold mt-5 mb-3;
}

.markdown-content :deep(h3) {
  @apply text-lg font-bold mt-4 mb-2;
}
</style>
