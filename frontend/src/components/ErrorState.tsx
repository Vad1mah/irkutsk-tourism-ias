import { AlertCircle, RefreshCw } from 'lucide-react'
import { Card, CardContent, Button } from './ui'

type Props = {
  title?: string
  message?: string
  onRetry?: () => void
}

export function ErrorState({
  title = 'Ошибка загрузки данных',
  message = 'Не удалось получить данные. Проверьте подключение к серверу.',
  onRetry,
}: Props) {
  return (
    <Card variant="glass" className="border-[hsl(var(--destructive)/0.3)]">
      <CardContent>
        <div className="flex flex-col items-center text-center py-8">
          <div className="w-14 h-14 rounded-2xl bg-[hsl(var(--destructive)/0.1)] flex items-center justify-center mb-4">
            <AlertCircle className="w-7 h-7 text-[hsl(var(--destructive))]" />
          </div>
          <h3 className="text-lg font-semibold mb-1">{title}</h3>
          <p className="text-sm text-[hsl(var(--muted-foreground))] max-w-md mb-4">{message}</p>
          {onRetry && (
            <Button variant="outline" size="sm" onClick={onRetry}>
              <RefreshCw size={14} />
              Повторить
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
