/** RPC runtime for the 投研工作台 panel: one bounded snapshot state source
 * plus mutation helpers that refresh on completion. Immutable snapshot +
 * listener set — the view wraps it in React state via useSyncExternalStore.
 * 数据面：凭据状态 + 技能目录（设置页）+ 三库列表/详情 + 报告库（工作台，
 * 只读——建库与归档只由 agent 工具完成，KStock 同款纪律）。 */

import { unwrapRpcResult, type ClientRpc, type SaveSecretsResult, type SkillsCatalog, type WorkbenchStatus } from './protocol.ts'

export const RPC_CHANNEL = '/dsh-skills-stock'

export type LibraryTab = 'strategies' | 'factors' | 'selections'
export type WorkbenchTab = LibraryTab | 'reports'
export const LIBRARY_TABS: readonly LibraryTab[] = ['strategies', 'factors', 'selections']
export const WORKBENCH_TABS: readonly WorkbenchTab[] = ['strategies', 'factors', 'selections', 'reports']

/** 绑定后的翻译函数（locale.bind 产物；fallback 见 client/index.tsx）。 */
export type Translate = (key: string, params?: Record<string, unknown>) => string

export type PanelPhase = 'idle' | 'loading' | 'ready' | 'error' | 'unavailable'

export interface LibraryItemView extends Record<string, unknown> {
  readonly object_id: string
  readonly name: string
  readonly status: string
  readonly current_version: number
  readonly updated_at: string
}

export interface LibraryListState {
  readonly loaded: boolean
  readonly items: readonly LibraryItemView[]
}

export interface ReportListState {
  readonly loaded: boolean
  readonly items: readonly Record<string, unknown>[]
}

export interface LibraryDetailView extends Record<string, unknown> {
  readonly object_id: string
  readonly name: string
  readonly status: string
  readonly current_version: number
  readonly versions: readonly Record<string, unknown>[]
  readonly runs: readonly Record<string, unknown>[]
}

export interface PanelState {
  readonly phase: PanelPhase
  readonly status?: WorkbenchStatus
  readonly catalog?: SkillsCatalog
  readonly error?: string | undefined
  readonly refreshedAt?: number | undefined
  readonly saving?: boolean | undefined
  readonly savedKeys?: readonly string[] | undefined
  readonly saveError?: string | undefined
  readonly libraries?: Readonly<Record<LibraryTab, LibraryListState>>
  readonly detail?: { readonly kind: LibraryTab; readonly data: LibraryDetailView } | undefined
  readonly detailLoading?: boolean | undefined
  readonly reports?: ReportListState
  readonly reportDetail?: { readonly data: Record<string, unknown> } | undefined
  readonly reportLoading?: boolean | undefined
}

export interface WorkbenchRuntime {
  readonly source: {
    getSnapshot(): PanelState
    subscribe(listener: () => void): () => void
  }
  refresh(): Promise<void>
  loadLibrary(kind: LibraryTab): Promise<void>
  openDetail(kind: LibraryTab, objectId: string): Promise<void>
  closeDetail(): void
  /** 运行对比：按 run_ids（2-4 个）拉取完整运行归档（含 equity/ic_series 曲线）。 */
  loadRuns(kind: LibraryTab, objectId: string, runIds: readonly string[]): Promise<Record<string, unknown>[]>
  /** 报告库（第四 tab，只读）：列表 + 按 id 拉取 meta 与 HTML 全文。 */
  loadReports(): Promise<void>
  openReport(reportId: string): Promise<void>
  closeReport(): void
  saveSecrets(input: { tushareToken?: string; iwencaiKey?: string }): Promise<SaveSecretsResult>
  clearFeedback(): void
}

export interface WorkbenchRuntimeDeps {
  readonly rpc: ClientRpc
}

