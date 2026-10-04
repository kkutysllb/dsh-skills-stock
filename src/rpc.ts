/** Host RPC adapter for the 投研工作台 Web client over the Connection
 * generic-channel registry (`/dsh-skills-stock`). 同 dsh-kylin-automation：
 * Host/Origin + 浏览器认证围栏由 connection.requestRejection 复刻，本适配器
 * 只做负载校验与结果封装；写方向凭据处理见 service.ts 的红线注释。
 */

import type { IncomingMessage, ServerResponse } from 'node:http'
import { ServiceError, SECRET_KEYS, WorkbenchService, type SecretKey } from './service.ts'
import { LibraryError, isLibraryKind, type LibraryStore } from './library.ts'

export const RPC_CHANNEL = '/dsh-skills-stock'

/** Bounded payload shapes keep every handler total. */
const MAX_TOKEN_CHARS = 200

export type RpcResult<T> =
  | { readonly ok: true; readonly value: T }
  | { readonly ok: false; readonly error: { readonly code: string; readonly message: string; readonly details: Record<string, never> } }

function ok<T>(value: T): RpcResult<T> {
  return { ok: true, value }
}

/** details 是宿主连接层客户端 parseConnectionResponse 的必填字段——缺失时
 * 真实错误会在浏览器侧被替换成 "invalid server-response failure"。 */
function fail(code: string, message: string): RpcResult<never> {
  return { ok: false, error: { code, message, details: {} } }
}

function toErrorResult(error: unknown): RpcResult<never> {
  if (error instanceof ServiceError) return fail(error.code, error.message)
  return fail('internal', error instanceof Error ? error.message : String(error))
}

/** JSON body limit for RPC payloads（与 connection 围栏同量级的有界缓存体）。 */
const RPC_BODY_LIMIT_BYTES = 256 * 1024

interface CordisContext {
  connection: { requestRejection(req: IncomingMessage): number | undefined }
  webServer: {
    register(spec: { kind: 'prefix'; path: string; handler(req: IncomingMessage, res: ServerResponse): void }): unknown
  }
  effect(fn: () => () => void, name?: string): unknown
}

/** Register the `/dsh-skills-stock` channel on the caller's injected
 * webServer（直接注册是受支持的路径——vendored connection.rpc.handle() 的
 * route effect 跑在 connection 插件自己的 fiber 上，第三方 patch 行无法
 * 获得 webServer 注入）。服务面：凭据受控写 + 三库只读（写入走 agent
 * 工具，工作台 UI 保持 KStock 的「建库只由 agent 完成」纪律）。 */
export function registerWorkbenchRpc(ctx: CordisContext, service: WorkbenchService, library: LibraryStore): () => void {
  return ctx.effect(() => {
    const registered = ctx.webServer.register({
      kind: 'prefix',
      path: RPC_CHANNEL,
      handler: (req, res) => { void serveRpcRequest(ctx, service, library, req, res) },
    })
    return () => {
      if (typeof registered === 'function') registered()
    }
  }, 'dsh-skills-stock: rpc channel') as unknown as () => void
}

async function serveRpcRequest(
  ctx: CordisContext,
  service: WorkbenchService,
  library: LibraryStore,
  req: IncomingMessage,
  res: ServerResponse,
): Promise<void> {
  const reply = (status: number, payload: unknown): void => {
    res.writeHead(status, { 'content-type': 'application/json', connection: 'close' })
    res.end(JSON.stringify(payload))
  }
  // The same Host/Origin + persistent browser-auth fence the /api route uses.
  const rejection = ctx.connection.requestRejection(req)
  if (rejection !== undefined) {
    res.writeHead(rejection)
    res.end(rejection === 401 ? 'unauthorized' : 'forbidden')
    return
  }
  if (req.method !== 'POST') {
    res.writeHead(405, { 'content-type': 'text/plain' })
    res.end('method not allowed')
    return
  }
  const url = new URL(req.url ?? '/', 'http://dsh.internal')
  const endpoint = url.pathname === RPC_CHANNEL ? '' : url.pathname.startsWith(`${RPC_CHANNEL}/`)
    ? url.pathname.slice(RPC_CHANNEL.length + 1)
    : undefined
  if (endpoint === undefined || !/^[A-Za-z0-9_$.:-]+$/.test(endpoint)) {
    reply(404, { type: 'server-response', rpcId: 'invalid-request', result: fail('not-found', 'unknown endpoint') })
    return
  }
  const contentType = String(req.headers['content-type'] ?? '').split(';')[0]?.trim().toLowerCase()
  if (contentType !== 'application/json') {
    reply(415, { type: 'server-response', rpcId: 'invalid-request', result: fail('invalid', 'content type must be application/json') })
    return
  }
  const declared = req.headers['content-length']
  if (declared !== undefined && Number(declared) > RPC_BODY_LIMIT_BYTES) {
    res.writeHead(413, { connection: 'close' })
    res.end()
    return
  }
  let raw = ''
  const abort = new AbortController()
  res.on('close', () => { if (!res.writableEnded) abort.abort() })
  try {
    let received = 0
    for await (const chunk of req) {
      received += (chunk as Buffer).byteLength
      if (received > RPC_BODY_LIMIT_BYTES) throw new Error('body too large')
      raw += String(chunk)
    }
  } catch {
    res.writeHead(400, { connection: 'close' })
    res.end('body read failure')
    req.destroy()
    return
  }
  let envelope: { type?: unknown; rpcId?: unknown; method?: unknown; payload?: unknown }
  try {
    envelope = JSON.parse(raw) as typeof envelope
  } catch {
    reply(400, { type: 'server-response', rpcId: 'invalid-request', result: fail('invalid', 'body is not JSON') })
    return
  }
  if (envelope?.type !== 'client-request' || typeof envelope.rpcId !== 'string'
    || typeof envelope.method !== 'string') {
    reply(200, {
      type: 'server-response',
      rpcId: typeof envelope?.rpcId === 'string' ? envelope.rpcId : 'invalid-request',
      result: fail('invalid', 'invalid client-request message'),
    })
    return
  }
  if (envelope.method !== endpoint) {
    reply(200, {
      type: 'server-response',
      rpcId: envelope.rpcId,
      result: fail('invalid', `method ${JSON.stringify(envelope.method)} does not match endpoint ${JSON.stringify(endpoint)}`),
    })
    return
  }
  const result = await handleWorkbenchRpc(service, library, envelope.method, envelope.payload, abort.signal)
  reply(200, { type: 'server-response', rpcId: envelope.rpcId, result })
}

