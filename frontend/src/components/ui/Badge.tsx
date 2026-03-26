import { type HTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

export type BadgeVariant = 'default' | 'primary' | 'accent' | 'success' | 'warning' | 'danger' | 'outline' | 'secondary'

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  variant?: BadgeVariant
  size?: 'sm' | 'md'
  dot?: boolean
  pulse?: boolean
}

const variants: Record<BadgeVariant, string> = {
  default: 'bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]',
  primary: 'bg-[hsl(var(--primary)/0.15)] text-[hsl(var(--primary))] border border-[hsl(var(--primary)/0.3)]',
  accent: 'bg-[hsl(var(--accent)/0.15)] text-[hsl(var(--accent))] border border-[hsl(var(--accent)/0.3)]',
  success: 'bg-[hsl(var(--success)/0.15)] text-[hsl(var(--success))] border border-[hsl(var(--success)/0.3)]',
  warning: 'bg-[hsl(var(--warning)/0.15)] text-[hsl(var(--warning))] border border-[hsl(var(--warning)/0.3)]',
  danger: 'bg-[hsl(var(--destructive)/0.15)] text-[hsl(var(--destructive))] border border-[hsl(var(--destructive)/0.3)]',
  outline: 'bg-transparent border border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))]',
  secondary: 'bg-[hsl(var(--secondary))] text-[hsl(var(--secondary-foreground))] border border-[hsl(var(--border))]',
}

const sizes = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-3 py-1 text-sm',
}

export function Badge({
  className,
  variant = 'default',
  size = 'md',
  dot = false,
  pulse = false,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 font-medium rounded-full whitespace-nowrap',
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {dot && (
        <span className="relative flex h-2 w-2">
          {pulse && (
            <span className={cn(
              'animate-ping absolute inline-flex h-full w-full rounded-full opacity-75',
              variant === 'success' && 'bg-[hsl(var(--success))]',
              variant === 'warning' && 'bg-[hsl(var(--warning))]',
              variant === 'danger' && 'bg-[hsl(var(--destructive))]',
              variant === 'primary' && 'bg-[hsl(var(--primary))]',
              variant === 'accent' && 'bg-[hsl(var(--accent))]',
              (variant === 'default' || variant === 'outline') && 'bg-[hsl(var(--muted-foreground))]'
            )} />
          )}
          <span className={cn(
            'relative inline-flex rounded-full h-2 w-2',
            variant === 'success' && 'bg-[hsl(var(--success))]',
            variant === 'warning' && 'bg-[hsl(var(--warning))]',
            variant === 'danger' && 'bg-[hsl(var(--destructive))]',
            variant === 'primary' && 'bg-[hsl(var(--primary))]',
            variant === 'accent' && 'bg-[hsl(var(--accent))]',
            (variant === 'default' || variant === 'outline') && 'bg-[hsl(var(--muted-foreground))]'
          )} />
        </span>
      )}
      {children}
    </span>
  )
}