/** One observable panel state; identity stays stable for the plugin fiber. */
export function createWorkbenchRuntime(deps: WorkbenchRuntimeDeps): WorkbenchRuntime {
  let state: PanelState = { phase: 'idle' }
  let refreshPromise: Promise<void> | undefined
  const listeners = new Set<() => void>()
  const publish = (next: PanelState): void => {
    state = next
    for (const listener of [...listeners]) listener()
  }
  const patch = (partial: Partial<PanelState>): void => {
    publish({ ...state, ...partial })
  }
  const source = {
    getSnapshot: (): PanelState => state,
    subscribe: (listener: () => void): (() => void) => {
      listeners.add(listener)
      return () => { listeners.delete(listener) }
    },
  }

  const loadLibrary = async (kind: LibraryTab): Promise<void> => {
    const items = unwrapRpcResult<{ items: LibraryItemView[] }>(
      await deps.rpc.call(RPC_CHANNEL, 'library_list', { kind }),
    ).items
    const libraries = state.libraries ?? {
      strategies: { loaded: false, items: [] },
      factors: { loaded: false, items: [] },
      selections: { loaded: false, items: [] },
    }
    patch({ libraries: { ...libraries, [kind]: { loaded: true, items } } })
  }

  const refresh = async (): Promise<void> => {
    if (refreshPromise !== undefined) return refreshPromise
    const previous = { status: state.status, catalog: state.catalog }
    publish(previous.status === undefined && previous.catalog === undefined
      ? { phase: 'loading' }
      : { ...state, phase: 'loading' })
    refreshPromise = (async () => {
      try {
        const [status, catalog] = await Promise.all([
          deps.rpc.call(RPC_CHANNEL, 'status') as Promise<unknown>,
          deps.rpc.call(RPC_CHANNEL, 'skills') as Promise<unknown>,
        ])
        patch({
          phase: 'ready',
          status: unwrapRpcResult<WorkbenchStatus>(status),
          catalog: unwrapRpcResult<SkillsCatalog>(catalog),
          error: undefined,
          refreshedAt: Date.now(),
        })
      } catch (error) {
        patch({
          phase: 'error',
          error: error instanceof Error ? error.message : String(error),
          refreshedAt: Date.now(),
        })
      } finally {
        refreshPromise = undefined
      }
    })()
    return refreshPromise
  }

  return {
    source,
    refresh,
    async loadLibrary(kind) {
      try {
        await loadLibrary(kind)
      } catch (error) {
        const libraries = state.libraries ?? {
          strategies: { loaded: false, items: [] },
          factors: { loaded: false, items: [] },
          selections: { loaded: false, items: [] },
        }
        patch({ libraries: { ...libraries, [kind]: { loaded: true, items: [] } }, error: error instanceof Error ? error.message : String(error) })
      }
    },
    async openDetail(kind, objectId) {
      patch({ detailLoading: true })
      try {
        const data = unwrapRpcResult<LibraryDetailView>(
          await deps.rpc.call(RPC_CHANNEL, 'library_detail', { kind, object_id: objectId }),
        )
        patch({ detail: { kind, data }, detailLoading: false })
      } catch (error) {
        patch({
          detailLoading: false,
          error: error instanceof Error ? error.message : String(error),
        })
      }
    },
    closeDetail() {
      patch({ detail: undefined })
    },
    async loadRuns(kind, objectId, runIds) {
      const value = unwrapRpcResult<{ runs: Record<string, unknown>[] }>(
        await deps.rpc.call(RPC_CHANNEL, 'library_runs', { kind, object_id: objectId, run_ids: [...runIds] }),
      )
      return value.runs
    },
    async loadReports() {
      try {
        const items = unwrapRpcResult<{ items: Record<string, unknown>[] }>(
          await deps.rpc.call(RPC_CHANNEL, 'reports_list', {}),
        ).items
        patch({ reports: { loaded: true, items } })
      } catch (error) {
        patch({ reports: { loaded: true, items: [] }, error: error instanceof Error ? error.message : String(error) })
      }
    },
    async openReport(reportId) {
      patch({ reportLoading: true })
      try {
        const data = unwrapRpcResult<Record<string, unknown>>(
          await deps.rpc.call(RPC_CHANNEL, 'reports_get', { report_id: reportId, content: true }),
        )
        patch({ reportDetail: { data }, reportLoading: false })
      } catch (error) {
        patch({ reportLoading: false, error: error instanceof Error ? error.message : String(error) })
      }
    },
    closeReport() {
      patch({ reportDetail: undefined })
    },
    async saveSecrets(input) {
      patch({ saving: true, saveError: undefined, savedKeys: undefined })
      try {
        const payload: Record<string, string> = {}
        if (input.tushareToken !== undefined && input.tushareToken !== '') payload['TUSHARE_TOKEN'] = input.tushareToken
        if (input.iwencaiKey !== undefined && input.iwencaiKey !== '') payload['IWENCAI_API_KEY'] = input.iwencaiKey
        const value = unwrapRpcResult<SaveSecretsResult>(
          await deps.rpc.call(RPC_CHANNEL, 'save_secrets', payload),
        )
        const pending = refreshPromise
        if (pending !== undefined) await pending.catch(() => undefined)
        await refresh()
        patch({ saving: false, savedKeys: value.saved, saveError: undefined })
        return value
      } catch (error) {
        patch({
          saving: false,
          saveError: error instanceof Error ? error.message : String(error),
        })
        throw error
      }
    },
    clearFeedback() {
      patch({ savedKeys: undefined, saveError: undefined })
    },
  }
}
