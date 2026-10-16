<!-- Modified in fjy566/mineru-tianshu (2026-10-16); original project: magicyuan876/mineru-tianshu. -->
<template>
  <span :class="badgeClass" class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium">
    <span :class="dotClass" class="w-1.5 h-1.5 rounded-full mr-1.5"></span>
    {{ statusText }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { TaskStatus } from '@/api/types'

const { t } = useI18n()

const props = defineProps<{
  status: TaskStatus
}>()

const statusText = computed(() => {
  return t(`status.${props.status}`)
})

const badgeClass = computed(() => {
  const classMap: Record<TaskStatus, string> = {
    pending: 'bg-gray-100 text-gray-800',
    paused: 'bg-blue-100 text-blue-800',
    processing: 'bg-yellow-100 text-yellow-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    cancelled: 'bg-gray-100 text-gray-600',
  }
  return classMap[props.status] || 'bg-gray-100 text-gray-800'
})

const dotClass = computed(() => {
  const classMap: Record<TaskStatus, string> = {
    pending: 'bg-gray-400',
    paused: 'bg-blue-400',
    processing: 'bg-yellow-400 animate-pulse',
    completed: 'bg-green-500',
    failed: 'bg-red-500',
    cancelled: 'bg-gray-400',
  }
  return classMap[props.status] || 'bg-gray-400'
})
</script>
