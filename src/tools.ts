/** 三库 agent 工具（15 个，注册名与 KStock 对齐）+ 报告库工具（3 个，
 * KStock 2.0 quant-reports 同构）：把「策略 / 因子 / 选股 / 报告」
 * 作为资产写进 <数据根>/product/，供投研工作台 UI 查看与重跑。
 *
 * 形态对齐 dsh-kylin-automation tools.ts：纯对象定义 + {ok,value} 信封 +
 * ToolRejection/工具信封错误映射，经 ctx.tools.register 全局注册
 * （dsh-super-ppts 同款：ppts_check 等宿主工具即全局注册）。
 *
 * 版本纪律（沿袭 KStock lead_soul）：代码/口径必须经 save_version 入库，
 * 禁止只留在会话工作区；rules/config 原样抄录才能跨版本对比。
 * 报告库例外：无版本链，同 report_id 重复归档即覆盖更新。
 */

import { LibraryError, LibraryStore, isLibraryKind, type LibraryKind } from './library.ts'
import { ReportError, ReportStore } from './reports.ts'

export class ToolRejection extends Error {
  constructor(readonly code: string, message: string) {
    super(message)
    this.name = 'ToolRejection'
  }
}

/** Bounded caller identity a tool may bind to. */
export interface ToolCaller {
  readonly cwd?: string | undefined
  readonly sessionId?: string | undefined
}

export function callerFrom(exec: unknown): ToolCaller {
  const agent = (exec as { agent?: { session?: { id?: unknown; header?: { cwd?: unknown } } } }).agent
  return {
    sessionId: typeof agent?.session?.id === 'string' ? agent.session.id : undefined,
    cwd: typeof agent?.session?.header?.cwd === 'string' ? agent.session.header.cwd : undefined,
  }
}

/** 模型可见的工具输出部件（宿主 ToolRuntime 契约，官方 schedule 插件同款）：
 * render 必须返回 ContentBlock 部件对象数组——返回裸 string 会被宿主原样
 * 塞进 tool 消息的 content，模型侧消息规范化时静默丢弃（表现为「工具无返回」）。 */
export interface ToolContentBlock {
  readonly type: 'text'
  readonly text: string
}

const jsonRender = (_args: unknown, value: unknown): ToolContentBlock[] => [
  { type: 'text', text: typeof value === 'string' ? value : JSON.stringify(value, null, 2) },
]

function toolEnvelope(error: unknown): { ok: false; error: { code: string; message: string } } {
  if (error instanceof LibraryError || error instanceof ReportError) {
    return { ok: false, error: { code: error.code, message: error.message } }
  }
  return { ok: false, error: { code: 'internal', message: error instanceof Error ? error.message : String(error) } }
}

function requireKind(value: unknown, label: string): LibraryKind {
  if (!isLibraryKind(value)) throw new ToolRejection('invalid', `${label} 必须是 strategies / factors / selections 之一`)
  return value
}

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new ToolRejection('invalid', `${label} 必须是对象`)
  }
  return value as Record<string, unknown>
}

function string(value: unknown, label: string): string {
  if (typeof value !== 'string') throw new ToolRejection('invalid', `${label} 必须是字符串`)
  return value
}

function boundedLine(summary: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(summary).map(([k, v]) => [k, typeof v === 'string' && v.length > 200 ? v.slice(0, 200) + '…' : v]))
}

export interface DshToolDefinition {
  readonly name: string
  readonly description: string
  readonly parameters: Record<string, unknown>
  readonly output: { readonly schema: Record<string, unknown>; readonly render: (args: unknown, value: unknown) => ToolContentBlock[] }
  readonly timeoutMs: number
  readonly execute: (args: unknown, exec: unknown) => Promise<unknown>
}

