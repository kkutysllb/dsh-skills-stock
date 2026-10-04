/** 报告库：自包含 HTML 研究报告的归档与索引（KStock 2.0 quant-reports 同构）。
 *
 * 与策略/因子/选股三库不同（KStock 原注释口径）：报告**无版本链**——
 * 同 report_id 重复归档即覆盖更新；归档入口收敛为 agent 显式调用
 * （html-report 技能交付即归档，dsh 侧经 report_archive 工具）。存储沿用
 * 本插件纯 JSON 文件形态，meta 与 HTML 全文分离（列表不背内容负载）：
 *
 *   <数据根>/product/reports/<reportId>/report.json    meta（含 sha256/size）
 *   <数据根>/product/reports/<reportId>/content.html   报告全文（0600）
 *
 * KStock 同款纪律：report_id / 尺寸白名单防路径穿越与灌爆；内容 sha256
 * 寻址；同 id 覆盖只刷新内容与 updated_at（created_at 保留首档时间）。
 * 错误走 ReportError（tools/RPC 信封与 LibraryError 同构映射）。
 */

import { existsSync, mkdirSync, readFileSync, readdirSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { isAbsolute, join, resolve } from 'node:path'
import { stockHome } from './stock-home.ts'

/** 单份报告 HTML 的大小上限（KStock MAX_REPORT_BYTES 同量级）。 */
export const MAX_REPORT_BYTES = 8 * 1024 * 1024

/** KStock 1.x 同款路径组件白名单：防 report_id 拼进文件路径。 */
const SAFE_REPORT_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/

export interface ReportArchiveInput {
  title: string
  /** 报告 HTML 全文（UTF-8 单文件自包含）。与 contentPath 二选一。 */
  content?: string | undefined
  /** 报告 HTML 文件路径（绝对，或相对 baseDir 的相对路径）：宿主端直读，
   * 大报告不经 LLM 上下文中转（几十 KB 单行内联转录必有损坏风险）。 */
  contentPath?: string | undefined
  /** 解析相对 contentPath 的基目录（agent 会话工作区 cwd）。 */
  baseDir?: string | undefined
  reportId?: string | undefined
  symbol?: string | undefined
  reportType?: string | undefined
  generatedAt?: string | undefined
  periodStart?: string | undefined
  periodEnd?: string | undefined
  riskLevel?: string | undefined
  coverageStatus?: string | undefined
  threadId?: string | undefined
}

export type ReportMeta = Record<string, unknown> & {
  report_id: string
  title: string
  created_at: string
  updated_at: string
}

export class ReportStore {
  private readonly root: string

  constructor(root = join(stockHome(), 'product', 'reports')) {
    this.root = root
  }

  private dir(reportId?: string): string {
    return reportId === undefined ? this.root : join(this.root, reportId)
  }

  private metaPath(reportId: string): string {
    return join(this.dir(reportId), 'report.json')
  }

  private contentPath(reportId: string): string {
    return join(this.dir(reportId), 'content.html')
  }

  private static now(): string {
    return new Date().toISOString()
  }

  private static sha256(text: string): string {
    return createHash('sha256').update(text).digest('hex')
  }

  /** 写文件（临时文件 + rename 原子替换，权限 0600）。 */
  private writeFileAtomic(path: string, data: string): void {
    mkdirSync(ReportStore.dirname(path), { recursive: true })
    const tmp = `${path}.tmp-${process.pid}-${Date.now()}`
    writeFileSync(tmp, data, { mode: 0o600 })
    renameSync(tmp, path)
  }

  private static dirname(path: string): string {
    const at = path.lastIndexOf('/')
    return at > 0 ? path.slice(0, at) : '.'
  }

  private readMeta(reportId: string): ReportMeta | undefined {
    try {
      return JSON.parse(readFileSync(this.metaPath(reportId), 'utf8')) as ReportMeta
    } catch {
      return undefined
    }
  }

  /** 归档/覆盖更新：缺省 report_id 按 thread+标题稳定派生（同研究重跑不增新档）。 */
  archive(input: ReportArchiveInput): Record<string, unknown> {
    const title = typeof input.title === 'string' ? input.title.trim() : ''
    if (title === '') throw new ReportError('invalid', 'title 必填（报告标题）')
    if (title.length > 300) throw new ReportError('invalid', 'title 过长（≤300 字）')
    let content: string
    if (typeof input.contentPath === 'string' && input.contentPath.trim() !== '') {
      // 文件通道：宿主端直读，路径以绝对路径或会话 cwd 相对路径给出
      const raw = input.contentPath.trim()
      const full = isAbsolute(raw) ? raw : resolve(input.baseDir ?? '.', raw)
      try {
        content = readFileSync(full, 'utf8')
      } catch {
        throw new ReportError('invalid', `content_path 无法读取：${full}（确认文件存在，或改传绝对路径）`)
      }
    } else if (typeof input.content === 'string' && input.content.trim() !== '') {
      content = input.content
    } else {
      throw new ReportError('invalid', 'content / content_path 必填其一（大报告一律用 content_path 传文件路径，禁止读进上下文内联）')
    }
    if (content.trim() === '') throw new ReportError('invalid', '报告内容为空')
    const bytes = Buffer.byteLength(content)
    if (bytes > MAX_REPORT_BYTES) {
      throw new ReportError('too-large', `content 超出单份报告上限（${bytes} > ${MAX_REPORT_BYTES} 字节）`)
    }
    let reportId = input.reportId?.trim() ?? ''
    if (reportId === '') {
      // KStock 同款稳定派生：thread+标题 → 同会话同标题重复归档即覆盖
      reportId = 'rpt_' + ReportStore.sha256(`${input.threadId ?? ''}::${title}`).slice(0, 12)
    } else if (!SAFE_REPORT_ID.test(reportId)) {
      throw new ReportError('invalid', 'report_id 只允许字母/数字/点/下划线/连字符（1-128 位，防路径穿越）')
    }
    const now = ReportStore.now()
    const existing = this.readMeta(reportId)
    const meta: ReportMeta = {
      report_id: reportId,
      title,
      thread_id: input.threadId ?? existing?.['thread_id'] ?? null,
      symbol: input.symbol ?? existing?.['symbol'] ?? null,
      report_type: input.reportType ?? existing?.['report_type'] ?? 'analysis',
      generated_at: input.generatedAt ?? existing?.['generated_at'] ?? now,
      period_start: input.periodStart ?? existing?.['period_start'] ?? null,
      period_end: input.periodEnd ?? existing?.['period_end'] ?? null,
      risk_level: input.riskLevel ?? existing?.['risk_level'] ?? null,
      coverage_status: input.coverageStatus ?? existing?.['coverage_status'] ?? 'complete',
      size_bytes: bytes,
      sha256: ReportStore.sha256(content),
      created_at: existing?.['created_at'] ?? now,
      updated_at: now,
    }
    this.writeFileAtomic(this.contentPath(reportId), content)
    this.writeFileAtomic(this.metaPath(reportId), JSON.stringify(meta, null, 2))
    return { ...meta, content_path: this.contentPath(reportId), updated: existing !== undefined }
  }

  /** 报告清单（轻量 meta 投影，updated_at 倒序；不含 content）。 */
  list(): Array<Record<string, unknown>> {
    if (!existsSync(this.root)) return []
    const out: Array<Record<string, unknown>> = []
    for (const entry of readdirSync(this.root)) {
      if (entry.startsWith('.')) continue
      const meta = this.readMeta(entry)
      if (meta === undefined) continue
      out.push({ ...meta }) // 不投影 content_path 键（lossless 校验拒绝 undefined 值属性）
    }
    out.sort((a, b) => String(b['updated_at']).localeCompare(String(a['updated_at'])))
    return out
  }

  /** 读单份报告；withContent=true 时带 HTML 全文（工具/RPC 按需拉取）。 */
  get(reportId: string, withContent = false): Record<string, unknown> {
    const meta = this.readMeta(this.requireId(reportId))
    if (meta === undefined) throw new ReportError('not-found', `报告 ${reportId} 不存在（先 report_list 定位）`)
    const out: Record<string, unknown> = { ...meta, content_path: this.contentPath(meta.report_id) }
    if (withContent) out['content'] = readFileSync(this.contentPath(meta.report_id), 'utf8')
    return out
  }

  delete(reportId: string): void {
    const id = this.requireId(reportId)
    const dir = this.dir(id)
    if (!existsSync(dir)) throw new ReportError('not-found', `报告 ${reportId} 不存在`)
    rmSync(dir, { recursive: true, force: true })
  }

  /** report_id 白名单校验（拼路径前先过，拒绝穿越/非法字符）。 */
  private requireId(reportId: string): string {
    if (typeof reportId !== 'string' || !SAFE_REPORT_ID.test(reportId)) {
      throw new ReportError('invalid', 'report_id 只允许字母/数字/点/下划线/连字符（1-128 位）')
    }
    return reportId
  }
}

/** 报告库错误：与 LibraryError 同构（同 code/message 信封），避免循环依赖。 */
export class ReportError extends Error {
  constructor(readonly code: string, message: string) {
    super(message)
    this.name = 'ReportError'
  }
}

/** archive/list/get 抛 LibraryError 形状的错误（复用既有信封映射）。 */
function LibraryErrorLike(code: string, message: string): Error {
  return new ReportError(code, message)
}
