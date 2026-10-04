/** 运行对比：指标并排表 + 曲线叠加（KStock 桌面端同款语义）。
 * 策略库叠加净值曲线（normalizeEquity 归一到同起点 1），因子库叠加累计
 * IC 曲线（cumulativeIc 0 起点累加）；曲线负载不随 detail 常驻传输，勾选
 * ≥2 个运行时经 library_runs 端点整批拉取。选股库无时间序列，仅指标表
 * （KStock 选股对比是命中重合分析，依赖 picks 明细，留待后续版本）。 */

import { useEffect, useMemo, useRef, useState } from 'react'
import type { LibraryTab, Translate } from './runtime.ts'

/** KStock 桌面端运行对比同款配色（中亮度，明暗主题下均可读）。 */
const RUN_COLORS = ['#e8a33d', '#5ab0ff', '#22a06b', '#c792ea', '#e64646', '#8ee6c8']

const CHART_WIDTH = 560
const CHART_HEIGHT = 240
const PAD_LEFT = 46
const PAD_RIGHT = 12
const PAD_TOP = 14
const PAD_BOTTOM = 26

interface CurveSeries {
  readonly label: string
  readonly values: number[]
  readonly color: string
}

function runIdOf(run: Record<string, unknown>): string {
  return typeof run['run_id'] === 'string' ? run['run_id'] : ''
}

function versionOf(run: Record<string, unknown>): number {
  return typeof run['version'] === 'number' ? run['version'] : 0
}

/** 净值归一化（KStock StrategiesLibrary.normalizeEquity 同款）：兼容
 * [{date,equity}] / 数值数组 / {dates,values|equity_values} 形态，
 * 统一除以首值，让不同运行的曲线从同一起点 1 开始可比。 */
export function normalizeEquity(raw: unknown): number[] {
  let values: number[] = []
  if (Array.isArray(raw)) {
    const asObjects = raw.every((item) => typeof item === 'object' && item !== null
      && typeof (item as Record<string, unknown>)['equity'] === 'number')
    if (asObjects) {
      values = (raw as Record<string, unknown>[]).map((item) => item['equity'] as number)
    } else {
      values = raw.filter((item): item is number => typeof item === 'number')
    }
  } else if (typeof raw === 'object' && raw !== null) {
    const record = raw as Record<string, unknown>
    const candidate = Array.isArray(record['values']) ? record['values'] : record['equity_values']
    if (Array.isArray(candidate)) values = candidate.filter((v): v is number => typeof v === 'number')
  }
  const base = values[0]
  if (base === undefined || !Number.isFinite(base) || base <= 0) return values
  return values.map((value) => value / base)
}

/** IC 累计（KStock FactorsLibrary.cumulativeIc 同款）：兼容 [{date,ic}] /
 * 数值数组，0 起点逐期累加，得到累计 IC 曲线。 */
export function cumulativeIc(raw: unknown): number[] {
  let values: number[] = []
  if (Array.isArray(raw)) {
    const asObjects = raw.every((item) => typeof item === 'object' && item !== null
      && typeof (item as Record<string, unknown>)['ic'] === 'number')
    if (asObjects) {
      values = (raw as Record<string, unknown>[]).map((item) => item['ic'] as number)
    } else {
      values = raw.filter((item): item is number => typeof item === 'number')
    }
  }
  const out: number[] = []
  let acc = 0
  for (const value of values) {
    acc += Number.isFinite(value) ? value : 0
    out.push(acc)
  }
  return out
}

function bounds(values: number[]): { min: number; max: number } {
  let min = Number.POSITIVE_INFINITY
  let max = Number.NEGATIVE_INFINITY
  for (const value of values) {
    if (value < min) min = value
    if (value > max) max = value
  }
  return { min, max }
}

/** KStock EquityOverlay/IcOverlay 同几何的叠加 SVG：虚线基线（净值 1 /
 * 累计 IC 0）+ 首末值刻度 + 每序列折线与图例（点数/期数）。 */
function CurveOverlay(props: {
  ariaLabel: string
  baseline: number
  baselineLabel: string
  includeBaseline: boolean
  series: readonly CurveSeries[]
  unit: string
}): React.ReactElement | null {
  const drawable = props.series.filter((item) => item.values.length >= 2)
  if (drawable.length === 0) return null
  const flat = drawable.flatMap((item) => item.values)
  const data = bounds(flat)
  const min = props.includeBaseline ? Math.min(data.min, props.baseline) : data.min
  const max = props.includeBaseline ? Math.max(data.max, props.baseline) : data.max
  const span = max - min || 1
  const maxLen = drawable.reduce((acc, item) => Math.max(acc, item.values.length), 0)
  const x = (index: number, length: number): number =>
    PAD_LEFT + (index / Math.max(1, length - 1)) * (CHART_WIDTH - PAD_LEFT - PAD_RIGHT)
  const y = (value: number): number =>
    PAD_TOP + (1 - (value - min) / span) * (CHART_HEIGHT - PAD_BOTTOM - PAD_TOP)
  return (
    <svg className='kss-curve-svg' viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} role='img' aria-label={props.ariaLabel}>
      <line className='kss-curve-grid' x1={PAD_LEFT} y1={y(props.baseline)} x2={CHART_WIDTH - PAD_RIGHT} y2={y(props.baseline)} />
      <text className='kss-curve-axis' x={PAD_LEFT - 6} y={y(props.baseline) + 4} textAnchor='end'>{props.baselineLabel}</text>
      <text className='kss-curve-axis' x={PAD_LEFT - 6} y={y(max) + 4} textAnchor='end'>{max.toFixed(2)}</text>
      <text className='kss-curve-axis' x={PAD_LEFT - 6} y={y(min) + 4} textAnchor='end'>{min.toFixed(2)}</text>
      {drawable.map((item) => (
        <polyline
          key={item.label}
          className='kss-curve-line'
          style={{ stroke: item.color }}
          points={item.values.map((value, index) => `${x(index, item.values.length)},${y(value)}`).join(' ')}
        />
      ))}
      {drawable.map((item, row) => (
        <g key={`legend-${item.label}`}>
          <rect x={PAD_LEFT + row * 120} y={CHART_HEIGHT - 14} width={10} height={10} fill={item.color} />
          <text className='kss-curve-legend' x={PAD_LEFT + row * 120 + 15} y={CHART_HEIGHT - 5}>
            {item.label}（{item.values.length === maxLen ? `${item.values.length}${props.unit}` : `${item.values.length}/${maxLen}${props.unit}`}）
          </text>
        </g>
      ))}
    </svg>
  )
}

