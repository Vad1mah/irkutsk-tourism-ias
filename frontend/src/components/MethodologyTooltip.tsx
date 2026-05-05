import { Info } from 'lucide-react'
import { useState } from 'react'

type Props = {
  text: string
}

export function MethodologyTooltip({ text }: Props) {
  const [open, setOpen] = useState(false)
  return (
    <span
      className="relative inline-flex items-center"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <Info size={12} className="text-[hsl(var(--muted-foreground))] cursor-help" />
      {open && (
        <span
          className="absolute bottom-full left-0 mb-1 z-50 w-64 p-2 text-xs rounded-md
                     bg-[hsl(var(--card))] border border-[hsl(var(--border))]
                     text-[hsl(var(--foreground))] shadow-lg"
        >
          {text}
        </span>
      )}
    </span>
  )
}
