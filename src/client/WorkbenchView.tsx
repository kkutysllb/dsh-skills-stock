/** 投研工作台主面板：策略库 / 因子库 / 选股库 / 报告库四个 tab + 会话桥任务入口。
 * 工作台是「dsh agent 能力」的作业界面：库内容由 agent 会话经
 * strategy_* / factor_* / selection_* / report_* 工具登记归档（面板只读），
 * 「新建研究任务 / 重跑本版本」把预填 prompt 投递到会话（submit，剪贴板
 * 降级），形成 KStock 同款闭环：agent 入库 → 面板查看时间线/运行对比/
 * 报告看板 → 一键重跑迭代。 */

import { useEffect, useState, useSyncExternalStore } from 'react'
import type { LibraryTab, WorkbenchTab, LibraryListState, ReportListState, LibraryDetailView, Translate, WorkbenchRuntime } from './runtime.ts'
import { LIBRARY_TABS, WORKBENCH_TABS } from './runtime.ts'
import type { PanelState } from './runtime.ts'
import type { ConversationBridge } from './bridge.ts'
import { RunCompare } from './RunCompare.tsx'
import { NotesCard } from './SettingsView.tsx'

export interface WorkbenchViewProps {
  readonly t: Translate
  readonly runtime: WorkbenchRuntime
  readonly bridge: ConversationBridge
}

const TAB_LABEL: Record<WorkbenchTab, string> = {
  strategies: 'tabStrategies',
  factors: 'tabFactors',
  selections: 'tabSelections',
  reports: 'tabReports',
}

const TOOL_PREFIX: Record<LibraryTab, string> = {
  strategies: 'strategy',
  factors: 'factor',
  selections: 'selection',
}

function usePanelState(runtime: WorkbenchRuntime): PanelState {
  return useSyncExternalStore(runtime.source.subscribe, runtime.source.getSnapshot, runtime.source.getSnapshot)
}