/** One endpoint dispatch — exported for direct unit tests. */
export async function handleWorkbenchRpc(
  service: WorkbenchService,
  library: LibraryStore,
  endpoint: string,
  payload: unknown,
  signal: AbortSignal,
): Promise<RpcResult<unknown>> {
  try {
    signal.throwIfAborted()
    if (endpoint === 'status') {
      return ok(service.status())
    }
    if (endpoint === 'skills') {
      return ok(service.skills())
    }
    if (endpoint === 'library_list') {
      const kind = libraryKindOf(payload)
      return ok({ library: kind, items: library.listObjects(kind) })
    }
    if (endpoint === 'library_detail') {
      const kind = libraryKindOf(payload)
      const body = payload as Record<string, unknown>
      const objectId = typeof body['object_id'] === 'string' ? body['object_id'] : ''
      if (!/^[a-z]+_[a-z0-9]+$/i.test(objectId)) return fail('invalid', 'object_id 形如 stg_/fac_/sel_ + 标识后缀')
      return ok(library.detail(kind, objectId))
    }
    if (endpoint === 'library_runs') {
      const kind = libraryKindOf(payload)
      const body = payload as Record<string, unknown>
      const objectId = typeof body['object_id'] === 'string' ? body['object_id'] : ''
      if (!/^[a-z]+_[a-z0-9]+$/i.test(objectId)) return fail('invalid', 'object_id 形如 stg_/fac_/sel_ + 标识后缀')
      const rawIds = body['run_ids']
      if (!Array.isArray(rawIds) || rawIds.length < 2 || rawIds.length > 4) {
        return fail('invalid', 'run_ids 必须是 2-4 个 run_id 的数组（与工作台对比勾选上限一致）')
      }
      const runIds: string[] = []
      for (const id of rawIds) {
        // 字符集白名单同时堵住路径穿越（runId 会拼进 runs/ 下的文件名）
        if (typeof id !== 'string' || !/^[a-z]+_[a-z0-9]+$/i.test(id)) {
          return fail('invalid', 'run_id 形如 srun_/frun_/xrun_ + 标识后缀')
        }
        if (!runIds.includes(id)) runIds.push(id)
      }
      return ok({ library: kind, object_id: objectId, runs: library.runsByIds(kind, objectId, runIds) })
    }
    if (endpoint === 'save_secrets') {
      if (typeof payload !== 'object' || payload === null) return fail('invalid', 'payload must be an object')
      const body = payload as Record<string, unknown>
      const updates: Partial<Record<SecretKey, string>> = {}
      for (const key of SECRET_KEYS) {
        const value = body[key]
        if (value === undefined || value === null) continue
        if (typeof value !== 'string') return fail('invalid', `${key} must be a string`)
        if (value.trim() !== value) return fail('invalid', `${key} must not have surrounding whitespace`)
        if (value.length > MAX_TOKEN_CHARS) return fail('invalid', `${key} exceeds ${MAX_TOKEN_CHARS} chars`)
        if (/[\r\n#]/.test(value)) return fail('invalid', `${key} contains forbidden characters`)
        if (value.trim() === '') return fail('invalid', `${key} must not be empty（留空表示保持不变，请直接省略该字段）`)
        updates[key] = value
      }
      return ok(service.saveSecrets(updates))
    }
    return fail('not-found', `unknown endpoint ${JSON.stringify(endpoint)}`)
  } catch (error) {
    if (error instanceof LibraryError) return fail(error.code, error.message)
    return toErrorResult(error)
  }
}

function libraryKindOf(payload: unknown): 'strategies' | 'factors' | 'selections' {
  const body = typeof payload === 'object' && payload !== null ? payload as Record<string, unknown> : {}
  const kind = body['kind']
  if (!isLibraryKind(kind)) throw new LibraryError('invalid', 'kind 必须是 strategies / factors / selections 之一')
  return kind
}
