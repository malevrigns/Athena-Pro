import { onMounted, onUnmounted, nextTick } from 'vue'
import anime from 'animejs'

/**
 * Run a staggered entrance animation against any selector once Vue has finished
 * rendering. Skips work when `prefers-reduced-motion` is set.
 */
export function useEntrance(selector: string, opts: anime.AnimeParams = {}) {
  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  if (reduced) return
  onMounted(async () => {
    await nextTick()
    const targets = document.querySelectorAll(selector)
    if (!targets.length) return
    anime({
      targets,
      opacity: [0, 1],
      translateY: [16, 0],
      delay: anime.stagger(60),
      duration: 520,
      easing: 'easeOutCubic',
      ...opts,
    })
  })
}

/**
 * Count-up: walk every element matched by `selector` and roll its numeric
 * `data-value` attribute from 0 → target using easeOutExpo.
 *
 * Supports `data-precision`, `data-prefix`, `data-suffix` on each element.
 */
export function runCountUp(selector = '.count-up') {
  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  document.querySelectorAll<HTMLElement>(selector).forEach((el) => {
    const target = Number(el.dataset.value ?? '0')
    const precision = Number(el.dataset.precision ?? '0')
    const prefix = el.dataset.prefix ?? ''
    const suffix = el.dataset.suffix ?? ''
    if (reduced) {
      el.textContent = `${prefix}${target.toFixed(precision)}${suffix}`
      return
    }
    const obj = { v: 0 }
    anime({
      targets: obj,
      v: target,
      duration: 1300,
      easing: 'easeOutExpo',
      update: () => {
        el.textContent = `${prefix}${obj.v.toFixed(precision)}${suffix}`
      },
    })
  })
}

/**
 * Apply a subtle 3D tilt to an element based on the cursor position. Use in
 * `@mousemove` handlers. Reset with `resetTilt` on `@mouseleave`.
 */
export function tilt(e: MouseEvent, el: HTMLElement, depth = 8) {
  const r = el.getBoundingClientRect()
  const dx = (e.clientX - r.left) / r.width - 0.5
  const dy = (e.clientY - r.top) / r.height - 0.5
  anime({
    targets: el,
    rotateX: -dy * depth,
    rotateY: dx * depth,
    translateZ: 4,
    duration: 220,
    easing: 'easeOutQuad',
  })
}
export function resetTilt(el: HTMLElement) {
  anime({ targets: el, rotateX: 0, rotateY: 0, translateZ: 0, duration: 360, easing: 'easeOutQuad' })
}

/**
 * Quick "pop" animation often used for click feedback (e.g. tag/button press).
 */
export function pop(el: HTMLElement | null) {
  if (!el) return
  anime({
    targets: el,
    scale: [{ value: .94, duration: 120 }, { value: 1, duration: 260, easing: 'easeOutBack' }],
  })
}

/**
 * Animated ripple emanating from a click point, useful on accent buttons.
 */
export function ripple(e: MouseEvent) {
  const host = e.currentTarget as HTMLElement
  const rect = host.getBoundingClientRect()
  const r = document.createElement('span')
  r.className = 'anim-ripple'
  r.style.left = `${e.clientX - rect.left}px`
  r.style.top  = `${e.clientY - rect.top}px`
  host.appendChild(r)
  anime({
    targets: r,
    scale: [0, 4],
    opacity: [0.35, 0],
    duration: 600,
    easing: 'easeOutQuad',
    complete: () => r.remove(),
  })
}

/**
 * Float-in a stack of cards in a fixed root. Call from `onMounted` after data
 * is loaded so the DOM exists.
 */
export function floatInGroup(els: HTMLElement[] | NodeListOf<HTMLElement>, opts: anime.AnimeParams = {}) {
  if (!els || (Array.isArray(els) && els.length === 0)) return
  anime({
    targets: els as any,
    opacity: [0, 1],
    translateY: [18, 0],
    delay: anime.stagger(70),
    duration: 500,
    easing: 'easeOutQuart',
    ...opts,
  })
}

export { anime }