function metricKeysOf(tab: LibraryTab): readonly string[] {
  return tab === 'strategies'
    ? ['total_return_pct', 'annual_return_pct', 'sharpe_ratio', 'max_drawdown_pct', 'win_rate_pct', 'trade_count']
    : tab === 'factors'
      ? ['ic_mean', 'ir', 'ic_positive_pct', 'n_periods', 'long_short_spread_pct']
      : ['hit_count', 'strategy_count', 'consensus_count', 'top_n']
}

export function RunCompare(props: {
  t: Translate
  tab: LibraryTab
  objectId: string
  /** 已勾选运行的轻量归档（metrics 表直接用）。 */
  runs: readonly Record<string, unknown>[]
  loadRuns: (runIds: readonly string[]) => Promise<Record<string, unknown>[]>
}): React.ReactElement | null {
  const { t, tab, objectId, runs, loadRuns } = props
  const curveTab = tab === 'strategies' || tab === 'factors'
  const idsKey = runs.map(runIdOf).join('|')
  const [fullRuns, setFullRuns] = useState<readonly Record<string, unknown>[] | undefined>(undefined)
  const [curveError, setCurveError] = useState<string | undefined>(undefined)

  // 调用方常传内联箭头（每次渲染新引用）；只按勾选集合变化重新取数。
  const loadRunsRef = useRef(loadRuns)
  loadRunsRef.current = loadRuns
  useEffect(() => {
    if (!curveTab) return
    let active = true
    setFullRuns(undefined)
    setCurveError(undefined)
    loadRunsRef.current(idsKey.split('|')).then((value) => {
      if (active) setFullRuns(value)
    }).catch((error) => {
      if (active) setCurveError(error instanceof Error ? error.message : String(error))
    })
    return () => { active = false }
  }, [curveTab, objectId, idsKey])

  const curveSeries = useMemo<CurveSeries[]>(() => {
    if (fullRuns === undefined) return []
    const versionSet = new Set(fullRuns.map(versionOf))
    const duplicated = versionSet.size !== fullRuns.length
    return fullRuns.map((run, index) => ({
      label: duplicated ? `v${versionOf(run)}·${runIdOf(run).slice(-4)}` : `v${versionOf(run)}`,
      values: tab === 'strategies' ? normalizeEquity(run['equity']) : cumulativeIc(run['ic_series']),
      color: RUN_COLORS[index % RUN_COLORS.length] as string,
    }))
  }, [fullRuns, tab])

  const num = (value: unknown): string => typeof value === 'number' ? String(value) : '—'
  return (
    <div className='kss-compare'>
      <h3 className='kss-group-title'>{t('compare')}（{t('compareHint')}）</h3>
      <table className='kss-table'>
        <thead>
          <tr>
            <th />
            {runs.map((run) => <th key={runIdOf(run)} className='kss-mono'>{runIdOf(run).slice(0, 10)}</th>)}
          </tr>
        </thead>
        <tbody>
          {metricKeysOf(tab).map((key) => (
            <tr key={key}>
              <td className='kss-field-hint'>{key}</td>
              {runs.map((run) => {
                const metrics = typeof run['metrics'] === 'object' && run['metrics'] !== null
                  ? run['metrics'] as Record<string, unknown>
                  : {}
                return <td key={runIdOf(run)}>{num(metrics[key])}</td>
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {curveTab && (curveError !== undefined
        ? <p className='kss-error'>{curveError}</p>
        : fullRuns === undefined
          ? <p className='kss-card-hint'>{t('curveLoading')}</p>
          : curveSeries.some((item) => item.values.length >= 2)
            ? (
                <div className='kss-curve-block'>
                  <h4 className='kss-group-title'>{tab === 'strategies' ? t('curveEquity') : t('curveCumIc')}</h4>
                  <CurveOverlay
                    ariaLabel={tab === 'strategies' ? '净值曲线叠加对比' : '累计 IC 曲线叠加对比'}
                    baseline={tab === 'strategies' ? 1 : 0}
                    baselineLabel={tab === 'strategies' ? '1.00' : '0'}
                    includeBaseline={tab !== 'strategies'}
                    series={curveSeries}
                    unit={tab === 'strategies' ? 'pt' : '期'}
                  />
                </div>
              )
            : <p className='kss-card-hint'>{tab === 'strategies' ? t('curveMissingEquity') : t('curveMissingIc')}</p>)}
    </div>
  )
}
