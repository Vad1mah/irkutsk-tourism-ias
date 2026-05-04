import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { cn } from '../../lib/cn'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'outline' | 'danger'
type ButtonSize = 'sm' | 'md' | 'lg' | 'icon'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: ButtonSize
  isLoading?: boolean
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

const variants: Record<ButtonVariant, string> = {
  primary: `
    bg-gradient-to-r from-[hsl(var(--primary))] to-[hsl(var(--accent))]
    text-[hsl(var(--primary-foreground))] font-semibold
    hover:shadow-lg hover:shadow-[hsl(var(--primary)/0.3)]
    active:scale-[0.98]
  `,
  secondary: `
    bg-[hsl(var(--secondary))] text-[hsl(var(--secondary-foreground))]
    hover:bg-[hsl(var(--secondary))]/80
    border border-[hsl(var(--border))]
  `,
  ghost: `
    bg-transparent text-[hsl(var(--muted-foreground))]
    hover:bg-[hsl(var(--secondary))] hover:text-[hsl(var(--foreground))]
  `,
  outline: `
    bg-transparent border border-[hsl(var(--primary))]
    text-[hsl(var(--primary))]
    hover:bg-[hsl(var(--primary)/0.1)]
  `,
  danger: `
    bg-[hsl(var(--destructive))] text-[hsl(var(--destructive-foreground))]
    hover:bg-[hsl(var(--destructive))]/90
  `,
}

const sizes: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-sm rounded-lg',
  md: 'px-5 py-2.5 text-sm rounded-xl',
  lg: 'px-6 py-3 text-base rounded-xl',
  icon: 'p-2.5 rounded-xl',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      className,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      leftIcon,
      rightIcon,
      disabled,
      children,
      ...props
    },
    ref
  ) {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          'inline-flex items-center justify-center gap-2',
          'font-medium transition-all duration-200',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))] focus-visible:ring-offset-2 focus-visible:ring-offset-[hsl(var(--background))]',
          'disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none',
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      >
        {isLoading ? (
          <svg
            className="animate-spin h-4 w-4"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        ) : (
          leftIcon
        )}
        {!isLoading && children}
        {!isLoading && rightIcon}
      </button>
    )
  }
)
