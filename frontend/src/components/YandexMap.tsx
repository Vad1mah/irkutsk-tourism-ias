import { YMaps, Map, Placemark } from '@pbe/react-yandex-maps'

export type HotelPin = {
  id: string
  name: string
  lat: number
  lon: number
  rooms_num?: number | null
  occupancy?: number | null
  min_price?: number | null
}

type Props = {
  hotels: HotelPin[]
  center?: [number, number]
  zoom?: number
  onHotelClick?: (id: string) => void
}

const DEFAULT_CENTER: [number, number] = [52.2871, 104.305] // Иркутск
const APIKEY = import.meta.env.VITE_YANDEX_MAPS_API_KEY as string | undefined

function _colorForOccupancy(occ: number | null | undefined): string {
  if (occ == null) return '#94a3b8' // gray
  if (occ < 40) return '#22c55e'   // green
  if (occ < 70) return '#f59e0b'   // amber
  return '#ef4444'                  // red
}

export function YandexMap({ hotels, center = DEFAULT_CENTER, zoom = 7, onHotelClick }: Props) {
  return (
    <YMaps query={{ apikey: APIKEY, lang: 'ru_RU' }}>
      <Map
        defaultState={{ center, zoom, controls: ['zoomControl', 'typeSelector', 'fullscreenControl'] }}
        width="100%"
        height={520}
        modules={['control.ZoomControl', 'control.TypeSelector', 'control.FullscreenControl']}
        options={{ suppressMapOpenBlock: true }}
      >
        {hotels.filter(h => h.lat != null && h.lon != null).map(h => (
          <Placemark
            key={h.id}
            geometry={[h.lat, h.lon]}
            options={{
              preset: 'islands#circleDotIcon',
              iconColor: _colorForOccupancy(h.occupancy),
            }}
            properties={{
              balloonContentHeader: `<strong>${h.name ?? 'Объект'}</strong>`,
              balloonContentBody: `
                <div style="font-size:12px;line-height:1.5">
                  ${h.rooms_num != null ? `Номеров: <b>${h.rooms_num}</b><br/>` : ''}
                  ${h.occupancy != null ? `Загрузка: <b>${h.occupancy.toFixed(0)}%</b><br/>` : ''}
                  ${h.min_price != null ? `Мин. цена: <b>${h.min_price.toLocaleString('ru-RU')} ₽</b><br/>` : ''}
                  <a href="/hotels/${encodeURIComponent(h.id)}" style="color:#3b82f6">Подробнее →</a>
                </div>
              `,
              hintContent: h.name ?? 'Объект',
            }}
            onClick={() => onHotelClick?.(h.id)}
            modules={['geoObject.addon.balloon', 'geoObject.addon.hint']}
          />
        ))}
      </Map>
    </YMaps>
  )
}
