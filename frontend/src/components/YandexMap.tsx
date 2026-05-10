import { YMaps, Map, Placemark, FullscreenControl } from '@pbe/react-yandex-maps'

export type HotelPin = {
  id: string
  name: string
  lat: number
  lon: number
  city?: string | null
  district?: string | null
  rooms_num?: number | null
  free_rooms?: number | null
  max_capacity?: number | null
  occupancy?: number | null
  min_price?: number | null
  rating?: number | null
}

type Props = {
  hotels: HotelPin[]
  center?: [number, number]
  zoom?: number
  height?: number | string
  pinnedHotelId?: string | null
  onHotelClick?: (id: string) => void
  onHotelHover?: (hotel: HotelPin | null) => void
}

const DEFAULT_CENTER: [number, number] = [52.2871, 104.305] // Иркутск
const APIKEY = import.meta.env.VITE_YANDEX_MAPS_API_KEY as string | undefined

function _colorForOccupancy(occ: number | null | undefined): string {
  if (occ == null) return '#94a3b8' // gray
  if (occ < 40) return '#22c55e'   // green
  if (occ < 70) return '#f59e0b'   // amber
  return '#ef4444'                  // red
}

function _hintFor(h: HotelPin): string {
  const parts: string[] = [h.name ?? 'Объект']
  if (h.occupancy != null) parts.push(`загрузка ${h.occupancy.toFixed(0)}%`)
  if (h.free_rooms != null && h.rooms_num != null) parts.push(`свободно ${h.free_rooms}/${h.rooms_num}`)
  if (h.min_price != null) parts.push(`от ${h.min_price.toLocaleString('ru-RU')} ₽`)
  return parts.join(' • ')
}

function _balloonBody(h: HotelPin): string {
  const rows: string[] = []
  if (h.district || h.city) rows.push(`${h.city ?? ''}${h.city && h.district ? ', ' : ''}${h.district ?? ''}`)
  if (h.rooms_num != null) {
    const free = h.free_rooms != null ? ` (свободно ${h.free_rooms})` : ''
    rows.push(`Номеров: <b>${h.rooms_num}</b>${free}`)
  }
  if (h.occupancy != null) rows.push(`Загрузка: <b>${h.occupancy.toFixed(0)}%</b>`)
  if (h.min_price != null) rows.push(`Мин. цена: <b>${h.min_price.toLocaleString('ru-RU')} ₽</b>`)
  if (h.max_capacity != null) rows.push(`Вместимость: до ${h.max_capacity} чел.`)
  if (h.rating != null) rows.push(`Рейтинг: ${h.rating.toFixed(1)} ★`)
  return `
    <div style="font-size:12px;line-height:1.6">
      ${rows.map(r => `<div>${r}</div>`).join('')}
      <a href="/hotels/${encodeURIComponent(h.id)}" style="color:#3b82f6;display:inline-block;margin-top:6px">Подробнее →</a>
    </div>
  `
}

export function YandexMap({ hotels, center = DEFAULT_CENTER, zoom = 7, height = 520, pinnedHotelId, onHotelClick, onHotelHover }: Props) {
  return (
    <YMaps query={{ apikey: APIKEY, lang: 'ru_RU' }}>
      <Map
        defaultState={{ center, zoom, controls: ['zoomControl', 'typeSelector'] }}
        width="100%"
        height={height}
        modules={['control.ZoomControl', 'control.TypeSelector', 'control.FullscreenControl']}
        options={{ suppressMapOpenBlock: true }}
      >
        {/* mode:'browser' — стандартный Fullscreen API. Только так срабатывает
            document.fullscreenchange, на котором основан remount чартов в Map.tsx.
            Дефолтный 'viewport' использует CSS position:fixed без события.
            'mode' валиден в Yandex Maps API, но отсутствует в @pbe types. */}
        <FullscreenControl
          options={{ float: 'right', mode: 'browser' } as React.ComponentProps<typeof FullscreenControl>['options']}
        />
        {hotels.filter(h => h.lat != null && h.lon != null).map(h => {
          const isPinned = pinnedHotelId === h.id
          return (
            <Placemark
              key={h.id}
              geometry={[h.lat, h.lon]}
              options={{
                preset: isPinned ? 'islands#circleDotIcon' : 'islands#circleIcon',
                iconColor: _colorForOccupancy(h.occupancy),
                zIndex: isPinned ? 1000 : 100,
              }}
              properties={{
                balloonContentHeader: `<strong>${h.name ?? 'Объект'}</strong>`,
                balloonContentBody: _balloonBody(h),
                hintContent: _hintFor(h),
              }}
              onClick={() => onHotelClick?.(h.id)}
              onMouseEnter={() => onHotelHover?.(h)}
              onMouseLeave={() => onHotelHover?.(null)}
              modules={['geoObject.addon.balloon', 'geoObject.addon.hint']}
            />
          )
        })}
      </Map>
    </YMaps>
  )
}
