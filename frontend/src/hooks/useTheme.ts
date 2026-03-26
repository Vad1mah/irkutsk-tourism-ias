import { useState, useEffect, useCallback } from 'react'

type Theme = 'dark' | 'light'

const STORAGE_KEY = 'pribaikalie_theme'

function getInitialTheme(): Theme {
  try {
    const saved = localStorage.getItem(STORAGE_KEY) as Theme | null
    if (saved === 'dark' || saved === 'light') return saved
  } catch { /* ignore */ }
  return 'dark'
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme)

  useEffect(() => {
    const root = document.documentElement
    root.classList.remove('dark', 'light')
    root.classList.add(theme)
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  const toggle = useCallback(() => {
    setThemeState(prev => prev === 'dark' ? 'light' : 'dark')
  }, [])

  return { theme, toggle, isDark: theme === 'dark' } as const
}
