// 1. 直接传值(不响应)
useCitations(allCitations)

// 2. 传 ref(响应)
const citations = ref<Citation[]>([])
useCitations(citations)

// 3. 传 getter(响应,适合从 props 拿)
useCitations(() => props.metadata?.citations ?? [])