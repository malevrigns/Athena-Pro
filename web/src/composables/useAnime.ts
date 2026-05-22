import { onMounted, onUnmounted, nextTick, watch } from 'vue'
import anime from 'animejs'

function prefersReducedMotion() {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

/**
 * Run a staggered entrance animation against any selector once Vue has finished
 * rendering. Skips work when `prefers-reduced-motion` is set.
 */
export function useEntrance(selector: string, opts: anime.AnimeParams = {}) {
  const reduced = prefersReducedMotion()
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
  const reduced = prefersReducedMotion()
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

/**
 * Route-level anime.js motion system.
 *
 * This keeps every page interactive without copying animation code into every
 * view: page roots get a small entrance, and common clickable/scannable
 * controls get hover + press feedback. Page-specific animations can still use
 * `useEntrance` for denser sequences.
 */
export function useRouteMotion(routeKey: () => unknown, rootSelector = '.main-body') {
  if (prefersReducedMotion()) return

  const cleanups: Array<() => void> = []
  let runId = 0

  function clearBindings() {
    while (cleanups.length) cleanups.pop()?.()
  }

  function isDisabled(el: HTMLElement) {
    return el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true'
  }

  function bindInteractive(el: HTMLElement) {
    const onEnter = () => {
      if (isDisabled(el)) return
      anime.remove(el)
      anime({
        targets: el,
        translateY: -2,
        scale: 1.01,
        duration: 180,
        easing: 'easeOutQuad',
      })
    }
    const onLeave = () => {
      anime.remove(el)
      anime({
        targets: el,
        translateY: 0,
        scale: 1,
        duration: 220,
        easing: 'easeOutQuad',
      })
    }
    const onDown = () => {
      if (isDisabled(el)) return
      anime.remove(el)
      anime({ targets: el, scale: 0.985, duration: 90, easing: 'easeOutQuad' })
    }
    const onUp = () => {
      if (isDisabled(el)) return
      anime.remove(el)
      anime({ targets: el, scale: 1.01, duration: 140, easing: 'easeOutBack' })
    }

    el.addEventListener('mouseenter', onEnter)
    el.addEventListener('mouseleave', onLeave)
    el.addEventListener('mousedown', onDown)
    el.addEventListener('mouseup', onUp)
    cleanups.push(() => {
      anime.remove(el)
      el.removeEventListener('mouseenter', onEnter)
      el.removeEventListener('mouseleave', onLeave)
      el.removeEventListener('mousedown', onDown)
      el.removeEventListener('mouseup', onUp)
    })
  }

  async function applyMotion() {
    const currentRun = ++runId
    clearBindings()
    await nextTick()
    if (currentRun !== runId) return

    const root = document.querySelector<HTMLElement>(rootSelector)
    if (!root) return

    const pageRoot = root.firstElementChild as HTMLElement | null
    if (pageRoot) {
      anime.remove(pageRoot)
      anime({
        targets: pageRoot,
        opacity: [0, 1],
        translateY: [10, 0],
        duration: 360,
        easing: 'easeOutCubic',
      })
    }

    const pageInteractive = root.querySelectorAll<HTMLElement>([
      'button',
      'a',
      '.row-button',
      '.td-row',
      '.stage-item',
      '.trace-main',
      '.summary-item',
      '.hist-stat',
      '.kpi-card',
      '.cost-kpi-grid .card',
      '.coll-card',
      '.src-card',
    ].join(', '))
    const shellInteractive = document.querySelectorAll<HTMLElement>('.app-side .nav-item, .topbar button')
    ;[...pageInteractive, ...shellInteractive].forEach(bindInteractive)
  }

  onMounted(applyMotion)
  watch(routeKey, applyMotion, { flush: 'post' })
  onUnmounted(clearBindings)
}

export { anime }