/** 生成某一库的 5 件套工具定义（list/create/get_latest/save_version/record）。 */
function libraryToolSet(kind: LibraryKind, store: LibraryStore): DshToolDefinition[] {
  const zh = kind === 'strategies'
    ? { noun: '策略', record: 'strategy_record_backtest', recordLabel: '回测', runPayload: ['data_start', 'data_end', 'rules', 'metrics', 'equity?', 'trades?'] }
    : kind === 'factors'
      ? { noun: '因子', record: 'factor_record_run', recordLabel: '检验', runPayload: ['universe', 'data_start', 'data_end', 'config', 'metrics', 'ic_series?', 'layers?'] }
      : { noun: '选股', record: 'selection_record_run', recordLabel: '执行', runPayload: ['trade_date', 'universe', 'rules', 'metrics', 'report?', 'picks?'] }
  const idKey = kind === 'strategies' ? 'strategy_id' : kind === 'factors' ? 'factor_id' : 'selection_id'
  return [
    {
      name: `${kind === 'strategies' ? 'strategy' : kind === 'factors' ? 'factor' : 'selection'}_list`,
      description: `列出${zh.noun}库全部${zh.noun}（id/名称/状态/当前版本/最近${zh.recordLabel}核心指标）。用户说「继续/改进/对比之前的${zh.noun}」时，从这里定位起点。`,
      parameters: { type: 'object', properties: {} },
      output: { schema: { type: 'object' }, render: jsonRender },
      timeoutMs: 15_000,
      execute: async () => {
        try {
          const views = store.listObjects(kind).map((view) => boundedLine(view))
          return { ok: true, value: { library: kind, count: views.length, items: views } }
        } catch (error) {
          return toolEnvelope(error)
        }
      },
    },
    {
      name: `${kind === 'strategies' ? 'strategy' : kind === 'factors' ? 'factor' : 'selection'}_create`,
      description: kind === 'selections'
        ? `创建选股方案（{name, criteria, params?}）：criteria 是一句话选股口径，创建即落 v1「初始选股要求」。后续执行结果用 selection_record_run 归档。`
        : `创建${zh.noun}（{name, hypothesis${kind === 'factors' ? ', category' : ''}}）：hypothesis 写清经济学/投资假设。返回 ${idKey}，后续用 get_latest / save_version 迭代。`,
      parameters: {
        type: 'object',
        properties: {
          name: { type: 'string', description: '名称（≤120 字）' },
          hypothesis: { type: 'string', description: '投资/经济学假设（策略与因子）' },
          category: { type: 'string', enum: ['value', 'momentum', 'quality', 'low_vol', 'size', 'growth', 'custom'], description: '因子类别（仅因子库）' },
          criteria: { type: 'string', description: '一句话选股口径（仅选股库）' },
          params: { type: 'object', description: '初始参数（可选）' },
        },
      },
      output: { schema: { type: 'object' }, render: jsonRender },
      timeoutMs: 15_000,
      execute: async (args) => {
        try {
          const body = record(args, 'args')
          const created = store.createObject(kind, {
            name: string(body['name'], 'name'),
            hypothesis: typeof body['hypothesis'] === 'string' ? body['hypothesis'] : undefined,
            category: typeof body['category'] === 'string' ? body['category'] : undefined,
            criteria: typeof body['criteria'] === 'string' ? body['criteria'] : undefined,
            criteria_json: body['criteria_json'] === undefined ? undefined : record(body['criteria_json'], 'criteria_json'),
            params: body['params'],
          })
          return { ok: true, value: created }
        } catch (error) {
          return toolEnvelope(error)
        }
      },
    },
    {
      name: `${kind === 'strategies' ? 'strategy' : kind === 'factors' ? 'factor' : 'selection'}_get_latest`,
      description: `读取${zh.noun}当前版本的完整快照（${kind === 'selections' ? 'criteria_json 结构化口径' : '代码 code'} + params + change_note）。迭代/复用的起点；库内无版本时先 save_version 落 v1。`,
      parameters: {
        type: 'object',
        properties: { [idKey]: { type: 'string', description: `${zh.noun} id（${idKey} 前缀）` } },
        required: [idKey],
      },
      output: { schema: { type: 'object' }, render: jsonRender },
      timeoutMs: 15_000,
      execute: async (args) => {
        try {
          const body = record(args, 'args')
          const objectId = string(body[idKey], idKey)
          const detail = store.detail(kind, objectId)
          const versions = (detail['versions'] as unknown[]) ?? []
          const latest = versions.length > 0 ? versions[versions.length - 1] : undefined
          if (latest === undefined) {
            throw new ToolRejection('empty', `${objectId} 尚无版本：先 save_version 落 v1（${kind === 'selections' ? 'criteria_json.summary 必填' : '完整代码 + params + change_note'}）`)
          }
          return { ok: true, value: { object: boundedLine(detail), latest_version: latest } }
        } catch (error) {
          return toolEnvelope(error)
        }
      },
    },
    {
      name: `${kind === 'strategies' ? 'strategy' : kind === 'factors' ? 'factor' : 'selection'}_save_version`,
      description: kind === 'selections'
        ? `保存选股方案新版本（{${idKey}, criteria_json, change_note, parent_version}）：criteria_json.summary 必填；parent_version 必须等于当前版本（乐观锁）。临时新口径先存版本再执行。`
        : `保存${zh.noun}新版本（{${idKey}, code, params, change_note, parent_version}）：code 是完整可执行快照——${zh.noun}代码必须入库，禁止只留在会话工作区；parent_version 必须等于当前版本（乐观锁），conflict 时先 get_latest。`,
      parameters: {
        type: 'object',
        properties: {
          [idKey]: { type: 'string', description: `${zh.noun} id` },
          code: { type: 'string', description: '完整代码快照（策略/因子）' },
          criteria_json: { type: 'object', description: '结构化选股要求（选股库，summary 必填）' },
          params: { type: 'object', description: '参数字典' },
          change_note: { type: 'string', description: '本版本改动与原因（证伪也要如实写）' },
          parent_version: { type: 'number', description: '基于的当前版本号（乐观锁）' },
        },
        required: [idKey, 'change_note', 'parent_version'],
      },
      output: { schema: { type: 'object' }, render: jsonRender },
      timeoutMs: 15_000,
      execute: async (args) => {
        try {
          const body = record(args, 'args')
          const objectId = string(body[idKey], idKey)
          const saved = store.saveVersion(kind, objectId, body)
          return { ok: true, value: { [idKey]: objectId, version: saved['version'], change_note: saved['change_note'] } }
        } catch (error) {
          return toolEnvelope(error)
        }
      },
    },
    {
      name: zh.record,
      description: `${zh.noun}${zh.recordLabel}后登记运行归档（{${idKey}, version, ${zh.runPayload.join(', ')}, thread_id?}）：${kind === 'strategies' ? 'rules 必须原样抄录回测的 A 股交易规则回显' : kind === 'factors' ? 'config 原样抄录检验配置' : 'picks=[{code,name,score,strategies,rank}]，report 为完整 markdown 报告'}；登记后可在投研工作台对应库查看与跨${kind === 'selections' ? '基准日' : '版本'}对比。`,
      parameters: {
        type: 'object',
        properties: {
          [idKey]: { type: 'string', description: `${zh.noun} id` },
          version: { type: 'number', description: '本次运行基于的版本号' },
          data_start: { type: 'string', description: '数据区间起（YYYYMMDD）' },
          data_end: { type: 'string', description: '数据区间止（YYYYMMDD）' },
          trade_date: { type: 'string', description: '基准日（选股库，YYYYMMDD）' },
          universe: { type: 'string', description: '股票池说明（因子/选股）' },
          rules: { type: 'object', description: '交易/执行规则（原样抄录）' },
          config: { type: 'object', description: '检验配置（因子，原样抄录）' },
          metrics: { type: 'object', description: '核心指标字典' },
          equity: { type: 'object', description: '净值曲线（策略，可选，≤2MB）' },
          trades: { type: 'object', description: '成交明细（可选，≤4MB）' },
          ic_series: { type: 'object', description: 'IC 序列（因子，可选）' },
          layers: { type: 'object', description: '分层回测结果（因子，可选）' },
          report: { type: 'string', description: '完整 markdown 报告（选股，可选）' },
          picks: { type: 'object', description: '命中清单（选股，可选）' },
          thread_id: { type: 'string', description: '来源会话 id（可选）' },
        },
        required: [idKey, 'version', 'metrics'],
      },
      output: { schema: { type: 'object' }, render: jsonRender },
      timeoutMs: 30_000,
      execute: async (args, exec) => {
        try {
          const body = record(args, 'args')
          const objectId = string(body[idKey], idKey)
          const caller = callerFrom(exec)
          const run = store.recordRun(kind, objectId, {
            ...body,
            ...(caller.sessionId !== undefined && body['thread_id'] === undefined ? { thread_id: caller.sessionId } : {}),
          })
          return { ok: true, value: { [idKey]: objectId, run_id: run['run_id'], version: run['version'], created_at: run['created_at'] } }
        } catch (error) {
          return toolEnvelope(error)
        }
      },
    },
  ]
}

