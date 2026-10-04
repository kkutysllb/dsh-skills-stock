/** 策略库 / 因子库 / 选股库 的文件型存储（dsh 适配 KStock 三库同构模型）。
 *
 * KStock 原型：~/.kstock/product/ 下 SQLite 索引 + 版本链文件 + 运行归档，
 * agent 经 15 个 *_store 工具强制版本纪律（乐观锁 + 容量上限），UI 只读 +
 * 「重跑本版本」。dsh 版保持同一领域语义，存储简化为纯 JSON 文件
 * （单机单用户；文件形态对 agent 的 fs 工具天然可读）：
 *
 *   ~/.dsh-stock/product/<kind>/<objId>/object.json      身份（含 current_version）
 *   ~/.dsh-stock/product/<kind>/<objId>/versions/vNNN.json  版本快照
 *   ~/.dsh-stock/product/<kind>/<objId>/runs/<runId>.json   运行归档
 *
 * 纪律（沿袭 KStock）：
 * - 写入只走 agent 工具（Web UI 只读），版本号单调递增，parent_version
 *   必须等于当前版本（否则版本冲突）；
 * - 「策略/因子是活资产」：版本快照保存完整代码/口径，运行归档与版本
 *   多对一，回测口径（rules/config）原样保存才有跨版本对比意义；
 * - 容量上限防灌爆（与 KStock 同量级）。
 */

