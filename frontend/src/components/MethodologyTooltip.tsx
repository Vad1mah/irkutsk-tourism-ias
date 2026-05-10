import { Info } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

type Props = {
  text: string
}

const TOOLTIP_W = 288
const VIEWPORT_MARGIN = 8

export function MethodologyTooltip({ text }: Props) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)
  const iconRef = useRef<HTMLSpanElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    if (!open || !iconRef.current) {
      setPos(null)
      return
    }
    const iconRect = iconRef.current.getBoundingClientRect()
    const tooltipH = tooltipRef.current?.offsetHeight ?? 0
    const ttHeight = tooltipH || 64

    let top = iconRect.top - ttHeight - 6
    if (top < VIEWPORT_MARGIN) top = iconRect.bottom + 6

    let left = iconRect.left
    if (left + TOOLTIP_W > window.innerWidth - VIEWPORT_MARGIN) {
      left = window.innerWidth - TOOLTIP_W - VIEWPORT_MARGIN
    }
    if (left < VIEWPORT_MARGIN) left = VIEWPORT_MARGIN

    setPos({ top, left })
  }, [open])

  useEffect(() => {
    if (!open) return
    const onScroll = () => setOpen(false)
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', onScroll)
    }
  }, [open])

  return (
    <span
      ref={iconRef}
      className="relative inline-flex items-center"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <Info size={12} className="text-[hsl(var(--muted-foreground))] cursor-help" />
      {open && pos && createPortal(
        <div
          ref={tooltipRef}
          style={{ top: pos.top, left: pos.left, width: TOOLTIP_W }}
          className="fixed z-[9999] p-2.5 text-xs rounded-md
                     bg-[hsl(var(--card))] border border-[hsl(var(--border))]
                     text-[hsl(var(--foreground))] shadow-xl whitespace-normal leading-relaxed
                     pointer-events-none"
        >
          {text}
        </div>,
        document.body,
      )}
    </span>
  )
}
