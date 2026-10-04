/** Client-side service faces（对齐 dsh-kylin-automation contracts.ts 的窄类型
 * 风格）：只声明本插件实际用到的方法，宿主实现由 dsh.client.inject 的
 * 官方包提供。 */

export interface SlotSpec {
  readonly name: string
  readonly id?: string
  readonly key?: string
  readonly order?: number
  readonly label?: () => string
  readonly locale?: string
}

export interface SlotsService {
  inject(slot: string, factory: () => () => void): void
  register(spec: SlotSpec, render: (props: { size?: number }) => unknown): () => void
}

export interface LocaleService {
  register?(ns: string, dictionaries: { zh: Record<string, string>; en: Record<string, string> }): () => void
  bind?(ns: string): (key: string, params?: Record<string, unknown>) => string
}

export interface LayoutService {
  selectPanel(panelId: string | null): void
}

export interface ConnectionService {
  rpc: {
    call(channel: string, endpoint: string, payload?: unknown): Promise<unknown>
  }
}

/** 会话/工作区服务面（会话桥使用；与宿主 shells 对齐的最窄声明）。 */
export interface SessionsService {
  list?: { getSnapshot(): { current?: string | undefined } }
  create?(): Promise<string>
  open?(sessionId: string): void
  scope(sessionId: string): {
    conversation?: {
      input?: {
        for(actx: unknown): InputShell | null
      }
    }
  } | undefined
}

/** 输入 shell（写入 + 提交；setDraft/submit 均为可选能力探测）。 */
export interface InputShell {
  setDraft?(text: string): void
  submit?(): void
}

/** 根 conversation 服务面（宿主 ≥0.1.6 公开：input registry，优先于
 * 旧 scope(id).conversation 路径；由 dsh-client-ui-conversation 提供）。 */
export interface ConversationService {
  input?: {
    shell?(sessionId: string): InputShell | null
    for?(actx: unknown): InputShell | null
  }
}

export interface UiWorkspaceService {
  openWorkspace(workspaceId: string): unknown
}

export interface WorkspacesService {
  list?: { getSnapshot(): { items?: Array<{ workspaceId?: string; sessionIds?: string[] }> } }
}

/** apply(ctx) 收到的客户端上下文面。 */
export interface ClientContext {
  slots?: SlotsService
  locale?: LocaleService
  layout?: LayoutService
  connection?: ConnectionService
  sessions?: SessionsService
  /** 根 conversation 服务：宿主 ≥0.1.6 经 inject('conversation') 注入；
   * 旧宿主缺席时为 undefined（会话桥走旧作用域路径）。 */
  conversation?: ConversationService
  uiWorkspace?: UiWorkspaceService
  workspaces?: WorkspacesService
  effect(fn: () => () => void, name?: string): () => void
  /** cordis ctx.get：按服务名取根服务（conversation 等注入面）。 */
  get?(name: string): unknown
}