/** 全部 15 个三库工具定义。 */
export function libraryToolDefs(store: LibraryStore): DshToolDefinition[] {
  return (['strategies', 'factors', 'selections'] as const).flatMap((kind) => libraryToolSet(kind, store))
}

/* ── 报告库工具（3 个，KStock 2.0 quant-reports 同构：无版本链，同 id 覆盖）── */

/** 报告 meta 的有界投影：长字符串截断，字段原样透传。 */
function boundedReport(meta: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(meta).map(([k, v]) => [k, typeof v === 'string' && v.length > 200 ? v.slice(0, 200) + '…' : v]))
}

export function reportToolDefs(store: ReportStore): DshToolDefinition[] {
  return [
    {
      name: 'report_archive',
      description: '把研究报告 HTML 看板归档进报告库（投研工作台「报告库」随时查看）。{title, content_path, report_id?, symbol?, report_type?, generated_at?, period_start?, period_end?, risk_level?, coverage_status?}：**大报告一律用 content_path 传看板文件路径**（绝对路径，或相对当前工作目录如 reports/<主题名>.html），宿主端直读文件，禁止先把 HTML 读进上下文再内联传参（几十 KB 单行标记经 LLM 转录必有损坏风险）；content 内联通道仅限小块 HTML。同一 report_id 重复归档是覆盖更新，不传 report_id 时按会话+标题稳定派生。研究交付即归档——报告库与策略/因子/选股库互补（报告看呈现，三库看版本与运行）。',
      parameters: {
        type: 'object',
        properties: {
          title: { type: 'string', description: '报告标题（≤300 字）' },
          content_path: { type: 'string', description: '报告 HTML 文件路径（推荐：绝对路径或相对当前工作目录，宿主端直读，不经上下文）' },
          content: { type: 'string', description: '报告 HTML 全文（仅限小块内容内联；大文件必须走 content_path）' },
          report_id: { type: 'string', description: '报告 id（可选，字母/数字/点/下划线/连字符；缺省按会话+标题派生）' },
          symbol: { type: 'string', description: '标的代码（如 600519.SH，可选）' },
          report_type: { type: 'string', description: '报告类型（analysis/backtest/screening/review 等，默认 analysis）' },
          generated_at: { type: 'string', description: '生成时间（ISO 8601，可选）' },
          period_start: { type: 'string', description: '覆盖区间起（可选）' },
          period_end: { type: 'string', description: '覆盖区间止（可选）' },
          risk_level: { type: 'string', description: '风险等级（低/中/高，可选）' },
          coverage_status: { type: 'string', description: '数据覆盖状态（complete/partial 等，默认 complete）' },
          thread_id: { type: 'string', description: '来源会话 id（可选，缺省自动绑定当前会话）' },
        },
        required: ['title'],
      },
      output: { schema: { type: 'object' }, render: jsonRender },
      timeoutMs: 30_000,
      execute: async (args, exec) => {
        try {
          const body = record(args, 'args')
          const caller = callerFrom(exec)
          const threadId = typeof body['thread_id'] === 'string'
            ? body['thread_id']
            : caller.sessionId
          const saved = store.archive({
            title: string(body['title'], 'title'),
            content: typeof body['content'] === 'string' ? body['content'] : undefined,
            contentPath: typeof body['content_path'] === 'string' ? body['content_path'] : undefined,
            baseDir: caller.cwd,
            reportId: typeof body['report_id'] === 'string' ? body['report_id'] : undefined,
            symbol: typeof body['symbol'] === 'string' ? body['symbol'] : undefined,
            reportType: typeof body['report_type'] === 'string' ? body['report_type'] : undefined,
            generatedAt: typeof body['generated_at'] === 'string' ? body['generated_at'] : undefined,
            periodStart: typeof body['period_start'] === 'string' ? body['period_start'] : undefined,
            periodEnd: typeof body['period_end'] === 'string' ? body['period_end'] : undefined,
            riskLevel: typeof body['risk_level'] === 'string' ? body['risk_level'] : undefined,
            coverageStatus: typeof body['coverage_status'] === 'string' ? body['coverage_status'] : undefined,
            threadId,
          })
          return { ok: true, value: saved }
        } catch (error) {
          return toolEnvelope(error)
        }
      },
    },
    {
      name: 'report_list',
      description: '列出报告库全部已归档报告（report_id/标题/标的/类型/生成时间/风险等级/大小，按更新时间倒序）。用户说「之前出的看板/报告」时从这里定位；读全文用 report_get。',
      parameters: { type: 'object', properties: {} },
      output: { schema: { type: 'object' }, render: jsonRender },
      timeoutMs: 15_000,
      execute: async () => {
        try {
          const items = store.list().map(boundedReport)
          return { ok: true, value: { count: items.length, items } }
        } catch (error) {
          return toolEnvelope(error)
        }
      },
    },
    {
      name: 'report_get',
      description: '读取报告 meta 与落盘绝对路径（content_path）；content:true 时连同 HTML 全文返回——全文可能很大，仅在需要回看/二次加工时才拉取，禁止把全文复述进对话。',
      parameters: {
        type: 'object',
        properties: {
          report_id: { type: 'string', description: '报告 id（report_list 获取）' },
          content: { type: 'boolean', description: '是否返回 HTML 全文（默认 false，只回 meta 与路径）' },
        },
        required: ['report_id'],
      },
      output: { schema: { type: 'object' }, render: jsonRender },
      timeoutMs: 30_000,
      execute: async (args) => {
        try {
          const body = record(args, 'args')
          const reportId = string(body['report_id'], 'report_id')
          const withContent = body['content'] === true
          const detail = store.get(reportId, withContent)
          return { ok: true, value: withContent ? detail : boundedReport(detail) }
        } catch (error) {
          return toolEnvelope(error)
        }
      },
    },
  ]
}
