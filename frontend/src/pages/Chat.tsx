import { useState, useRef, useEffect, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { usePageTitle } from '../hooks/usePageTitle'
import toast from 'react-hot-toast'
import {Send, Sparkles, User, Bot,
  TrendingUp, Building2, Calendar, MapPin,
  Copy, Check, ArrowRight, CloudSun, Trash2, RefreshCw, AlertCircle
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../api/client'
import { Card, Button, Badge } from '../components/ui'

const CHAT_STORAGE_KEY = 'pribaikalie_chat_history'
const SESSION_KEY = 'pribaikalie_session_id'

function getSessionId(): string {
  let id = localStorage.getItem(SESSION_KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(SESSION_KEY, id)
  }
  return id
}

type Message = {
  id: string
  role: 'user' | 'assistant'
  text: string
  sources?: string[]
  timestamp: string
  error?: boolean
}

function loadMessages(): Message[] {
  try {
    const saved = localStorage.getItem(CHAT_STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      return parsed as Message[]
    }
  } catch {
    // ignore
  }
  return []
}

function saveMessages(messages: Message[]) {
  try {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages.slice(-50)))
  } catch {
    // ignore
  }
}

const TOOL_LABELS: Record<string, string> = {
  search_hotels: 'Реестр объектов размещения',
  search_events: 'События как фактор спроса',
  get_weather: 'Погода как внешний фактор',
  forecast_occupancy: 'Прогноз загрузки',
  get_statistics: 'KPI рынка',
  get_revenue_metrics: 'RMS-метрики (RevPAR/ADR)',
}

const QUICK_QUESTIONS = [
  { icon: TrendingUp, text: 'Рассчитай RevPAR на майские праздники по Иркутскому району и сравни с прошлой неделей', short: 'RevPAR на майские' },
  { icon: Calendar, text: 'Какие ближайшие события сильнее всего поднимают спрос на размещение? Топ-5 с расчётом влияния', short: 'События с пиком спроса' },
  { icon: Building2, text: 'Сравни средний тариф и загрузку по всем районам региона за последние 30 дней. Где RevPAR максимальный?', short: 'Сравни районы по тарифу' },
  { icon: MapPin, text: 'Покажи динамику бронирований за последние 14 дней по Ольхонскому району. Тренд ускоряется или замедляется?', short: 'Динамика бронирований' },
  { icon: CloudSun, text: 'Как погода повлияла на загрузку Иркутского района за последний месяц?', short: 'Погода как фактор спроса' },
  { icon: TrendingUp, text: 'Дай прогноз загрузки и факторов спроса по Слюдянскому району на 14 дней', short: 'Прогноз спроса 14 дней' },
]

