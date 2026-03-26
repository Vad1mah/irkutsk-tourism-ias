/**
 * Экспорт DOM-элемента (графика) в PNG файл.
 * Работает через SVG → Canvas → Blob → download.
 */
export async function exportChartPng(
  container: HTMLElement,
  filename: string = 'chart.png',
): Promise<void> {
  const svg = container.querySelector('svg')
  if (!svg) return

  const clone = svg.cloneNode(true) as SVGElement
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')

  const { width, height } = svg.getBoundingClientRect()
  clone.setAttribute('width', String(width))
  clone.setAttribute('height', String(height))

  const styles = document.createElement('style')
  styles.textContent = `
    text { font-family: system-ui, -apple-system, sans-serif; }
  `
  clone.insertBefore(styles, clone.firstChild)

  const data = new XMLSerializer().serializeToString(clone)
  const blob = new Blob([data], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)

  const img = new Image()
  img.crossOrigin = 'anonymous'

  return new Promise((resolve) => {
    img.onload = () => {
      const scale = 2
      const canvas = document.createElement('canvas')
      canvas.width = width * scale
      canvas.height = height * scale

            const ctx = canvas.getContext('2d')!
            const isDark = document.documentElement.classList.contains('dark') ||
              !document.documentElement.classList.contains('light')
            ctx.fillStyle = isDark ? '#0d1117' : '#ffffff'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.scale(scale, scale)
      ctx.drawImage(img, 0, 0, width, height)

      canvas.toBlob((pngBlob) => {
        if (!pngBlob) { resolve(); return }
        const a = document.createElement('a')
        a.href = URL.createObjectURL(pngBlob)
        a.download = filename
        a.click()
        URL.revokeObjectURL(a.href)
        URL.revokeObjectURL(url)
        resolve()
      }, 'image/png')
    }
    img.onerror = () => { URL.revokeObjectURL(url); resolve() }
    img.src = url
  })
}
