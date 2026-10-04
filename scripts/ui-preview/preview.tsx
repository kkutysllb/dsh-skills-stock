/** 独立预览支架（仅开发自查用，不进包）：真实挂载 WorkbenchView +
 * 假 RPC 数据，宿主 design token 用深色桩值模拟，验证卡片风格对齐。
 * 构建：node scripts/build.mjs 后
 *   esbuild scripts/ui-preview/preview.tsx --bundle --outfile=/tmp/kss-preview/main.js
 *   （external 无——react 打进去，页面完全自包含）
 */

import { createRoot } from 'react-dom/client'
import { createElement as h, useEffect } from 'react'
import { installStyles } from '../../src/client/styles.ts'
import { WorkbenchView } from '../../src/client/WorkbenchView.tsx'
import { createWorkbenchRuntime, type Translate } from '../../src/client/runtime.ts'
import { zh } from '../../src/client/locales.ts'
import type { ConversationBridge } from '../../src/client/bridge.ts'

// ── 深色宿主 token 桩（与 dsh 桌面端 dark 主题同值的别名子集） ──────────
const TOKENS: Record<string, string> = {
  '--dsw-alias-bg-base': '#101114',
  '--dsw-alias-label-primary': '#ececf1',
  '--dsw-alias-label-secondary': '#c0c5cd',
  '--dsw-alias-label-tertiary': '#9aa0aa',
  '--dsw-specific-sidebar-fill': 'rgba(127,127,127,.08)',
  '--dsw-alias-interactive-bg-hover': 'rgba(127,127,127,.1)',
  '--dsw-alias-border-l2': '#55555c',
  '--dsw-alias-border-l3': '#2c2f36',
  '--dsw-alias-border-l4': 'rgba(127,127,127,.48)',
  '--dsw-alias-button-primary-fill': '#f5f5f5',
  '--dsw-alias-button-primary-hover': '#e8e8e8',
  '--dsw-alias-label-primary-foreground': '#141518',
  '--dsw-alias-state-business-primary': '#4c6ef5',
  '--dsw-alias-state-success-primary': '#2f9e6e',
  '--dsw-alias-state-warn-primary': '#d9a514',
  '--dsw-alias-state-error-primary': '#d64545',
}
for (const [k, v] of Object.entries(TOKENS)) document.documentElement.style.setProperty(k, v)
document.body.style.cssText = 'margin:0;background:#101114;'

const t: Translate = (key, params) => {
  const template = zh[key as keyof typeof zh] ?? String(key)
  if (params === undefined) return template
  return template.replace(/\{(\w+)\}/g, (_m, name: string) => String(params[name] ?? `{${name}}`))
}

const daysAgo = (n: number): string => new Date(Date.now() - n * 86_400_000).toISOString()

const strategyRun = (id: string, ret: number, sharpe: number, when: number) => ({
  run_id: id,
  version: 1,
  created_at: daysAgo(when),
  metrics: { total_return_pct: ret, sharpe_ratio: sharpe, max_drawdown_pct: -14.2 },
})

const rpc = async (channel: string, endpoint: string, payload?: unknown): Promise<unknown> => {
  if (endpoint === 'status') {
    return { ok: true, value: { stockHome: '/Users/libing/.dsh/dsh-skills-stock', secretsPath: '/Users/libing/.dsh/dsh-skills-stock/secrets.env', secretsExists: true, secretsWritable: true, keys: { TUSHARE_TOKEN: true, IWENCAI_API_KEY: false }, skillCount: 41 } }
  }
  if (endpoint === 'skills') {
    return { ok: true, value: { skills: [{ name: 'stock-analysis', description: 'A股个股十四维一体深度分析引擎' }, { name: 'html-report', description: '研究报告看板生成与归档' }] } }
  }
  if (endpoint === 'library_list') {
    const kind = (payload as { kind: string }).kind
    if (kind === 'strategies') {
      return { ok: true, value: { items: [
        { object_id: 'stg_a1b2c3', name: '双均线趋势', status: 'researching', current_version: 3, updated_at: daysAgo(1), hypothesis: '20日上穿60日做多，A股日线趋势跟随', latest_run: strategyRun('srun_x1', 32.5, 1.21, 1) },
        { object_id: 'stg_d4e5f6', name: '高股息低波红利', status: 'paused', current_version: 2, updated_at: daysAgo(6), hypothesis: '股息率+低波动双因子红利组合', latest_run: strategyRun('srun_x2', 12.8, 0.94, 5) },
      ] } }
    }
    return { ok: true, value: { items: [] } }
  }
  if (endpoint === 'library_detail') {
    return { ok: true, value: {
      object_id: 'stg_a1b2c3', name: '双均线趋势', status: 'researching', current_version: 3,
      hypothesis: '20日上穿60日做多，A股日线趋势跟随',
      versions: [
        { version: 1, created_at: daysAgo(30), change_note: '初版：20/60 双均线' },
        { version: 2, created_at: daysAgo(12), change_note: '加止损：ATR 2 倍吊灯止损' },
        { version: 3, created_at: daysAgo(1), change_note: '费率口径修正为万 2.5 双边' },
      ],
      runs: [strategyRun('srun_9a2b4c', 26.4, 1.05, 12), strategyRun('srun_7d8e9f', 32.5, 1.21, 1)],
    } }
  }
  if (endpoint === 'reports_list') {
    return { ok: true, value: { items: [
      { report_id: 'rpt_a1b2c3d4e5f6', title: '贵州茅台尽调看板', symbol: '600519.SH', report_type: 'analysis', generated_at: daysAgo(0), updated_at: daysAgo(0), risk_level: '中', coverage_status: 'complete', size_bytes: 186_400 },
      { report_id: 'rpt_b2c3d4e5f6a1', title: '全市场双低转债扫描', report_type: 'screening', generated_at: daysAgo(2), updated_at: daysAgo(2), risk_level: '低', coverage_status: 'complete', size_bytes: 94_120 },
    ] } }
  }
  if (endpoint === 'reports_get') {
    return { ok: true, value: {
      report_id: 'rpt_a1b2c3d4e5f6', title: '贵州茅台尽调看板', symbol: '600519.SH', report_type: 'analysis',
      generated_at: daysAgo(0), period_start: '2025-10-01', period_end: '2026-09-30', risk_level: '中',
      coverage_status: 'complete', size_bytes: 186_400,
      content: '<body style="margin:0;font-family:system-ui;background:#141518;color:#ececf1;padding:28px"><h2 style="margin:0 0 8px">贵州茅台尽调看板（预览桩）</h2><p style="color:#9aa0aa">单文件自包含 HTML 看板内嵌预览……</p><svg width="420" height="120"><polyline points="0,100 60,80 120,86 180,60 240,52 300,30 360,24 420,10" fill="none" stroke="#4c6ef5" stroke-width="2"/></svg></body>',
    } }
  }
  return { ok: false, error: { code: 'not-found', message: `preview stub: ${channel} ${endpoint}`, details: {} } }
}

const runtime = createWorkbenchRuntime({ rpc: { call: rpc } })
const bridge: ConversationBridge = { send: async () => 'submitted' } as unknown as ConversationBridge

function Preview(): React.ReactElement {
  useEffect(() => { installStyles() }, [])
  return h('div', { style: { height: '100vh', overflow: 'auto' } },
    h(WorkbenchView, { t, runtime, bridge }),
  )
}

createRoot(document.getElementById('root')!).render(h(Preview, null))