function Chat() {
  usePageTitle('AI-агент')
  const [searchParams, setSearchParams] = useSearchParams()
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>(() => loadMessages())
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [lastFailedQuery, setLastFailedQuery] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingMsgIdRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const lastUrlContextRef = useRef<string | null>(null)

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current)
      }
      abortRef.current?.abort()
    }
  }, [])

  useEffect(() => {
    saveMessages(messages)
  }, [messages])

  const [streamStatus, setStreamStatus] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async ({ text, sessionId }: { text: string; sessionId: string }) => {
      setStreamStatus(null)
      const msgId = crypto.randomUUID()
      pendingMsgIdRef.current = msgId
      setMessages(prev => [...prev, { id: msgId, role: 'assistant', text: '', timestamp: new Date().toISOString() }])

      let fullText = ''
      let tools: string[] = []
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      try {
        for await (const event of api.queryStream(text, sessionId, controller.signal)) {
          if (event.type === 'token') {
            fullText += event.content
            setMessages(prev => prev.map(m => m.id === msgId ? { ...m, text: fullText } : m))
          } else if (event.type === 'tool_start') {
            setStreamStatus(`Использую ${TOOL_LABELS[event.tool ?? ''] || event.tool}...`)
          } else if (event.type === 'tool_end') {
            setStreamStatus(null)
          } else if (event.type === 'done') {
            tools = event.tools || []
          } else if (event.type === 'error') {
            throw new Error(event.content)
          }
        }
        if (!fullText.trim()) {
          const fallback = await api.query(text, sessionId)
          fullText = fallback.answer
          tools = fallback.sources
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          return
        }
        if (!fullText) {
          const fallback = await api.query(text, sessionId)
          fullText = fallback.answer
          tools = fallback.sources
        }
      }
      pendingMsgIdRef.current = null
      setMessages(prev => prev.map(m => m.id === msgId ? { ...m, text: fullText || 'Нет ответа', sources: tools } : m))
      setStreamStatus(null)
      setLastFailedQuery(null)
      return { answer: fullText, sources: tools }
    },
    onError: (_error, variables) => {
      setStreamStatus(null)
      setLastFailedQuery(variables.text)
      toast.error('Ошибка запроса. Попробуйте ещё раз.', { icon: <AlertCircle size={16} /> })
      const staleId = pendingMsgIdRef.current
      pendingMsgIdRef.current = null
      setMessages(prev => [
        ...prev.filter(m => m.id !== staleId),
        {
          id: crypto.randomUUID(), role: 'assistant',
          text: 'Произошла ошибка при обработке запроса.',
          timestamp: new Date().toISOString(), error: true,
        },
      ])
    },
  })

  const handleSend = useCallback((text: string) => {
    if (!text.trim() || mutation.isPending) return
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      text: text.trim(),
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMessage])
    mutation.mutate({ text: text.trim(), sessionId: getSessionId() })
  }, [mutation])

  const urlContext = searchParams.get('context')?.trim() ?? ''

  useEffect(() => {
    if (!urlContext) {
      lastUrlContextRef.current = null
      return
    }
    if (lastUrlContextRef.current === urlContext) return
    lastUrlContextRef.current = urlContext
    setSearchParams({}, { replace: true })
    handleSend(urlContext)
  }, [urlContext, setSearchParams, handleSend])

  const handleRetry = useCallback(() => {
    if (lastFailedQuery) {
      mutation.mutate({ text: lastFailedQuery, sessionId: getSessionId() })
      toast.success('Повторяю запрос...')
    }
  }, [lastFailedQuery, mutation])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    handleSend(input)
    setInput('')
  }

  function handleQuestion(text: string) {
    handleSend(text)
  }

  function handleCopy(text: string, id: string) {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    if (copyTimeoutRef.current) {
      clearTimeout(copyTimeoutRef.current)
    }
    copyTimeoutRef.current = setTimeout(() => setCopiedId(null), 2000)
  }

  const hasMessages = messages.length > 0

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col animate-fade-in">
      {!hasMessages && (
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))] flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">AI-агент</h1>
              <p className="text-sm text-[hsl(var(--muted-foreground))]">
                B2B-аналитика рынка размещения в режиме диалога
              </p>
              <p className="text-xs text-[hsl(var(--muted-foreground)/0.7)] mt-1 max-w-md">
                Ответы строятся на ансамблевом прогнозе, RMS-метриках (RevPAR, ADR, динамика бронирований) и данных 11 источников. Для отельеров, региональной администрации и исследователей.
              </p>
            </div>
          </div>
        </div>
      )}

      <Card variant="glass" padding="none" className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-4 lg:p-6 space-y-4">
          {!hasMessages ? (
            <EmptyState onQuestion={handleQuestion} isLoading={mutation.isPending} />
          ) : (
            messages.map((msg, idx) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                onCopy={() => handleCopy(msg.text, msg.id)}
                isCopied={copiedId === msg.id}
                onRetry={msg.error ? handleRetry : undefined}
                showTyping={
                  mutation.isPending
                  && msg.role === 'assistant'
                  && !msg.text.trim()
                  && idx === messages.length - 1
                }
              />
            ))
          )}
          
          {streamStatus && (
            <div className="flex justify-center">
              <Badge variant="accent" size="sm" className="animate-pulse">
                {streamStatus}
              </Badge>
            </div>
          )}

          {lastFailedQuery && !mutation.isPending && (
            <div className="flex justify-center">
              <button
                onClick={handleRetry}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[hsl(var(--destructive)/0.1)] border border-[hsl(var(--destructive)/0.3)] text-[hsl(var(--destructive))] hover:bg-[hsl(var(--destructive)/0.2)] transition-colors"
              >
                <RefreshCw size={16} />
                Повторить запрос
              </button>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {hasMessages && !mutation.isPending && (
          <div className="px-4 pb-2 flex gap-2 overflow-x-auto">
            {QUICK_QUESTIONS.slice(0, 4).map(({ text, short }) => (
              <button
                key={text}
                onClick={() => handleQuestion(text)}
                className="px-3 py-1.5 rounded-full border border-[hsl(var(--border))] bg-[hsl(var(--secondary)/0.5)] hover:bg-[hsl(var(--secondary))] text-xs text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] whitespace-nowrap transition-all"
              >
                {short}
              </button>
            ))}
          </div>
        )}

        <div className="border-t border-[hsl(var(--border))] p-3 lg:p-4 bg-[hsl(var(--card)/0.5)]">
          <form onSubmit={handleSubmit} className="flex gap-2 lg:gap-3">
            {hasMessages && (
              <button
                type="button"
                onClick={() => { setMessages([]); localStorage.removeItem(SESSION_KEY); }}
                className="p-3 rounded-xl border border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--destructive))] hover:border-[hsl(var(--destructive)/0.3)] transition-colors"
                title="Очистить чат"
              >
                <Trash2 size={18} />
              </button>
            )}
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Спросите B2B-аналитика: RevPAR, прогноз, события, RMS-метрики..."
              className="flex-1 bg-[hsl(var(--input))] border border-[hsl(var(--border))] rounded-xl px-4 py-3 text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))] focus:border-transparent transition-all"
            />
            <Button
              type="submit"
              variant="primary"
              size="lg"
              disabled={mutation.isPending || !input.trim()}
              isLoading={mutation.isPending}
            >
              <Send size={18} />
            </Button>
          </form>
        </div>
      </Card>
    </div>
  )
}

