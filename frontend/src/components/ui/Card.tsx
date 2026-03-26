import { type HTMLAttributes, forwardRef } from 'react'
import { cn } from '../../lib/cn'

type CardProps = HTMLAttributes<HTMLDivElement> & {
  variant?: 'default' | 'glass' | 'gradient' | 'glow'
  hover?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const variants = {
  default: 'bg-[hsl(var(--card))] border border-[hsl(var(--border))]',
  glass: 'glass',
  gradient: 'bg-gradient-to-br from-[hsl(var(--card))] to-[hsl(var(--secondary))] border border-[hsl(var(--border))]',
  glow: 'bg-[hsl(var(--card))] border border-[hsl(var(--border))] glow',
}

const paddings = {
  none: '',
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8',
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  function Card({ className, variant = 'default', hover = false, padding = 'md', children, ...props }, ref) {
    return (
      <div
        ref={ref}
        className={cn(
          'rounded-2xl',
          variants[variant],
          paddings[padding],
          hover && 'card-hover cursor-pointer',
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)

type CardHeaderProps = HTMLAttributes<HTMLDivElement>

export function CardHeader({ className, children, ...props }: CardHeaderProps) {
  return (
    <div className={cn('flex flex-col space-y-1.5', className)} {...props}>
      {children}
    </div>
  )
}

type CardTitleProps = HTMLAttributes<HTMLHeadingElement>

export function CardTitle({ className, children, ...props }: CardTitleProps) {
  return (
    <h3 className={cn('text-lg font-semibold leading-none tracking-tight', className)} {...props}>
      {children}
    </h3>
  )
}

type CardDescriptionProps = HTMLAttributes<HTMLParagraphElement>

export function CardDescription({ className, children, ...props }: CardDescriptionProps) {
  return (
    <p className={cn('text-sm text-[hsl(var(--muted-foreground))]', className)} {...props}>
      {children}
    </p>
  )
}

type CardContentProps = HTMLAttributes<HTMLDivElement>

export function CardContent({ className, children, ...props }: CardContentProps) {
  return (
    <div className={cn('', className)} {...props}>
      {children}
    </div>
  )
}

type CardFooterProps = HTMLAttributes<HTMLDivElement>

export function CardFooter({ className, children, ...props }: CardFooterProps) {
  return (
    <div className={cn('flex items-center pt-4', className)} {...props}>
      {children}
    </div>
  )
}