import { existsSync, mkdirSync, readFileSync, readdirSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import { createHash, randomBytes } from 'node:crypto'
import { join } from 'node:path'
import { stockHome } from './stock-home.ts'

export type LibraryKind = 'strategies' | 'factors' | 'selections'

export const LIBRARY_KINDS: readonly LibraryKind[] = ['strategies', 'factors', 'selections']

/** 容量上限（字节），与 KStock 三库同量级。 */
export const CAPS = {
  code: 512 * 1024,
  params: 64 * 1024,
  metrics: 64 * 1024,
  rules: 16 * 1024,
  curve: 2 * 1024 * 1024, // equity / ic_series / report
  detail: 4 * 1024 * 1024, // trades / layers / picks
} as const

interface KindConfig {
  readonly idPrefix: string
  readonly runPrefix: string
  readonly statuses: readonly string[]
  /** 选股库的版本主存是 criteria_json 而非 code；create 自动落 v1。 */
  readonly autoVersionOnCreate: boolean
}

const KIND_CONFIG: Record<LibraryKind, KindConfig> = {
  strategies: { idPrefix: 'stg_', runPrefix: 'srun_', statuses: ['researching', 'paused', 'rejected'], autoVersionOnCreate: false },
  factors: { idPrefix: 'fac_', runPrefix: 'frun_', statuses: ['researching', 'adopted', 'paused', 'rejected'], autoVersionOnCreate: false },
  selections: { idPrefix: 'sel_', runPrefix: 'xrun_', statuses: ['watching', 'archived', 'closed'], autoVersionOnCreate: true },
}

export type LibraryObject = Record<string, unknown> & {
  name: string
  status: string
  current_version: number
  created_at: string
  updated_at: string
}

/** 运行归档里的重负载字段（曲线/明细，容量上限见 CAPS.curve / CAPS.detail）：
 * 列表与详情投影一律剥离，运行对比经 runsByIds 按需整批拉取
 * （KStock 同款两段式：run 摘要常驻，曲线只在勾选对比时传输）。 */
export const RUN_PAYLOAD_KEYS: readonly string[] = ['equity', 'ic_series', 'report', 'trades', 'layers', 'picks']

export function lightRun(run: LibraryRun): Record<string, unknown> {
  const out: Record<string, unknown> = { ...run }
  for (const key of RUN_PAYLOAD_KEYS) delete out[key]
  return out
}

export type LibraryVersion = Record<string, unknown> & { version: number; created_at: string }
export type LibraryRun = Record<string, unknown> & { run_id: string; version: number; created_at: string }

export class LibraryError extends Error {
  constructor(readonly code: string, message: string) {
    super(message)
    this.name = 'LibraryError'
  }
}

export function isLibraryKind(value: unknown): value is LibraryKind {
  return typeof value === 'string' && (LIBRARY_KINDS as readonly string[]).includes(value)
}

function kindConfig(kind: LibraryKind): KindConfig {
  return KIND_CONFIG[kind]
}

export class LibraryStore {
  private readonly root: string

  constructor(root = join(stockHome(), 'product')) {
    this.root = root
  }

  private dir(kind: LibraryKind, objectId?: string): string {
    return objectId === undefined ? join(this.root, kind) : join(this.root, kind, objectId)
  }

  private objectPath(kind: LibraryKind, objectId: string): string {
    return join(this.dir(kind, objectId), 'object.json')
  }

  private versionPath(kind: LibraryKind, objectId: string, version: number): string {
    return join(this.dir(kind, objectId), 'versions', `v${String(version).padStart(3, '0')}.json`)
  }

  private runPath(kind: LibraryKind, objectId: string, runId: string): string {
    return join(this.dir(kind, objectId), 'runs', `${runId}.json`)
  }

  private readJson<T>(path: string): T | undefined {
    try {
      return JSON.parse(readFileSync(path, 'utf8')) as T
    } catch {
      return undefined
    }
  }

  private writeJson(path: string, value: unknown): void {
    mkdirSync(LibraryStore.dirname(path), { recursive: true })
    const tmp = `${path}.tmp-${process.pid}-${Date.now()}`
    writeFileSync(tmp, JSON.stringify(value, null, 2), { mode: 0o600 })
    renameSync(tmp, path)
  }

  private static dirname(path: string): string {
    const at = path.lastIndexOf('/')
    return at > 0 ? path.slice(0, at) : '.'
  }

  private static now(): string {
    return new Date().toISOString()
  }

  private newId(kind: LibraryKind): string {
    return kindConfig(kind).idPrefix + randomBytes(6).toString('hex')
  }

  private requireObject(kind: LibraryKind, objectId: string): LibraryObject {
    const object = this.readJson<LibraryObject>(this.objectPath(kind, objectId))
    if (object === undefined) {
      throw new LibraryError('not-found', `${kind}/${objectId} 不存在（先用 list 定位，或 create 创建）`)
    }
    return object
  }

  private assertSize(label: string, value: unknown, cap: number): void {
    if (value === undefined || value === null) return
    const bytes = typeof value === 'string' ? Buffer.byteLength(value) : Buffer.byteLength(JSON.stringify(value))
    if (bytes > cap) {
      throw new LibraryError('too-large', `${label} 超出容量上限（${bytes} > ${cap} 字节）`)
    }
  }

  private assertVersionPayload(kind: LibraryKind, payload: Record<string, unknown>): void {
    if (kind === 'selections') {
      const criteria = payload['criteria_json']
      if (typeof criteria !== 'object' || criteria === null || Array.isArray(criteria)) {
        throw new LibraryError('invalid', 'selection_save_version 需要 criteria_json 对象（选股要求结构化口径）')
      }
      const summary = (criteria as Record<string, unknown>)['summary']
      if (typeof summary !== 'string' || summary.trim() === '') {
        throw new LibraryError('invalid', 'criteria_json.summary 必填（一句话选股口径，用于库内定位与复用）')
      }
      this.assertSize('criteria_json', criteria, CAPS.params)
    } else {
      if (typeof payload['code'] !== 'string' || payload['code']!.trim() === '') {
        throw new LibraryError('invalid', 'save_version 需要 code 字符串（完整可执行版本快照，禁止只留在会话工作区）')
      }
      this.assertSize('code', payload['code'], CAPS.code)
    }
    if (payload['params'] !== undefined) this.assertSize('params', payload['params'], CAPS.params)
    if (typeof payload['change_note'] !== 'string' || payload['change_note']!.trim() === '') {
      throw new LibraryError('invalid', 'change_note 必填（本版本相对上一版改了什么、为什么）')
    }
  }

  /* ── 查询 ── */

  listObjects(kind: LibraryKind): Array<Record<string, unknown>> {
    const dir = this.dir(kind)
    if (!existsSync(dir)) return []
    const out: Array<Record<string, unknown>> = []
    for (const entry of readdirSync(dir)) {
      const object = this.readJson<LibraryObject>(this.objectPath(kind, entry))
      if (object === undefined) continue
      const runs = this.listRuns(kind, entry)
      const latest = runs.length > 0 ? runs[runs.length - 1] : undefined
      // 宿主 ToolRuntime 对工具返回值做 lossless JSON 校验（undefined 值属性
      // 即拒收）——无运行的资产不产 latest_run 键，而非置 undefined。
      out.push({
        ...object,
        object_id: entry,
        library: kind,
        ...(latest === undefined ? {} : { latest_run: lightRun(latest) }),
        run_count: runs.length,
      })
    }
    out.sort((a, b) => String(b['updated_at']).localeCompare(String(a['updated_at'])))
    return out
  }

  detail(kind: LibraryKind, objectId: string): Record<string, unknown> {
    const object = this.requireObject(kind, objectId)
    return {
      ...object,
      object_id: objectId,
      library: kind,
      versions: this.listVersions(kind, objectId),
      runs: this.listRuns(kind, objectId).map(lightRun),
    }
  }

  /** 运行对比取数：按 run_ids 返回完整归档（含 equity / ic_series 曲线负载）。
   * 任一 run 缺失即整体报 not-found——宁可让 UI 重开详情，也不给静默空曲线。 */
  runsByIds(kind: LibraryKind, objectId: string, runIds: readonly string[]): LibraryRun[] {
    this.requireObject(kind, objectId)
    const out: LibraryRun[] = []
    for (const runId of runIds) {
      const run = this.readJson<LibraryRun>(this.runPath(kind, objectId, runId))
      if (run === undefined) throw new LibraryError('not-found', `运行 ${runId} 不存在（列表可能已过期，请重开详情刷新）`)
      out.push(run)
    }
    return out
  }

  listVersions(kind: LibraryKind, objectId: string): LibraryVersion[] {
    const dir = join(this.dir(kind, objectId), 'versions')
    if (!existsSync(dir)) return []
    const out: LibraryVersion[] = []
    for (const entry of readdirSync(dir)) {
      if (!entry.endsWith('.json')) continue
      const version = this.readJson<LibraryVersion>(join(dir, entry))
      if (version !== undefined) out.push(version)
    }
    out.sort((a, b) => a.version - b.version)
    return out
  }

  listRuns(kind: LibraryKind, objectId: string): LibraryRun[] {
    const dir = join(this.dir(kind, objectId), 'runs')
    if (!existsSync(dir)) return []
    const out: LibraryRun[] = []
    for (const entry of readdirSync(dir)) {
      if (!entry.endsWith('.json')) continue
      const run = this.readJson<LibraryRun>(join(dir, entry))
      if (run !== undefined) out.push(run)
    }
    out.sort((a, b) => String(a['created_at']).localeCompare(String(b['created_at'])))
    return out
  }

  /* ── 写入（agent 工具专用语义） ── */

  createObject(kind: LibraryKind, input: { name: string; hypothesis?: string | undefined; criteria?: string | undefined; criteria_json?: Record<string, unknown> | undefined; category?: string | undefined; params?: unknown }): Record<string, unknown> {
    const name = typeof input.name === 'string' ? input.name.trim() : ''
    if (name === '') throw new LibraryError('invalid', 'name 必填')
    if (name.length > 120) throw new LibraryError('invalid', 'name 过长（≤120 字）')
    const now = LibraryStore.now()
    const objectId = this.newId(kind)
    const object: LibraryObject = {
      name,
      status: kindConfig(kind).statuses[0] as string,
      current_version: 0,
      created_at: now,
      updated_at: now,
    }
    if (kind === 'strategies' || kind === 'factors') {
      object['hypothesis'] = typeof input.hypothesis === 'string' ? input.hypothesis.slice(0, 2000) : ''
    }
    if (kind === 'factors') {
      const categories = ['value', 'momentum', 'quality', 'low_vol', 'size', 'growth', 'custom']
      const category = typeof input.category === 'string' && categories.includes(input.category) ? input.category : 'custom'
      object['category'] = category
    }
    if (kind === 'selections') {
      if (typeof input.criteria !== 'string' || input.criteria.trim() === '') {
        throw new LibraryError('invalid', 'selection_create 需要 criteria（一句话选股口径）')
      }
      object['criteria'] = input.criteria.trim().slice(0, 2000)
    }
    this.writeJson(this.objectPath(kind, objectId), object)
    // 选股库：create 自动落 v1（KStock 同款语义，口径即身份的一部分）
    if (kindConfig(kind).autoVersionOnCreate) {
      const criteriaJson = typeof input.criteria_json === 'object' && input.criteria_json !== null
        ? input.criteria_json
        : { summary: object['criteria'] }
      this.writeVersion(kind, objectId, { criteria_json: criteriaJson, params: input.params, change_note: '初始选股要求', parent_version: 0 })
    }
    return { object_id: objectId, ...this.readJson<LibraryObject>(this.objectPath(kind, objectId))!, library: kind }
  }

  updateObject(kind: LibraryKind, objectId: string, patch: { name?: string | undefined; hypothesis?: string | undefined; criteria?: string | undefined; category?: string | undefined; status?: string | undefined }): Record<string, unknown> {
    const object = this.requireObject(kind, objectId)
    if (patch.name !== undefined) {
      const name = patch.name.trim()
      if (name === '') throw new LibraryError('invalid', 'name 不能为空')
      object['name'] = name
    }
    if (patch.hypothesis !== undefined) object['hypothesis'] = patch.hypothesis.slice(0, 2000)
    if (patch.criteria !== undefined) object['criteria'] = patch.criteria.trim().slice(0, 2000)
    if (patch.category !== undefined) {
      const categories = ['value', 'momentum', 'quality', 'low_vol', 'size', 'growth', 'custom']
      if (!categories.includes(patch.category)) throw new LibraryError('invalid', `category 必须是 ${categories.join('/')}`)
      object['category'] = patch.category
    }
    if (patch.status !== undefined) {
      if (!kindConfig(kind).statuses.includes(patch.status)) {
        throw new LibraryError('invalid', `status 必须是 ${kindConfig(kind).statuses.join('/')}`)
      }
      object['status'] = patch.status
    }
    object['updated_at'] = LibraryStore.now()
    this.writeJson(this.objectPath(kind, objectId), object)
    return { ...object, object_id: objectId, library: kind }
  }

  private writeVersion(kind: LibraryKind, objectId: string, payload: Record<string, unknown>): LibraryVersion {
    const object = this.requireObject(kind, objectId)
    const parentVersion = typeof payload['parent_version'] === 'number' ? payload['parent_version'] : undefined
    if (parentVersion !== object['current_version']) {
      throw new LibraryError(
        'version-conflict',
        `版本冲突：parent_version=${parentVersion} 但当前是 v${object['current_version']}（先 get_latest 读取最新版，在其之上迭代）`,
      )
    }
    this.assertVersionPayload(kind, payload)
    const version = (object['current_version'] as number) + 1
    const record: LibraryVersion = {
      version,
      parent_version: parentVersion,
      code_sha256: kind === 'selections'
        ? undefined
        : createSha256(String(payload['code'])),
      ...payload,
      created_at: LibraryStore.now(),
    }
    if (record['code_sha256'] === undefined) delete record['code_sha256']
    this.writeJson(this.versionPath(kind, objectId, version), record)
    object['current_version'] = version
    object['updated_at'] = LibraryStore.now()
    if (kind === 'selections') {
      const criteria = payload['criteria_json'] as Record<string, unknown> | undefined
      const summary = criteria?.['summary']
      if (typeof summary === 'string' && summary.trim() !== '') object['criteria'] = summary.trim().slice(0, 2000)
    }
    this.writeJson(this.objectPath(kind, objectId), object)
    return record
  }

  saveVersion(kind: LibraryKind, objectId: string, payload: Record<string, unknown>): LibraryVersion {
    return this.writeVersion(kind, objectId, payload)
  }

  recordRun(kind: LibraryKind, objectId: string, input: Record<string, unknown>): LibraryRun {
    const object = this.requireObject(kind, objectId)
    const version = input['version']
    if (typeof version !== 'number' || version < 1 || version > (object['current_version'] as number)) {
      throw new LibraryError('invalid', `version 必须是 1..${object['current_version']}（先 save_version 落版本，再登记运行）`)
    }
    this.assertSize('metrics', input['metrics'], CAPS.metrics)
    this.assertSize('rules/config', input['rules'] ?? input['config'], CAPS.rules)
    for (const key of ['equity', 'ic_series', 'report']) {
      if (input[key] !== undefined) this.assertSize(key, input[key], CAPS.curve)
    }
    for (const key of ['trades', 'layers', 'picks']) {
      if (input[key] !== undefined) this.assertSize(key, input[key], CAPS.detail)
    }
    const runId = kindConfig(kind).runPrefix + randomBytes(6).toString('hex')
    const run: LibraryRun = {
      run_id: runId,
      version,
      ...input,
      created_at: LibraryStore.now(),
    }
    this.writeJson(this.runPath(kind, objectId, runId), run)
    return run
  }

  deleteObject(kind: LibraryKind, objectId: string): void {
    const dir = this.dir(kind, objectId)
    if (!existsSync(dir)) throw new LibraryError('not-found', `${kind}/${objectId} 不存在`)
    rmSync(dir, { recursive: true, force: true })
  }
}

function createSha256(text: string): string {
  return createHash('sha256').update(text).digest('hex')
}
