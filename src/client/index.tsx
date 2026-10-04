/** Client entry: three official slots —
 * 1. `sidebar.panellist` + `main` keyed：投研工作台（策略库/因子库/选股库
 *    三个 tab，agent 会话入库、面板只读 + 会话桥重跑）；
 * 2. `settings.section`：设置页「数据源」凭据配置（super-ppts 同款挂载）。
 * The shell owns buttons, active state, and panel switching; this plugin
 * contributes glyphs and pages — no DOM-hacked entries, no routing hacks.
 *
 * Contract: this bundle is consumed through the client module table (esbuild
 * CJS output wrapped by the build script in window.__ModuleLoader__.load),
 * `exports.inject` names the Cordis client services, and `exports.apply(ctx)`
 * registers everything inside ctx.effect-managed lifecycles.
 */

import { WorkbenchView } from './WorkbenchView.tsx'
import { DataSourcesSettingsView } from './SettingsView.tsx'
import type { ClientContext } from './contracts.ts'
import { createConversationBridge } from './bridge.ts'
import { dictionaries, NS, zh } from './locales.ts'
import { createWorkbenchRuntime, type Translate, type WorkbenchRuntime } from './runtime.ts'
import { installStyles } from './styles.ts'

export const name = 'dsh-skills-stock'

/** Services this client plugin composes against; each is provided by a
 * dsh.client.inject package row in the roster. */
export const inject = [
  'slots',
  'locale',
  'layout',
  'connection',
  'sessions',
  'conversation',
  'uiWorkspace',
  'workspaces',
] as const

/** Main panel id — shared by the panellist entry and the keyed main entry. */
const PANEL_ID = 'kss-workbench'

function bindTranslator(ctx: ClientContext): Translate {
  const localeService = ctx.locale
  if (localeService?.register !== undefined) {
    ctx.effect(() => localeService.register!(NS, { zh: { ...zh }, en: { ...dictionaries.en } }), 'kss: dictionaries')
  }
  return localeService?.bind !== undefined
    ? localeService.bind(NS)
    : (key: string, params?: Record<string, unknown>): string => {
      const template = zh[key as keyof typeof zh] ?? key
      if (params === undefined) return template
      return template.replace(/\{(\w+)\}/g, (_match, name: string) => String(params[name] ?? `{${name}}`))
    }
}

function createRuntime(ctx: ClientContext): WorkbenchRuntime {
  return createWorkbenchRuntime({
    rpc: {
      call: (channel, endpoint, payload) => {
        if (ctx.connection?.rpc === undefined) {
          return Promise.reject(new Error('投研工作台通道不可用 (the workbench channel is unavailable)'))
        }
        return ctx.connection.rpc.call(channel, endpoint, payload)
      },
    },
  })
}

/** Client plugin entry. */
export function apply(ctx: ClientContext): void {
  const disposeStyles = installStyles()
  const t = bindTranslator(ctx)
  const runtime = createRuntime(ctx)
  const bridge = createConversationBridge(ctx)

  // ── sidebar menu entry + independent main panel (official slots) ──────────
  if (ctx.slots?.inject !== undefined) {
    try {
      ctx.slots.inject('sidebar.panellist', () => {
        const disposeIcon = ctx.slots!.register({
          name: 'sidebar.panellist',
          id: PANEL_ID,
          order: 125,
          label: () => t('nav'),
          locale: NS,
        }, PanelIcon)
        const disposePanel = ctx.slots!.register({
          name: 'main',
          key: PANEL_ID,
          locale: NS,
        }, function WorkbenchMount(): React.ReactElement {
          return <WorkbenchView t={t} runtime={runtime} bridge={bridge} />
        })
        return () => {
          disposePanel()
          disposeIcon()
        }
      })
    } catch (error) {
      // Hosts without these slots stay usable through the Agent tools only.
      console.warn('[dsh-skills-stock] sidebar/main slot registration skipped:', error)
    }

    // ── settings section: 数据源凭据配置（super-ppts 同款官方 slot）─────────
    try {
      ctx.slots.inject('settings.section', () =>
        ctx.slots!.register(
          { name: 'settings.section', id: 'kstock-data-sources', order: 20, label: () => t('navDataSources'), locale: NS },
          function DataSourcesMount(): React.ReactElement {
            return <DataSourcesSettingsView t={t} runtime={runtime} />
          },
        ))
    } catch (error) {
      console.warn('[dsh-skills-stock] settings.section slot registration skipped:', error)
    }
  }

  ctx.effect(() => disposeStyles, 'kss: styles')
}

/** Sidebar glyph: candlestick chart (A 股投研). */
function PanelIcon(props: { size?: number }): React.ReactElement {
  const size = props.size ?? 18
  return (
    <svg
      width={size}
      height={size}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth={1.9}
      strokeLinecap='round'
      strokeLinejoin='round'
      aria-hidden='true'
    >
      <path d='M4 4v16' />
      <path d='M20 4v16' />
      <path d='M8 8.5h3' />
      <path d='M9.5 6.5v7' />
      <path d='M13 11h3' />
      <path d='M14.5 9v7' />
      <path d='M3 20h18' />
    </svg>
  )
}

export { createWorkbenchRuntime } from './runtime.ts'
