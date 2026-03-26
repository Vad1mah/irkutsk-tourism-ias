import { cn } from '../lib/cn'
import { TrendingUp, TrendingDown, Minus, Info, type LucideIcon } from 'lucide-react'

type InsightType = 'positive' | 'neutral' | 'negative' | 'info'

type Props = {
  type: InsightType
  title: string
  description: string
  metric?: string
  icon?: LucideIcon
  className?: string
}

const styles: Record<InsightType, { bg: string; border: string; iconColor: string; defaultIcon: LucideIcon }> = {
  positive: {
    bg: 'bg-[hsl(var(--success)/0.05)]',
    border: 'border-[hsl(var(--success)/0.2)]',
    iconColor: 'text-[hsl(var(--success))] bg-[hsl(var(--success)/0.1)]',
    defaultIcon: TrendingDown,
  },
  negative: {
    bg: 'bg-[hsl(var(--destructive)/0.05)]',
    border: 'border-[hsl(var(--destructive)/0.2)]',
    iconColor: 'text-[hsl(var(--destructive))] bg-[hsl(var(--destructive)/0.1)]',
    defaultIcon: TrendingUp,
  },
  neutral: {
    bg: 'bg-[hsl(var(--primary)/0.05)]',
    border: 'border-[hsl(var(--primary)/0.2)]',
    iconColor: 'text-[hsl(var(--primary))] bg-[hsl(var(--primary)/0.1)]',
    defaultIcon: Minus,
  },
  info: {
    bg: 'bg-[hsl(var(--primary)/0.05)]',
    border: 'border-[hsl(var(--primary)/0.2)]',
    iconColor: 'text-[hsl(var(--primary))] bg-[hsl(var(--primary)/0.1)]',
    defaultIcon: Info,
  },
}

export function InsightCard({ type, title, description, metric, icon, className }: Props) {
  const s = styles[type]
  const Icon = icon || s.defaultIcon

  return (
    <div className={cn(
      'flex items-start gap-3 p-4 rounded-xl border transition-colors',
      s.bg, s.border,
      className,
    )}>
      <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0', s.iconColor)}>
        <Icon size={18} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <p className="font-medium text-sm text-[hsl(var(--foreground))]">{title}</p>
          {metric && (
            <span className="text-sm font-semibold tabular-nums">{metric}</span>
          )}
        </div>
        <p className="text-xs text-[hsl(var(--muted-foreground))] mt-0.5 leading-relaxed">
          {description}
        </p>
      </div>
    </div>
  )
}
