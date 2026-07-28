/**
 * useCronToast — B1 方案（不改视觉，仅封装 artDialog 调用）
 *
 * 解耦 Vue 组件对 Wind.use('artDialog', …) 的直接依赖。
 * 内部优先调用 window.Wind + artDialog；不可用时降级到原生 confirm/alert。
 * 这样 Wind.js 不可用的环境（如单测、新页面）也能正常运行。
 */
export function useCronToast() {
  function confirm(msg, onOk) {
    if (window.Wind) {
      window.Wind.use('artDialog', function () {
        art.dialog({
          title: false,
          icon: 'question',
          content: msg,
          ok: function () { onOk(); return true },
          cancel: true,
        })
      })
    } else if (window.confirm(msg)) {
      onOk()
    }
  }

  function alert(msg, icon) {
    if (window.Wind) {
      window.Wind.use('artDialog', function () {
        art.dialog({ title: false, icon: icon || 'succeed', content: msg, ok: true })
      })
    } else {
      window.alert(msg)
    }
  }

  return { confirm, alert }
}
