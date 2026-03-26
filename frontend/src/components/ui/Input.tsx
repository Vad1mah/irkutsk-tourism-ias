import { forwardRef, useId, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes, type ReactNode } from 'react'
import { cn } from '../../lib/cn'

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string
  error?: string
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  function Input({ className, label, error, leftIcon, rightIcon, id: propId, ...props }, ref) {
    const autoId = useId()
    const id = propId || autoId
    return (
      <div className="space-y-2">
        {label && (
          <label htmlFor={id} className="block text-sm font-medium text-[hsl(var(--muted-foreground))]">
            {label}
          </label>
        )}
        <div className="relative">
          {leftIcon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground))]">
              {leftIcon}
            </div>
          )}
          <input
            ref={ref}
            id={id}
            className={cn(
              'w-full bg-[hsl(var(--input))] border border-[hsl(var(--border))]',
              'rounded-xl px-4 py-3 text-[hsl(var(--foreground))]',
              'placeholder:text-[hsl(var(--muted-foreground))]',
              'transition-all duration-200',
              'focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))] focus:border-transparent',
              'hover:border-[hsl(var(--muted-foreground))]',
              leftIcon ? 'pl-10' : '',
              rightIcon ? 'pr-10' : '',
              error && 'border-[hsl(var(--destructive))] focus:ring-[hsl(var(--destructive))]',
              className
            )}
            {...props}
          />
          {rightIcon && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground))]">
              {rightIcon}
            </div>
          )}
        </div>
        {error && (
          <p className="text-sm text-[hsl(var(--destructive))]">{error}</p>
        )}
      </div>
    )
  }
)

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: string
  error?: string
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea({ className, label, error, id: propId, ...props }, ref) {
    const autoId = useId()
    const id = propId || autoId
    return (
      <div className="space-y-2">
        {label && (
          <label htmlFor={id} className="block text-sm font-medium text-[hsl(var(--muted-foreground))]">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={id}
          className={cn(
            'w-full bg-[hsl(var(--input))] border border-[hsl(var(--border))]',
            'rounded-xl px-4 py-3 text-[hsl(var(--foreground))]',
            'placeholder:text-[hsl(var(--muted-foreground))]',
            'transition-all duration-200 resize-none',
            'focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))] focus:border-transparent',
            'hover:border-[hsl(var(--muted-foreground))]',
            error && 'border-[hsl(var(--destructive))] focus:ring-[hsl(var(--destructive))]',
            className
          )}
          {...props}
        />
        {error && (
          <p className="text-sm text-[hsl(var(--destructive))]">{error}</p>
        )}
      </div>
    )
  }
)

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string
  error?: string
  options: { value: string; label: string }[]
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  function Select({ className, label, error, options, id: propId, ...props }, ref) {
    const autoId = useId()
    const id = propId || autoId
    return (
      <div className="space-y-2">
        {label && (
          <label htmlFor={id} className="block text-sm font-medium text-[hsl(var(--muted-foreground))]">
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={id}
          className={cn(
            'w-full bg-[hsl(var(--input))] border border-[hsl(var(--border))]',
            'rounded-xl px-4 py-3 text-[hsl(var(--foreground))]',
            'transition-all duration-200 cursor-pointer',
            'focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))] focus:border-transparent',
            'hover:border-[hsl(var(--muted-foreground))]',
            error && 'border-[hsl(var(--destructive))] focus:ring-[hsl(var(--destructive))]',
            className
          )}
          {...props}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {error && (
          <p className="text-sm text-[hsl(var(--destructive))]">{error}</p>
        )}
      </div>
    )
  }
)
