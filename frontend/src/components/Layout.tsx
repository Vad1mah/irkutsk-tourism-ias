import { useState } from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import {
  Sparkles,
  Compass,
  Waves,
  ChevronRight,
  Map,
  PartyPopper,
  TrendingUp,
  LayoutDashboard,
  Menu,
  X,
  Sun,
  Moon,
  Info,
} from 'lucide-react'
import { Badge } from './ui'
import { useTheme } from '../hooks/useTheme'
import { api } from '../api/client'

const navItems = [
  { 
    to: '/', 
    icon: Compass, 
    label: 'Планирование',
    description: 'Спланируйте поездку'
  },
  { 
    to: '/analytics', 
    icon: LayoutDashboard, 
    label: 'Аналитика',
    description: 'Мониторинг и данные'
  },
  { 
    to: '/events', 
    icon: PartyPopper, 
    label: 'События',
    description: 'Календарь мероприятий'
  },
  { 
    to: '/map', 
    icon: Map, 
    label: 'Регионы',
    description: 'Карта и аналитика районов'
  },
  {
    to: '/forecast',
    icon: TrendingUp,
    label: 'Прогнозы',
    description: 'Прогноз загрузки и тренды',
    badge: 'ML'
  },
  { 
    to: '/chat', 
    icon: Sparkles, 
    label: 'AI-помощник',
    description: 'Задайте вопрос',
    badge: 'AI'
  },
  { 
    to: '/about', 
    icon: Info, 
    label: 'О системе',
    description: 'О системе и источниках данных'
  },
]

function Layout() {
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { toggle: toggleTheme, isDark } = useTheme()
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: 60_000,
    staleTime: 30_000,
  })
  
  return (
    <div className="min-h-screen flex bg-[hsl(var(--background))]">
      {/* Mobile header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 h-14 flex items-center px-4 border-b border-[hsl(var(--border))] bg-[hsl(var(--card))]">
        <button onClick={() => setSidebarOpen(true)} aria-label="Открыть меню" className="p-2 -ml-2 rounded-lg hover:bg-[hsl(var(--secondary))]">
          <Menu size={20} />
        </button>
        <div className="flex items-center gap-2 ml-3">
          <Waves className="w-5 h-5 text-[hsl(var(--primary))]" />
          <span className="font-bold gradient-text">Прибайкалье</span>
        </div>
      </div>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed lg:static inset-y-0 left-0 z-50 w-64 2xl:w-72 flex flex-col border-r border-[hsl(var(--border))] bg-gradient-to-b from-[hsl(var(--card))] to-[hsl(var(--background))] flex-shrink-0
        transition-transform duration-300 lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Logo */}
        <div className="p-6 border-b border-[hsl(var(--border))]">
          <div className="flex items-center gap-3">
            <button className="lg:hidden p-1 rounded-lg hover:bg-[hsl(var(--secondary))]" onClick={() => setSidebarOpen(false)} aria-label="Закрыть меню">
              <X size={18} />
            </button>
            <div className="relative">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))] flex items-center justify-center">
                <Waves className="w-5 h-5 text-white" />
              </div>
              <div className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-[hsl(var(--accent))] animate-pulse" />
            </div>
            <div>
              <h1 className="font-bold text-lg gradient-text">
                Прибайкалье
              </h1>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                Туристическая аналитика
              </p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-2">
          <p className="text-xs font-medium text-[hsl(var(--muted-foreground))] uppercase tracking-wider px-3 mb-4">
            Навигация
          </p>
          {navItems.map(({ to, icon: Icon, label, description, badge }) => {
            const isActive = location.pathname === to
            return (
              <NavLink
                key={to}
                to={to}
                onClick={() => setSidebarOpen(false)}
                className={`
                  group flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-300
                  ${isActive 
                    ? 'bg-gradient-to-r from-[hsl(var(--primary)/0.15)] to-[hsl(var(--accent)/0.1)] border border-[hsl(var(--primary)/0.3)]' 
                    : 'hover:bg-[hsl(var(--secondary))] border border-transparent'
                  }
                `}
              >
                <div className={`
                  w-9 h-9 rounded-lg flex items-center justify-center transition-all duration-300
                  ${isActive 
                    ? 'bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))] text-white shadow-lg shadow-[hsl(var(--primary)/0.3)]' 
                    : 'bg-[hsl(var(--secondary))] text-[hsl(var(--muted-foreground))] group-hover:text-[hsl(var(--foreground))]'
                  }
                `}>
                  <Icon size={18} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`font-medium text-sm ${isActive ? 'text-[hsl(var(--foreground))]' : 'text-[hsl(var(--muted-foreground))] group-hover:text-[hsl(var(--foreground))]'}`}>
                      {label}
                    </span>
                    {badge && (
                      <Badge variant="accent" size="sm">
                        <Sparkles size={10} />
                        {badge}
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] truncate">
                    {description}
                  </p>
                </div>
                <ChevronRight 
                  size={16} 
                  className={`
                    transition-all duration-300
                    ${isActive 
                      ? 'text-[hsl(var(--primary))] opacity-100' 
                      : 'text-[hsl(var(--muted-foreground))] opacity-0 group-hover:opacity-100'
                    }
                  `} 
                />
              </NavLink>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-[hsl(var(--border))] space-y-3">
          <div className="flex items-center gap-2">
            <div className="glass rounded-xl p-3 flex-1">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${health?.db_connected ? 'bg-[hsl(var(--success))] animate-pulse' : 'bg-[hsl(var(--destructive))]'}`} />
                <p className="text-xs text-[hsl(var(--muted-foreground))]">
                  {health?.db_connected ? 'Система активна' : 'Нет связи'}
                </p>
              </div>
            </div>
            <button
              onClick={toggleTheme}
              className="w-10 h-10 rounded-xl flex items-center justify-center bg-[hsl(var(--secondary))] hover:bg-[hsl(var(--secondary)/0.8)] transition-colors"
              aria-label={isDark ? 'Включить светлую тему' : 'Включить тёмную тему'}
            >
              {isDark ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </div>
          <p className="text-[10px] text-center text-[hsl(var(--muted-foreground))] mb-1">
            Ищите отели через AI-помощника
          </p>
          <NavLink
            to="/about"
            className="block text-xs text-center text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--primary))] transition-colors"
          >
            О системе · ИГУ © 2026
          </NavLink>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-h-screen overflow-hidden">
        <div className="flex-1 overflow-y-auto pt-14 lg:pt-0">
          <div className="p-4 lg:p-6 xl:p-8">
            <Outlet />
          </div>
        </div>
      </main>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: 'hsl(var(--card))',
            color: 'hsl(var(--foreground))',
            border: '1px solid hsl(var(--border))',
          },
          error: {
            style: {
              background: 'hsl(var(--destructive)/0.1)',
              border: '1px solid hsl(var(--destructive)/0.3)',
            },
          },
        }}
      />
    </div>
  )
}

export default Layout