function EmptyState({ onQuestion, isLoading }: { onQuestion: (text: string) => void; isLoading: boolean }) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center py-8">
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[hsl(var(--primary)/0.2)] to-[hsl(var(--accent)/0.2)] flex items-center justify-center mb-4">
        <Sparkles className="w-8 h-8 text-[hsl(var(--primary))]" />
      </div>
      <h3 className="text-lg font-semibold mb-2">Чем могу помочь?</h3>
      <p className="text-sm text-[hsl(var(--muted-foreground))] max-w-md mb-6">
        Запросите RMS-метрики, прогноз спроса, влияние событий или сравнительную аналитику районов.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 w-full max-w-2xl">
        {QUICK_QUESTIONS.map(({ icon: Icon, text, short }) => (
          <button
            key={text}
            onClick={() => onQuestion(text)}
            disabled={isLoading}
            className="flex items-center gap-3 p-3 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--secondary)/0.6)] hover:bg-[hsl(var(--secondary))] hover:border-[hsl(var(--primary)/0.5)] transition-all text-left group disabled:opacity-50"
          >
            <div className="w-8 h-8 rounded-lg bg-[hsl(var(--primary)/0.15)] flex items-center justify-center text-[hsl(var(--primary))] group-hover:bg-[hsl(var(--primary)/0.25)] transition-colors">
              <Icon size={16} />
            </div>
            <span className="text-sm text-[hsl(var(--foreground))] flex-1">
              {short}
            </span>
            <ArrowRight size={14} className="text-[hsl(var(--primary))] opacity-50 group-hover:opacity-100 transition-opacity" />
          </button>
        ))}
      </div>
    </div>
  )
}

