/** Host 服务面：技能目录（只读）+ 凭据文件（受控写）。
 *
 * 红线（对齐家族插件安全边界）：
 * - 凭据值只在写入方向流动：读取类端点只返回「键是否已配置」的布尔，
 *   任何路径都不把密钥值回传给 Web 端或写进日志；
 * - secrets.env 写入走临时文件 + rename 原子替换，权限 0600；
 * - 文件格式与技能脚本约定一致：KEY=VALUE 行，# 注释，其他行原样保留。
 */

import { chmodSync, mkdirSync, readFileSync, renameSync, unlinkSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { secretsPath, stockHome } from './stock-home.ts'

/** 支持的凭据键（与 KStock 技能链一致）。 */
export const SECRET_KEYS = ['TUSHARE_TOKEN', 'IWENCAI_API_KEY'] as const
export type SecretKey = (typeof SECRET_KEYS)[number]

/** skills/manifest.json 的注册项（与 adapt 脚本产出对齐）。 */
export interface SkillManifestEntry {
  readonly dir: string
  readonly name: string
  readonly description: string
  readonly whenToUse?: string
  readonly category?: string
  readonly requiredSecrets?: readonly string[]
}

export interface SkillsCatalogFile {
  readonly skills: readonly SkillManifestEntry[]
}

export interface WorkbenchStatus {
  readonly stockHome: string
  readonly secretsPath: string
  readonly secretsExists: boolean
  readonly secretsWritable: boolean
  readonly keys: Readonly<Record<SecretKey, boolean>>
  readonly skillCount: number
}

export class ServiceError extends Error {
  constructor(readonly code: string, message: string) {
    super(message)
    this.name = 'ServiceError'
  }
}

/** 解析 secrets.env：返回「已配置的键集合」；不解析值、不抛格式错误。 */
export function parseSecretKeySet(text: string): Set<string> {
  const found = new Set<string>()
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (line === '' || line.startsWith('#')) continue
    const eq = line.indexOf('=')
    if (eq <= 0) continue
    const key = line.slice(0, eq).trim()
    if (SECRET_KEYS.includes(key as SecretKey)) found.add(key)
  }
  return found
}

/** 读技能清单；缺文件/坏 JSON 返回空清单（不阻断插件加载）。 */
export function loadSkillsCatalog(packageRoot: string): SkillsCatalogFile {
  try {
    const parsed = JSON.parse(readFileSync(join(packageRoot, 'skills', 'manifest.json'), 'utf8')) as SkillsCatalogFile
    return Array.isArray(parsed.skills) ? { skills: parsed.skills } : { skills: [] }
  } catch {
    return { skills: [] }
  }
}

export class WorkbenchService {
  constructor(private readonly root: string) {}

  status(): WorkbenchStatus {
    const path = secretsPath()
    let keys = new Set<string>()
    let exists = false
    try {
      const text = readFileSync(path, 'utf8')
      exists = true
      keys = parseSecretKeySet(text)
    } catch {
      // 文件不存在 = 未配置
    }
    let writable = false
    try {
      mkdirSync(stockHome(), { recursive: true })
      const probe = join(stockHome(), '.write-probe')
      writeFileSync(probe, '')
      unlinkSync(probe)
      writable = true
    } catch {
      writable = false
    }
    const keyMap = Object.fromEntries(SECRET_KEYS.map((key) => [key, keys.has(key)])) as Record<SecretKey, boolean>
    return {
      stockHome: stockHome(),
      secretsPath: path,
      secretsExists: exists,
      secretsWritable: writable,
      keys: keyMap,
      skillCount: loadSkillsCatalog(this.root).skills.length,
    }
  }

  skills(): SkillsCatalogFile {
    return loadSkillsCatalog(this.root)
  }

  /** 合并写入凭据：只更新 payload 里出现且非空的键；返回落盘的键名。 */
  saveSecrets(updates: Partial<Record<SecretKey, string>>): { readonly saved: readonly SecretKey[] } {
    const path = secretsPath()
    const applied: SecretKey[] = []
    for (const key of SECRET_KEYS) {
      const value = updates[key]
      if (typeof value !== 'string' || value.trim() === '') continue
      applied.push(key)
    }
    if (applied.length === 0) throw new ServiceError('empty', '没有需要保存的凭据（提供 TUSHARE_TOKEN / IWENCAI_API_KEY 至少一项）')

    let existing = ''
    try {
      existing = readFileSync(path, 'utf8')
    } catch {
      existing = ''
    }
    const lines = existing.length > 0 ? existing.replace(/\n+$/, '').split(/\r?\n/) : []
    for (const key of applied) {
      const rendered = `${key}=${updates[key]!.trim()}`
      const at = lines.findIndex((line) => {
        const trimmed = line.trim()
        return !trimmed.startsWith('#') && trimmed.startsWith(`${key}=`)
      })
      if (at >= 0) lines[at] = rendered
      else lines.push(rendered)
    }
    mkdirSync(stockHome(), { recursive: true })
    const tmp = `${path}.tmp-${process.pid}-${Date.now()}`
    writeFileSync(tmp, `${lines.join('\n')}\n`, { mode: 0o600 })
    chmodSync(tmp, 0o600)
    renameSync(tmp, path)
    try {
      chmodSync(path, 0o600)
    } catch {
      // 个别文件系统不支持 chmod；rename 前已按 0600 创建
    }
    return { saved: applied }
  }
}
