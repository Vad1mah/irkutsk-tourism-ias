import { cn } from '../lib/cn'

type Props = {
  value: number
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  className?: string
}

function _getLevel(value: number) {
  if (value < 40) return { label: 'Свободно', color: 'text-[hsl(var(--success))]', bg: 'bg-[hsl(var(--success))]', ring: 'ring-[hsl(var(--success)/0.3)]' }
  if (value < 70) return { label: 'Умеренно', color: 'text-[hsl(var(--warning))]', bg: 'bg-[hsl(var(--warning))]', ring: 'ring-[hsl(var(--warning)/0.3)]' }
  return { label: 'Загружено', color: 'text-[hsl(var(--destructive))]', bg: 'bg-[hsl(var(--destructive))]', ring: 'ring-[hsl(var(--destructive)/0.3)]' }
}

const sizes = {
  sm: { dot: 'w-2.5 h-2.5', text: 'text-xs', ring: 'ring-2' },
  md: { dot: 'w-3.5 h-3.5', text: 'text-sm', ring: 'ring-[3px]' },
  lg: { dot: 'w-5 h-5', text: 'text-base', ring: 'ring-4' },
}

export function OccupancyIndicator({ value, size = 'md', showLabel = true, className }: Props) {
  const level = _getLevel(value)
  const s = sizes[size]

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span className={cn('rounded-full', s.dot, s.ring, level.bg, level.ring)} />
      {showLabel && (
        <span className={cn(s.text, 'font-medium', level.color)}>
          {level.label}
        </span>
      )}
    </div>
  )
}
