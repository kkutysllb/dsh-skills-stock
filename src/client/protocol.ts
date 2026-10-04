/** JSON contract shared conceptually with the dsh-skills-stock Host RPC
 * adapter. Self-contained: no host-module imports, so the client bundle stays
 * free of host-only dependencies. */

export interface WorkbenchStatus {
  readonly stockHome: string
  readonly secretsPath: string
  readonly secretsExists: boolean
  readonly secretsWritable: boolean
  readonly keys: Readonly<Record<'TUSHARE_TOKEN' | 'IWENCAI_API_KEY', boolean>>
  readonly skillCount: number
}

export interface SkillEntry {
  readonly name: string
  readonly description: string
  readonly whenToUse?: string
  readonly category?: string
  readonly requiredSecrets?: readonly string[]
}

export interface SkillsCatalog {
  readonly skills: readonly SkillEntry[]
}

export interface SaveSecretsResult {
  readonly saved: readonly string[]
}

/** 三库列表项（host library_list 投影，字段沿袭 KStock）。 */
export type LibraryItem = Record<string, unknown>

/** 三库详情（object + versions + runs）。 */
export interface LibraryDetail {
  readonly object_id: string
  readonly name: string
  readonly status: string
  readonly current_version: number
  readonly hypothesis?: string
  readonly criteria?: string
  readonly category?: string
  readonly versions: readonly Record<string, unknown>[]
  readonly runs: readonly Record<string, unknown>[]
}

export type RpcResult<T> =
  | { readonly ok: true; readonly value: T }
  | { readonly ok: false; readonly error: { readonly code: string; readonly message: string; readonly details?: Record<string, unknown> } }

export type ClientRpc = {
  call(channel: string, endpoint: string, payload?: unknown): Promise<unknown>
}

/** Unwrap the {ok, value}/{ok, error} server envelope into a value or throw. */
export function unwrapRpcResult<T>(response: unknown): T {
  const typed = response as RpcResult<T> | undefined
  if (typed !== undefined && typed !== null && typeof typed === 'object' && 'ok' in typed) {
    if (typed.ok === true) return typed.value
    throw new Error(typed.error?.message ?? String(typed.error?.code ?? 'rpc failed'))
  }
  throw new Error('投研工作台通道返回了无法识别的结果 (unexpected rpc result shape)')
}
