import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceArea } from 'recharts'

type GapAwarePoint = { date: string; value: number | null; is_gap?: boolean }

type Props = {
  data: GapAwarePoint[]
  height?: number
  yLabel?: string
}

export function GapAwareLineChart({ data, height = 200, yLabel }: Props) {
  // Find gap ranges (consecutive is_gap points)
  const gapRanges: Array<{ from: string; to: string }> = []
  let inGap = false
  let gapStart: string | null = null
  for (let i = 0; i < data.length; i++) {
    const p = data[i]
    if (p.is_gap && !inGap) {
      inGap = true
      gapStart = p.date
    } else if (!p.is_gap && inGap && gapStart) {
      gapRanges.push({ from: gapStart, to: data[i - 1].date })
      inGap = false
      gapStart = null
    }
  }
  if (inGap && gapStart) {
    gapRanges.push({ from: gapStart, to: data[data.length - 1].date })
  }

  // Replace gap values with null so line breaks
  const chartData = data.map(p => ({ date: p.date, value: p.is_gap ? null : p.value }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData}>
        <XAxis dataKey="date" tick={{ fontSize: 10 }} />
        <YAxis
          tick={{ fontSize: 10 }}
          label={yLabel ? { value: yLabel, angle: -90, position: 'insideLeft' } : undefined}
        />
        <Tooltip />
        {gapRanges.map((g, i) => (
          <ReferenceArea
            key={i}
            x1={g.from}
            x2={g.to}
            fill="hsl(var(--muted)/0.3)"
            label={{ value: 'Нет данных', position: 'insideTop', fontSize: 10 }}
          />
        ))}
        <Line
          type="monotone"
          dataKey="value"
          stroke="hsl(var(--primary))"
          strokeWidth={2}
          connectNulls={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
