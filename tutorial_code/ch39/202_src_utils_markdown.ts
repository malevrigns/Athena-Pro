import { marked } from 'marked'
import DOMPurify from 'dompurify'

// 配置 marked
marked.setOptions({
  gfm: true,
  breaks: false,
})

/**
 * 把 markdown 中的 [N] 标记预处理为带 data-citation 的 sup 标签,
 * 然后渲染为安全 HTML。
 */
export function renderMarkdownWithCitations(md: string): string {
  // 1. 把 [N] 转成 sup(在 marked 之前做,避免被 marked 当链接尝试解析)
  const preprocessed = md.replace(
    /\[(\d+)\]/g,
    '[$1]'
  )

  // 2. marked 渲染
  const rawHtml = marked.parse(preprocessed, { async: false }) as string

  // 3. DOMPurify 防 XSS,但允许 data-citation
  const safeHtml = DOMPurify.sanitize(rawHtml, {
    ADD_ATTR: ['data-citation', 'target'],
  })

  return safeHtml
}