function str(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function num(value: unknown): string {
  return typeof value === 'number' ? String(value) : '—'
}

function isLibraryTab(tab: WorkbenchTab): tab is LibraryTab {
  return (LIBRARY_TABS as readonly string[]).includes(tab)
}

export function WorkbenchView(props: WorkbenchViewProps): React.ReactElement {
  const { t, runtime, bridge } = props
  const state = usePanelState(runtime)
  const [tab, setTab] = useState<WorkbenchTab>('strategies')
  const [deliverNote, setDeliverNote] = useState<string | undefined>(undefined)

  useEffect(() => { void runtime.refresh() }, [runtime])
  useEffect(() => {
    if (tab === 'reports') void runtime.loadReports()
    else void runtime.loadLibrary(tab)
  }, [runtime, tab])
  useEffect(() => () => { runtime.closeDetail(); runtime.closeReport() }, [runtime])

  if (state.phase === 'error' && state.status === undefined) {
    return (
      <div className='kss-panel'>
        <div className='kss-state'>
          <span>{t('errorLoad')}</span>
          <span className='kss-error'>{state.error}</span>
          <button type='button' className='kss-btn' onClick={() => { void runtime.refresh() }}>{t('retry')}</button>
        </div>
      </div>
    )
  }

  const libraries = state.libraries
  const reportList: ReportListState = state.reports ?? { loaded: false, items: [] }
  const reportDetail = state.reportDetail?.data
  const list: LibraryListState = isLibraryTab(tab)
    ? (libraries?.[tab] ?? { loaded: false, items: [] })
    : { loaded: false, items: [] }
  const detail = state.detail?.kind === tab && isLibraryTab(tab) ? state.detail.data : undefined

  const deliver = (text: string): void => {
    void bridge.send(text).then((result) => {
      setDeliverNote(result === 'submitted' ? undefined : result === 'copied' ? t('sendFailed') : t('sendFailed'))
      setTimeout(() => setDeliverNote(undefined), 4000)
    })
  }

  return (
    <div className='kss-panel'>
      <header className='kss-header'>
        <div>
          <h1 className='kss-title'>{t('title')}</h1>
          <p className='kss-subtitle'>{t('subtitle')}</p>
        </div>
        <div className='kss-badges'>
          <button type='button' className='kss-btn' onClick={() => {
            void runtime.refresh()
            if (tab === 'reports') void runtime.loadReports()
            else void runtime.loadLibrary(tab)
          }}>
            {state.phase === 'loading' ? t('refreshing') : t('refresh')}
          </button>
        </div>
      </header>

      <div className='kss-tabs'>
        {WORKBENCH_TABS.map((kind) => (
          <button
            key={kind}
            type='button'
            className={`kss-tab ${tab === kind ? 'is-active' : ''}`}
            onClick={() => { runtime.closeDetail(); runtime.closeReport(); setTab(kind) }}
          >
            {t(TAB_LABEL[kind])}
          </button>
        ))}
        <span className='kss-tabs-spacer' />
        <button
          type='button'
          className='kss-btn is-primary'
          onClick={() => { deliver(t('researchTaskPrompt', { label: t(TAB_LABEL[tab]) })) }}
        >
          {t('newResearch')}
        </button>
      </div>
      {deliverNote !== undefined && <p className='kss-feedback is-warn'>{deliverNote}</p>}

      {tab === 'reports' ? (
        reportDetail !== undefined
          ? <ReportDetailViewPane t={t} runtime={runtime} detail={reportDetail} />
          : <ReportListTab t={t} runtime={runtime} list={reportList} />
      ) : detail === undefined ? (
        <LibraryListTab t={t} runtime={runtime} tab={tab} list={list} />
      ) : (
        <LibraryDetailViewPane
          t={t}
          runtime={runtime}
          tab={tab}
          detail={detail}
          bridge={bridge}
        />
      )}

      <NotesCard t={t} />
    </div>
  )
}

function LibraryListTab(props: {
  t: Translate
  runtime: WorkbenchRuntime
  tab: LibraryTab
  list: LibraryListState
}): React.ReactElement {
  const { t, runtime, tab, list } = props
  if (!list.loaded) return <div className='kss-state'>{t('refreshing')}</div>
  if (list.items.length === 0) return <p className='kss-card-hint'>{t('emptyLibrary')}</p>
  return (
    <div className='kss-grid'>
      {list.items.map((item) => (
        <article key={item.object_id} className='kss-skill'>
          <div className='kss-skill-head'>
            <span className='kss-skill-name'>{str(item['name'])}</span>
            <button
              type='button'
              className='kss-skill-copy'
              onClick={() => { void runtime.openDetail(tab, item.object_id) }}
            >
              {t('openDetail')}
            </button>
          </div>
          <p className='kss-skill-desc'>
            {str(item['hypothesis']) !== '' ? str(item['hypothesis']) : str(item['criteria'])}
          </p>
          <div className='kss-skill-meta'>
            <span className={`kss-badge ${str(item['status']) === 'researching' || str(item['status']) === 'watching' ? 'is-ok' : 'is-miss'}`}>
              {str(item['status'])}
            </span>
            <span className='kss-field-hint'>v{num(item['current_version'])}</span>
            {item['latest_run'] !== undefined && (
              <span className='kss-field-hint'>{summarizeRun(item['latest_run'])}</span>
            )}
          </div>
        </article>
      ))}
    </div>
  )
}

function summarizeRun(latestRun: unknown): string {
  if (typeof latestRun !== 'object' || latestRun === null) return ''
  const run = latestRun as Record<string, unknown>
  const metrics = typeof run['metrics'] === 'object' && run['metrics'] !== null
    ? run['metrics'] as Record<string, unknown>
    : {}
  const parts: string[] = []
  if (typeof metrics['total_return_pct'] === 'number') parts.push(`收益 ${metrics['total_return_pct']}%`)
  if (typeof metrics['sharpe_ratio'] === 'number') parts.push(`夏普 ${metrics['sharpe_ratio']}`)
  if (typeof metrics['ic_mean'] === 'number') parts.push(`IC ${metrics['ic_mean']}`)
  if (typeof metrics['hit_count'] === 'number') parts.push(`命中 ${metrics['hit_count']}`)
  return parts.join(' · ')
}

function LibraryDetailViewPane(props: {
  t: Translate
  runtime: WorkbenchRuntime
  tab: LibraryTab
  detail: LibraryDetailView
  bridge: ConversationBridge
}): React.ReactElement {
  const { t, runtime, tab, detail, bridge } = props
  const [checked, setChecked] = useState<string[]>([])
  const versions = detail.versions ?? []
  const runs = detail.runs ?? []

  const rerunPrompt = (version: number): string => t('rerunPrompt', {
    library: t(TAB_LABEL[tab]),
    name: detail.name,
    object_id: detail.object_id,
    toolPrefix: TOOL_PREFIX[tab],
    version,
    label: t(TAB_LABEL[tab]),
  })

  const toggleRun = (runId: string): void => {
    setChecked((prev) => prev.includes(runId)
      ? prev.filter((id) => id !== runId)
      : prev.length >= 4 ? prev : [...prev, runId])
  }

  return (
    <section className='kss-card'>
      <div className='kss-skill-head'>
        <button type='button' className='kss-btn' onClick={() => { runtime.closeDetail() }}>{t('backToList')}</button>
        <span className='kss-skill-name'>{detail.name}</span>
        <span className='kss-badge'>{detail.status}</span>
        <span className='kss-field-hint'>v{detail.current_version}</span>
        <span className='kss-tabs-spacer' />
        <button type='button' className='kss-btn is-primary' onClick={() => { bridge.send(rerunPrompt(detail.current_version)) }}>
          {t('rerun')}
        </button>
      </div>
      {(detail.hypothesis !== undefined || detail.criteria !== undefined) && (
        <p className='kss-card-hint'>{detail.hypothesis !== undefined ? `${t('hypothesis')}：${detail.hypothesis}` : `${t('criteria')}：${detail.criteria}`}</p>
      )}

      <h3 className='kss-group-title'>{t('versions')}</h3>
      <div className='kss-versions'>
        {[...versions].reverse().map((version) => {
          const v = typeof version['version'] === 'number' ? version['version'] : 0
          return (
            <div key={v} className='kss-version-row'>
              <span className='kss-version-tag'>v{v}</span>
              <span className='kss-field-hint'>{str(version['created_at']).slice(0, 16).replace('T', ' ')}</span>
              <span className='kss-skill-desc'>{str(version['change_note'])}</span>
              {v === detail.current_version && <span className='kss-badge is-ok'>{t('latest')}</span>}
              <span className='kss-tabs-spacer' />
              <button type='button' className='kss-skill-copy' onClick={() => { bridge.send(rerunPrompt(v)) }}>
                {t('rerun')}
              </button>
            </div>
          )
        })}
      </div>

      <h3 className='kss-group-title'>{t('runs')}</h3>
      {runs.length === 0 ? (
        <p className='kss-card-hint'>{t('noRuns', { label: t(TAB_LABEL[tab]) })}</p>
      ) : (
        <table className='kss-table'>
          <thead>
            <tr>
              <th />
              <th>run</th>
              <th>v</th>
              <th>{metricsHeaderLabel(tab)}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => {
              const runId = str(run['run_id'])
              return (
                <tr key={runId}>
                  <td>
                    <input
                      type='checkbox'
                      aria-label={runId}
                      checked={checked.includes(runId)}
                      onChange={() => { toggleRun(runId) }}
                    />
                  </td>
                  <td className='kss-mono'>{runId.slice(0, 10)}</td>
                  <td>v{num(run['version'])}</td>
                  <td>{summarizeRun(run)}</td>
                  <td>{str(run['created_at']).slice(0, 16).replace('T', ' ')}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
      {checked.length >= 2 && (
        <RunCompare
          t={t}
          tab={tab}
          objectId={detail.object_id}
          runs={runs.filter((run) => checked.includes(str(run['run_id'])))}
          loadRuns={(ids) => runtime.loadRuns(tab, detail.object_id, ids)}
        />
      )}
    </section>
  )
}

function metricsHeaderLabel(tab: LibraryTab): string {
  return tab === 'strategies' ? '收益/夏普' : tab === 'factors' ? 'IC/IR' : '命中'
}

/* ── 报告库（第四 tab，只读）：列表 + 内嵌 HTML 看板预览 ─────────────────── */

function formatBytes(bytes: unknown): string {
  if (typeof bytes !== 'number' || !Number.isFinite(bytes)) return '—'
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${bytes} B`
}

function ReportListTab(props: {
  t: Translate
  runtime: WorkbenchRuntime
  list: ReportListState
}): React.ReactElement {
  const { t, runtime, list } = props
  if (!list.loaded) return <div className='kss-state'>{t('refreshing')}</div>
  if (list.items.length === 0) return <p className='kss-card-hint'>{t('emptyReports')}</p>
  return (
    <div className='kss-grid'>
      {list.items.map((item) => (
        <article key={str(item['report_id'])} className='kss-skill'>
          <div className='kss-skill-head'>
            <span className='kss-skill-name'>{str(item['title'])}</span>
            <button
              type='button'
              className='kss-skill-copy'
              onClick={() => { void runtime.openReport(str(item['report_id'])) }}
            >
              {t('openDetail')}
            </button>
          </div>
          <p className='kss-skill-desc'>
            {str(item['symbol']) !== '' ? `${str(item['symbol'])} · ` : ''}{str(item['report_type'])}
            {str(item['coverage_status']) === 'partial' ? ' · 数据部分覆盖' : ''}
          </p>
          <div className='kss-skill-meta'>
            {str(item['risk_level']) !== '' && (
              <span className={`kss-badge ${str(item['risk_level']) === '高' ? 'is-miss' : 'is-ok'}`}>
                {t('reportRisk')} {str(item['risk_level'])}
              </span>
            )}
            <span className='kss-field-hint'>{formatBytes(item['size_bytes'])}</span>
            <span className='kss-field-hint'>{str(item['updated_at']).slice(0, 16).replace('T', ' ')}</span>
          </div>
        </article>
      ))}
    </div>
  )
}

function ReportDetailViewPane(props: {
  t: Translate
  runtime: WorkbenchRuntime
  detail: Record<string, unknown>
}): React.ReactElement {
  const { t, runtime, detail } = props
  const content = str(detail['content'])
  const openInNewWindow = (): void => {
    try {
      const url = URL.createObjectURL(new Blob([content], { type: 'text/html' }))
      window.open(url, '_blank', 'noopener')
    } catch {
      // 弹窗被宿主拦截时保留内嵌预览
    }
  }
  return (
    <section className='kss-card'>
      <div className='kss-skill-head'>
        <button type='button' className='kss-btn' onClick={() => { runtime.closeReport() }}>{t('backToList')}</button>
        <span className='kss-skill-name'>{str(detail['title'])}</span>
        {str(detail['symbol']) !== '' && <span className='kss-badge'>{str(detail['symbol'])}</span>}
        <span className='kss-field-hint'>{formatBytes(detail['size_bytes'])}</span>
        <span className='kss-tabs-spacer' />
        <button type='button' className='kss-btn is-primary' onClick={openInNewWindow}>{t('reportOpenNew')}</button>
      </div>
      <p className='kss-card-hint'>
        {str(detail['report_type'])} · {str(detail['generated_at']).slice(0, 16).replace('T', ' ')}
        {str(detail['period_start']) !== '' ? ` · ${str(detail['period_start'])} ~ ${str(detail['period_end'])}` : ''}
        {str(detail['risk_level']) !== '' ? ` · ${t('reportRisk')} ${str(detail['risk_level'])}` : ''}
      </p>
      <h3 className='kss-group-title'>{t('reportPreview')}</h3>
      {content === '' ? (
        <p className='kss-card-hint'>{t('reportNoContent')}</p>
      ) : (
        <iframe
          className='kss-report-frame'
          title={str(detail['title']) || t('reportPreview')}
          srcDoc={content}
          sandbox=''
        />
      )}
    </section>
  )
}
