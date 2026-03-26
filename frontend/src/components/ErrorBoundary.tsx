import { Component, type ReactNode } from 'react'

type ErrorBoundaryProps = {
  children: ReactNode
  fallback?: ReactNode
}

type ErrorBoundaryState = {
  hasError: boolean
  error?: Error
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  override render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="min-h-screen flex items-center justify-center bg-[hsl(var(--background))]">
          <div className="text-center p-8">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-[hsl(var(--destructive)/0.1)] flex items-center justify-center">
              <span className="text-3xl">⚠️</span>
            </div>
            <h1 className="text-2xl font-bold text-[hsl(var(--destructive))] mb-2">
              Что-то пошло не так
            </h1>
            <p className="text-[hsl(var(--muted-foreground))] mb-6">
              Произошла ошибка при загрузке страницы
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-3 rounded-xl bg-gradient-to-r from-[hsl(var(--primary))] to-[hsl(var(--accent))] text-white font-medium hover:opacity-90 transition-opacity"
            >
              Перезагрузить страницу
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
