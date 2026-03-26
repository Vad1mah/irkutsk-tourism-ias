import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { Building2, MapPin, Star, ArrowLeft, TrendingUp, DollarSign } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, Badge } from '../components/ui'
import { ErrorState } from '../components/ErrorState'
import { usePageTitle } from '../hooks/usePageTitle'
import { api } from '../api/client'

function HotelDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  usePageTitle('Отель')

  const { data: hotel, isLoading, isError, refetch } = useQuery({
    queryKey: ['hotel', id],
    queryFn: () => api.getHotel(id!),
    enabled: !!id,
  })

  const { data: stats } = useQuery({
    queryKey: ['hotel-stats', id],
    queryFn: () => api.getHotelStats(id!),
    enabled: !!id,
  })

  if (isLoading) {
    return (
      <div className="space-y-4 animate-fade-in">
        <div className="h-8 w-48 skeleton rounded-lg" />
        <div className="h-40 skeleton rounded-xl" />
        <div className="h-64 skeleton rounded-xl" />
      </div>
    )
  }

  if (isError || !hotel) {
    return <ErrorState title="Отель не найден" message="Проверьте ссылку или вернитесь к списку." onRetry={() => refetch()} />
  }

  const chartData = (stats || [])
    .sort((a, b) => a.date.localeCompare(b.date))
    .map(s => ({
      date: new Date(s.date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }),
      occupancy: s.available_rooms_percent != null ? Math.round(100 - s.available_rooms_percent) : null,
      price: s.min_price,
      free: s.free_rooms_amount,
    }))

  const lastStat = stats?.length ? stats[stats.length - 1] : null
  const currentOccupancy = lastStat?.available_rooms_percent != null
    ? Math.round(100 - lastStat.available_rooms_percent)
    : null

  return (
    <div className="space-y-6 animate-fade-in max-w-4xl mx-auto">
      <button onClick={() => navigate(-1)} className="inline-flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors">
        <ArrowLeft size={16} />
        Назад
      </button>

      <Card variant="glass">
        <CardContent>
          <div className="flex items-start gap-4">
            {hotel.image_url ? (
              <img
                src={hotel.image_url}
                alt={hotel.name}
                className="w-24 h-24 rounded-xl object-cover flex-shrink-0"
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
            ) : (
              <div className="w-24 h-24 rounded-xl bg-[hsl(var(--secondary))] flex items-center justify-center flex-shrink-0">
                <Building2 className="w-10 h-10 text-[hsl(var(--muted-foreground))]" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <h1 className="text-2xl font-bold mb-1">{hotel.name}</h1>
              <div className="flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))] mb-3">
                <MapPin size={14} />
                <span>{hotel.city}</span>
                {hotel.district && <Badge variant="outline" size="sm">{hotel.district}</Badge>}
              </div>
              <div className="flex flex-wrap gap-2">
                {hotel.rating != null && (
                  <Badge variant="primary" size="sm">
                    <Star size={12} /> {hotel.rating.toFixed(1)}
                  </Badge>
                )}
                {currentOccupancy != null && (
                  <Badge
                    variant={currentOccupancy > 70 ? 'danger' : currentOccupancy > 40 ? 'warning' : 'success'}
                    size="sm"
                  >
                    <TrendingUp size={12} /> Загрузка {currentOccupancy}%
                  </Badge>
                )}
                {lastStat?.min_price != null && (
                  <Badge variant="outline" size="sm">
                    <DollarSign size={12} /> от {lastStat.min_price.toLocaleString()}₽
                  </Badge>
                )}
              </div>
              {hotel.district && (
                <button
                  onClick={() => navigate(`/forecast?district=${encodeURIComponent(hotel.district || '')}`)}
                  className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-[hsl(var(--primary)/0.1)] text-[hsl(var(--primary))] hover:bg-[hsl(var(--primary)/0.2)] transition-colors"
                >
                  <TrendingUp size={14} />
                  Прогноз района {hotel.district}
                </button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {chartData.length > 0 ? (
        <>
          <Card variant="glass">
            <CardHeader>
              <CardTitle>Загруженность</CardTitle>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                Расчётная загруженность: доля занятых номеров по данным агрегатора
              </p>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `${v}%`} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                      color: 'hsl(var(--foreground))',
                    }}
                    formatter={(v: number) => [`${v}%`, 'Загрузка']}
                  />
                  <Area type="monotone" dataKey="occupancy" stroke="hsl(var(--primary))" fill="hsl(var(--primary))" fillOpacity={0.15} strokeWidth={2} connectNulls />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {chartData.some(d => d.price != null) && (
            <Card variant="glass">
              <CardHeader>
                <CardTitle>Динамика цен</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `${(v / 1000).toFixed(0)}k₽`} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '8px',
                        color: 'hsl(var(--foreground))',
                      }}
                      formatter={(v: number) => [`${v.toLocaleString()}₽`, 'Мин. цена']}
                    />
                    <Area type="monotone" dataKey="price" stroke="hsl(var(--accent))" fill="hsl(var(--accent))" fillOpacity={0.15} strokeWidth={2} connectNulls />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          <Card variant="default">
            <CardHeader>
              <CardTitle>Статистика ({chartData.length} записей)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold text-[hsl(var(--primary))]">
                    {lastStat?.rooms_num || '—'}
                  </p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Всего номеров</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-[hsl(var(--success))]">
                    {lastStat?.free_rooms_amount || '—'}
                  </p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Свободно</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-[hsl(var(--accent))]">
                    {lastStat?.min_price ? `${lastStat.min_price.toLocaleString()}₽` : '—'}
                  </p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Мин. цена</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-[hsl(var(--warning))]">
                    {currentOccupancy != null ? `${currentOccupancy}%` : '—'}
                  </p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Загрузка</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      ) : (
        <Card variant="glass">
          <CardContent>
            <p className="text-center text-[hsl(var(--muted-foreground))] py-8">
              Нет данных о загруженности для этого отеля. Данные появятся после работы парсера.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default HotelDetail
