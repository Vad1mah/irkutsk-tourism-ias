import { useMemo } from 'react'
import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet'
import { useTheme } from '../hooks/useTheme'
import type { MapHotel } from '../api/client'
import 'leaflet/dist/leaflet.css'

type DistrictGeoData = {
  district: string
  occupancy: number
  freeRooms: number
  totalRooms: number
  avgPrice: number
}

type Props = {
  districts: DistrictGeoData[]
  hotels?: MapHotel[]
  onDistrictClick?: (district: string) => void
  onHotelClick?: (hotelId: string) => void
}

const IRKUTSK_CENTER: [number, number] = [53.5, 106.0]
const DEFAULT_ZOOM = 6

function _occColor(occ: number): string {
  if (occ > 70) return 'hsl(0, 84%, 60%)'
  if (occ > 40) return 'hsl(38, 92%, 50%)'
  return 'hsl(142, 71%, 45%)'
}

function _occRadius(occ: number): number {
  return Math.max(4, Math.min(12, (occ / 100) * 12))
}

export function GeoMap({ hotels, onHotelClick }: Props) {
  const { isDark } = useTheme()

  const tileUrl = isDark
    ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
    : 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png'

  const markers = useMemo(() => {
    if (!hotels?.length) return []
    return hotels.filter(h => h.lat && h.lon)
  }, [hotels])

  return (
    <MapContainer
      center={IRKUTSK_CENTER}
      zoom={DEFAULT_ZOOM}
      className="w-full h-[300px] sm:h-[400px] lg:h-[500px] rounded-lg z-0"
      scrollWheelZoom
      attributionControl={false}
    >
      <TileLayer url={tileUrl} />

      {markers.map(h => (
        <CircleMarker
          key={h.id}
          center={[h.lat, h.lon]}
          radius={_occRadius(h.occupancy)}
          pathOptions={{
            fillColor: _occColor(h.occupancy),
            fillOpacity: 0.85,
            color: isDark ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.2)',
            weight: 1,
          }}
          eventHandlers={{
            click: () => onHotelClick?.(h.id),
          }}
        >
          <Tooltip direction="top" offset={[0, -6]}>
            <div className="text-xs">
              <div className="font-semibold mb-1">{h.name}</div>
              {h.city && (
                <div className="text-gray-500 mb-1">{h.city}, {(h.district || '').replace(' район', '')} р-н</div>
              )}
              <div>Заполняемость: <b>{Math.round(h.occupancy)}%</b></div>
              <div>Номеров: {h.rooms_num || '—'}</div>
              {h.min_price != null && <div>Цена от: {Math.round(h.min_price).toLocaleString()}₽</div>}
              {h.rating != null && <div>Рейтинг: {h.rating}</div>}
            </div>
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}