function MessageBubble({
  message,
  onCopy,
  isCopied,
  onRetry,
  showTyping,
}: {
  message: Message
  onCopy: () => void
  isCopied: boolean
  onRetry?: () => void
  showTyping?: boolean
}) {
  const isUser = message.role === 'user'
  const isError = message.error

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`
        w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0
        ${isUser
          ? 'bg-[hsl(var(--secondary))]'
          : isError
            ? 'bg-[hsl(var(--destructive))]'
            : 'bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))]'
        }
      `}>
        {isUser
          ? <User className="w-4 h-4 text-[hsl(var(--foreground))]" />
          : isError
            ? <AlertCircle className="w-4 h-4 text-white" />
            : <Bot className="w-4 h-4 text-white" />
        }
      </div>

      <div className={`flex-1 max-w-[85%] ${isUser ? 'flex flex-col items-end' : ''}`}>
        <Card
          variant={isUser ? 'gradient' : isError ? 'default' : 'default'}
          padding="md"
          className={`
            relative group
            ${isUser
              ? 'bg-gradient-to-r from-[hsl(var(--primary))] to-[hsl(var(--accent))] border-0'
              : isError
                ? 'border-[hsl(var(--destructive)/0.3)] bg-[hsl(var(--destructive)/0.05)]'
                : ''
            }
          `}
        >
          {isUser ? (
            <p className="text-sm leading-relaxed whitespace-pre-wrap text-white">
              {message.text}
            </p>
          ) : showTyping ? (
            <p className="text-sm text-[hsl(var(--muted-foreground))] flex items-center gap-2">
              <span className="inline-flex gap-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-[hsl(var(--primary))] animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-[hsl(var(--primary))] animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-[hsl(var(--primary))] animate-bounce [animation-delay:300ms]" />
              </span>
              Генерирую ответ…
            </p>
          ) : (
            <div className="prose prose-sm prose-invert max-w-none
              prose-headings:text-[hsl(var(--foreground))] prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-2
              prose-h1:text-lg prose-h2:text-base prose-h3:text-sm prose-h4:text-sm
              prose-p:text-[hsl(var(--foreground))] prose-p:leading-relaxed prose-p:my-2
              prose-strong:text-[hsl(var(--foreground))] prose-strong:font-semibold
              prose-ul:my-2 prose-ul:pl-4 prose-ol:my-2 prose-ol:pl-4
              prose-li:text-[hsl(var(--foreground))] prose-li:my-0.5
              prose-table:my-3 prose-table:text-sm
              prose-th:bg-[hsl(var(--secondary))] prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:font-medium prose-th:border prose-th:border-[hsl(var(--border))]
              prose-td:px-3 prose-td:py-2 prose-td:border prose-td:border-[hsl(var(--border))]
              prose-hr:my-4 prose-hr:border-[hsl(var(--border))]
              prose-code:text-[hsl(var(--primary))] prose-code:bg-[hsl(var(--secondary))] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs
              prose-pre:bg-[hsl(var(--secondary))] prose-pre:p-3 prose-pre:rounded-lg
              prose-a:text-[hsl(var(--primary))] prose-a:underline hover:prose-a:no-underline
              prose-blockquote:border-l-2 prose-blockquote:border-[hsl(var(--primary))] prose-blockquote:pl-4 prose-blockquote:italic
            ">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.text}
              </ReactMarkdown>
            </div>
          )}
          
          {!isUser && (
            <button
              onClick={onCopy}
              className="absolute top-2 right-2 p-1.5 rounded-lg bg-[hsl(var(--secondary))] sm:opacity-0 sm:group-hover:opacity-100 transition-opacity"
            >
              {isCopied 
                ? <Check size={12} className="text-[hsl(var(--success))]" />
                : <Copy size={12} className="text-[hsl(var(--muted-foreground))]" />
              }
            </button>
          )}
        </Card>
        
        {message.sources && message.sources.length > 0 && (
          <div className="flex gap-1 mt-1.5 flex-wrap">
            {message.sources.map((source, i) => (
              <Badge key={i} variant="outline" size="sm">
                {TOOL_LABELS[source] || source}
              </Badge>
            ))}
          </div>
        )}

        {isError && onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1.5 mt-2 text-xs text-[hsl(var(--destructive))] hover:underline"
          >
            <RefreshCw size={12} />
            Повторить
          </button>
        )}
      </div>
    </div>
  )
}

export default Chat
