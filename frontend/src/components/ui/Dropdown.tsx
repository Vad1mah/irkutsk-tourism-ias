import { useState, useRef, useEffect, useCallback, type ReactNode } from 'react'
import { ChevronDown, Check } from 'lucide-react'
import { cn } from '../../lib/cn'

type DropdownOption = {
  value: string
  label: string
  hint?: string
}

type Props = {
  value: string
  onChange: (value: string) => void
  options: DropdownOption[]
  placeholder?: string
  icon?: ReactNode
  className?: string
  compact?: boolean
}

export function Dropdown({ value, onChange, options, placeholder, icon, className, compact }: Props) {
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const selected = options.find(o => o.value === value)

  useEffect(() => {
    if (!open) return
    function handle(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  useEffect(() => {
    if (open) {
      setHighlight(options.findIndex(o => o.value === value))
    }
  }, [open, options, value])

  useEffect(() => {
    if (!open || highlight < 0 || !listRef.current) return
    const el = listRef.current.children[highlight] as HTMLElement | undefined
    el?.scrollIntoView({ block: 'nearest' })
  }, [highlight, open])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'Escape':
        setOpen(false)
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        if (open && highlight >= 0) {
          onChange(options[highlight].value)
          setOpen(false)
        } else {
          setOpen(true)
        }
        break
      case 'ArrowDown':
        e.preventDefault()
        if (!open) { setOpen(true); break }
        setHighlight(i => Math.min(i + 1, options.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setHighlight(i => Math.max(i - 1, 0))
        break
    }
  }, [open, highlight, options, onChange])

  return (
    <div ref={containerRef} className={cn('relative', className)} onKeyDown={handleKeyDown}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className={cn(
          'flex items-center gap-2 w-full rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))]',
          'text-sm font-medium transition-all cursor-pointer text-[hsl(var(--foreground))]',
          'focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))]',
          'hover:border-[hsl(var(--muted-foreground)/0.5)]',
          compact ? 'px-3 py-2 pr-8' : 'px-4 py-3 pr-9',
          open && 'ring-2 ring-[hsl(var(--ring))]',
        )}
      >
        {icon && <span className="text-[hsl(var(--muted-foreground))] flex-shrink-0">{icon}</span>}
        <span className="flex-1 text-left truncate">
          {selected?.label ?? placeholder ?? 'Выберите...'}
        </span>
        <ChevronDown
          size={compact ? 14 : 16}
          className={cn(
            'absolute text-[hsl(var(--muted-foreground))] transition-transform duration-200',
            compact ? 'right-2.5' : 'right-3',
            open && 'rotate-180',
          )}
        />
      </button>

      {open && (
        <div
          ref={listRef}
          className={cn(
            'absolute z-50 mt-1.5 w-full min-w-[160px] rounded-xl',
            'border border-[hsl(var(--border))] bg-[hsl(var(--card))]',
            'shadow-xl shadow-black/30 py-1 max-h-64 overflow-y-auto',
          )}
          style={{ animation: 'fadeIn 0.15s ease-out' }}
        >
          {options.map((opt, i) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => { onChange(opt.value); setOpen(false) }}
              onMouseEnter={() => setHighlight(i)}
              className={cn(
                'flex items-center justify-between w-full px-3 text-sm transition-colors',
                compact ? 'py-1.5' : 'py-2',
                opt.value === value
                  ? 'bg-[hsl(var(--primary)/0.1)] text-[hsl(var(--primary))] font-medium'
                  : 'text-[hsl(var(--foreground))] hover:bg-[hsl(var(--secondary))]',
                i === highlight && opt.value !== value && 'bg-[hsl(var(--secondary))]',
              )}
            >
              <span className="truncate">
                {opt.label}
                {opt.hint && (
                  <span className="ml-1.5 text-xs text-[hsl(var(--muted-foreground))]">{opt.hint}</span>
                )}
              </span>
              {opt.value === value && <Check size={14} className="flex-shrink-0 ml-2" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
