import { useEffect, useRef, useMemo } from 'react'
import { DISTRICT_COORDS } from '../constants/districts'
import { useTheme } from '../hooks/useTheme'
import * as echarts from 'echarts/core'
import { MapChart, ScatterChart, EffectScatterChart } from 'echarts/charts'
import {
  TooltipComponent,
  VisualMapComponent,
  GeoComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'

echarts.use([MapChart, ScatterChart, EffectScatterChart, TooltipComponent, VisualMapComponent, GeoComponent, CanvasRenderer])

type DistrictGeoData = {
  district: string
  occupancy: number
  freeRooms: number
  totalRooms: number
  avgPrice: number
}

type Props = {
  districts: DistrictGeoData[]
  onDistrictClick?: (district: string) => void
}

function _findCoords(district: string): [number, number] | null {
  if (DISTRICT_COORDS[district]) return DISTRICT_COORDS[district]
  const stripped = district.replace(/\s*район$/i, '')
  if (DISTRICT_COORDS[stripped]) return DISTRICT_COORDS[stripped]
  for (const [key, val] of Object.entries(DISTRICT_COORDS)) {
    if (district.startsWith(key) || key.startsWith(district)) return val
  }
  return null
}

const PALETTE = {
  dark: {
    tooltipBg: '#1c1c2e',
    tooltipBorder: '#2d2d44',
    tooltipText: '#e2e2e8',
    areaColor: '#1e1e30',
    areaBorder: '#3a3a55',
    areaEmphasis: '#2a3a5a',
    labelName: '#e2e2e8',
    labelOcc: '#9898b0',
  },
  light: {
    tooltipBg: '#ffffff',
    tooltipBorder: '#e2e8f0',
    tooltipText: '#1e293b',
    areaColor: '#f1f5f9',
    areaBorder: '#cbd5e1',
    areaEmphasis: '#e2e8f0',
    labelName: '#1e293b',
    labelOcc: '#64748b',
  },
} as const

export function GeoMap({ districts, onDistrictClick }: Props) {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)
  const { isDark } = useTheme()

  const scatterData = useMemo(() => {
    return districts.map(d => {
      const coords = _findCoords(d.district)
      if (!coords) return null
      return {
        name: d.district,
        value: [...coords, d.occupancy],
        occupancy: d.occupancy,
        freeRooms: d.freeRooms,
        totalRooms: d.totalRooms,
        avgPrice: d.avgPrice,
      }
    }).filter(Boolean)
  }, [districts])

  useEffect(() => {
    if (!chartRef.current) return

    if (chartInstance.current) {
      chartInstance.current.dispose()
    }
    chartInstance.current = echarts.init(chartRef.current, undefined, { renderer: 'canvas' })
    const chart = chartInstance.current

    const maxOcc = Math.max(...districts.map(d => d.occupancy), 1)
    const p = isDark ? PALETTE.dark : PALETTE.light

    const option = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: p.tooltipBg,
        borderColor: p.tooltipBorder,
        textStyle: { color: p.tooltipText },
        formatter: (params: { data?: { name?: string; occupancy?: number; freeRooms?: number; totalRooms?: number; avgPrice?: number } }) => {
          const d = params.data
          if (!d) return ''
          return `
            <div style="font-weight:600;margin-bottom:4px">${d.name}</div>
            <div>Загрузка: <b>${Math.round(d.occupancy ?? 0)}%</b></div>
            <div>Свободно: ${d.freeRooms} номеров</div>
            <div>Всего: ${d.totalRooms} номеров</div>
            ${d.avgPrice ? `<div>Ср. цена: ${Math.round(d.avgPrice).toLocaleString()}₽</div>` : ''}
          `
        },
      },
      geo: {
        map: 'irkutsk',
        roam: true,
        zoom: 1.2,
        center: [103, 54.5],
        itemStyle: {
          areaColor: p.areaColor,
          borderColor: p.areaBorder,
          borderWidth: 1,
        },
        emphasis: {
          itemStyle: {
            areaColor: p.areaEmphasis,
          },
        },
        silent: true,
      },
      series: [{
        type: 'scatter',
        coordinateSystem: 'geo',
        data: scatterData,
        symbolSize: (val: number[]) => {
          const occ = val[2] || 0
          return Math.max(20, (occ / maxOcc) * 60)
        },
        itemStyle: {
          color: (params: { data?: { occupancy?: number } }) => {
            const occ = params.data?.occupancy || 0
            if (occ > 70) return 'hsl(0, 84%, 60%)'
            if (occ > 40) return 'hsl(38, 92%, 50%)'
            return 'hsl(142, 71%, 45%)'
          },
          shadowBlur: 10,
          shadowColor: isDark ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.1)',
        },
        emphasis: {
          scale: 1.3,
        },
        label: {
          show: true,
          formatter: (params: { data?: { name?: string; occupancy?: number } }) => {
            const name = (params.data?.name || '').replace(' район', '')
            return `{name|${name}}\n{occ|${Math.round(params.data?.occupancy || 0)}%}`
          },
          rich: {
            name: {
              fontSize: 11,
              fontWeight: 600,
              color: p.labelName,
              padding: [0, 0, 2, 0],
            },
            occ: {
              fontSize: 10,
              color: p.labelOcc,
            },
          },
          position: 'top',
          distance: 8,
        },
      }],
    }

    _registerIrkutskMap()
    chart.setOption(option as EChartsOption)

    chart.on('click', (params) => {
      const name = (params as { data?: { name?: string } }).data?.name
      if (name && onDistrictClick) {
        onDistrictClick(name)
      }
    })

    const handleResize = () => {
      if (chartInstance.current && !chartInstance.current.isDisposed()) {
        chartInstance.current.resize()
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chartInstance.current?.dispose()
      chartInstance.current = null
    }
  }, [scatterData, districts, onDistrictClick, isDark])

  return (
    <div ref={chartRef} className="w-full h-[300px] sm:h-[400px] lg:h-[500px]" />
  )
}

function _registerIrkutskMap() {
  if ((echarts as unknown as { getMap(name: string): unknown }).getMap('irkutsk')) return

  const geoJson = {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      properties: { name: 'Иркутская область' },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [95.5, 52.0], [96.0, 53.0], [96.5, 54.5], [97.0, 55.5],
          [97.5, 56.5], [98.0, 57.5], [99.0, 58.5], [100.0, 59.5],
          [101.5, 60.0], [103.0, 60.5], [104.5, 60.0], [106.0, 59.0],
          [107.0, 57.5], [107.5, 56.0], [108.0, 55.0], [108.5, 54.0],
          [109.0, 53.0], [108.5, 52.0], [108.0, 51.5], [107.0, 51.0],
          [106.0, 51.5], [105.0, 51.5], [104.0, 51.5], [103.0, 51.5],
          [102.0, 51.8], [101.0, 52.0], [100.0, 52.0], [99.0, 51.8],
          [98.0, 51.5], [97.0, 51.5], [96.0, 51.5], [95.5, 52.0],
        ]],
      },
    }],
  }

  echarts.registerMap('irkutsk', geoJson as Parameters<typeof echarts.registerMap>[1])
}
