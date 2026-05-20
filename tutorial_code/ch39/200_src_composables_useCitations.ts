import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import type { Citation } from '@/types/api'

/**
 * 把 citations 数组转换成响应式 Map,方便按编号查找。
 *
 * 用法:
 *   const { citationMap } = useCitations(() => props.metadata?.citations ?? [])
 *   citationMap.value.get(3)        // → Citation | undefined
 */
export function useCitations(
  source: MaybeRefOrGetter<Citation[]>
) {
  const citationMap = computed(() => {
    const list = toValue(source)
    return new Map(list.map(c => [c.number, c]))
  })

  // 也提供 sorted 列表(按 number 排序),给 UI 用
  const sortedCitations = computed(() => {
    const list = toValue(source)
    return [...list].sort((a, b) => a.number - b.number)
  })

  return {
    citationMap,
    sortedCitations,
  }
}