/** dsh-skills-stock Host 入口（DSH/Cordis 插件）。
 *
 * 职责（刻意保持最小面，对齐 super-ppts / kylin-automation 惯例）：
 * 1. 旧预设清理：DSH 0.1.16 起 agent-presets 按 agent.cordis.yml 组合挂载，
 *    插件自造预设已失效；apply 时幂等清理历史版本写入的
 *    <宿主 home>/.agent-presets/dsh-skills-stock/（best-effort，失败不阻断加载）。
 * 2. 技能注册：读取包内 skills/manifest.json，逐个读取 SKILL.md 剥离
 *    frontmatter 后经 ctx.skills.register() 注册为 runtime skill（30 个，
 *    全局层，全 profile 会话可见；rank 250）。
 * 3. 能力通告：向 systemPrompt 注册一段能力路由与跨技能约定 section
 *    （可经 config.announceToAgent 关闭）。
 * 4. 工作台通道：注册 /dsh-skills-stock RPC 通道（数据源凭据受控写入 +
 *    技能目录只读查询），供 Web 侧边栏「投研工作台」面板使用。
 *
 * Cordis 契约（家族插件实装结论）：
 * - host 侧访问的每个 ctx 服务必须经命名导出 inject 声明——
 *   `cannot get property "skills" without inject` 即漏声明症状；
 * - apply 返回/内部 effect 的 disposer 由宿主 fiber 释放时自动回收。
 *
 * 部署注意（KCoder 打包态）：不 import 任何 @deepseek-ai/* 运行时——
 * 服务经 inject 名字到达；只依赖 node 内置模块。
 */

import { readFileSync, rmSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { KSTOCK_GUIDANCE, SECTION_ORDER } from './guidance.ts'
import { LibraryStore } from './library.ts'
import { registerWorkbenchRpc } from './rpc.ts'
import { WorkbenchService, type SkillManifestEntry } from './service.ts'
import { libraryToolDefs } from './tools.ts'
import { legacyPresetDirs, migrateLegacyStockHome } from './stock-home.ts'

// 测试与下游集成面：RPC 端点直测、服务直构、通告文本
export { handleWorkbenchRpc, RPC_CHANNEL } from './rpc.ts'
export { WorkbenchService, SECRET_KEYS } from './service.ts'
export { LibraryStore, LibraryError } from './library.ts'
export { libraryToolDefs, ToolRejection } from './tools.ts'
export { KSTOCK_GUIDANCE, SECTION_ORDER } from './guidance.ts'
export { stockHome, secretsPath, migrateLegacyStockHome } from './stock-home.ts'

/** Stable Cordis plugin name. */
export const name = 'dsh-skills-stock'

/** apply 内访问的 ctx 服务（漏声明即抛 without inject）。 */
export const inject = ['skills', 'systemPrompt', 'webServer', 'connection', 'tools'] as const

/** 包根（lib/index.js 的上一级）。 */
export const packageRoot = dirname(fileURLToPath(new URL('.', import.meta.url)))

/** 插件配置（patch 行 config）。 */
export interface Config {
  enabled?: boolean
  announceToAgent?: boolean
  registerTools?: boolean
}

interface SkillsService {
  register(spec: {
    name: string
    description: string
    whenToUse?: string
    source: string
    content: string
    resourceBase: { kind: 'directory'; path: string }
    metadata?: Record<string, unknown>
  }): () => void
}

interface SystemPromptService {
  section(spec: { name: string; order: number; text: string }): () => void
}

interface ToolsService {
  register(definition: unknown): () => void
}

/** 剥离 SKILL.md 开头的 YAML frontmatter 块（--- 限界），返回正文。 */
export function stripFrontmatter(raw: string): string {
  if (!raw.startsWith('---\n')) return raw
  const end = raw.indexOf('\n---\n', 4)
  if (end === -1) return raw
  return raw.slice(end + 5).replace(/^\n+/, '')
}

/** 幂等清理历史版本的插件预设目录（best-effort；失败静默跳过）。 */
export function cleanupLegacyPresets(): void {
  for (const dir of legacyPresetDirs()) {
    try {
      rmSync(dir, { recursive: true, force: true })
    } catch {
      // 清理失败不阻断插件加载
    }
  }
}

/** 注册清单内全部技能；返回组合 disposer。 */
export function registerSkills(skills: SkillsService, root: string): () => void {
  const manifest = JSON.parse(readFileSync(join(root, 'skills', 'manifest.json'), 'utf8')) as { skills: SkillManifestEntry[] }
  const disposers: Array<() => void> = []
  for (const item of manifest.skills) {
    const dir = join(root, 'skills', item.dir)
    const content = stripFrontmatter(readFileSync(join(dir, 'SKILL.md'), 'utf8'))
    disposers.push(skills.register({
      name: item.name,
      description: item.description,
      ...(item.whenToUse === undefined ? {} : { whenToUse: item.whenToUse }),
      source: 'runtime',
      content,
      // 正文引用的相对资源（scripts/、references/、assets/）按此基目录解析
      resourceBase: { kind: 'directory', path: dir },
      // 自由元数据：凭据需求随注册透传（宿主不消费，便于诊断与下游集成）
      ...(item.requiredSecrets?.length ? { metadata: { requiredSecrets: [...item.requiredSecrets] } } : {}),
    }))
  }
  console.log(`dsh-skills-stock: ${disposers.length} runtime skills registered (${manifest.skills.map((s) => s.name).join(', ')})`)
  return () => {
    for (const dispose of disposers) {
      try {
        dispose()
      } catch {
        // 回收失败不阻断卸载
      }
    }
  }
}

/** 插件 apply。config: { enabled?: boolean, announceToAgent?: boolean, registerTools?: boolean } */
export function apply(ctx: {
  skills: SkillsService
  systemPrompt: SystemPromptService
  tools?: ToolsService
  webServer: Parameters<typeof registerWorkbenchRpc>[0]['webServer']
  connection: Parameters<typeof registerWorkbenchRpc>[0]['connection']
  effect(fn: () => () => void, name?: string): () => void
}, config: Config = {}): () => void {
  if (config.enabled === false) return () => {}

  // 迁移必须先于一切 stockHome() 读方（三库存储/凭据状态）
  migrateLegacyStockHome()
  cleanupLegacyPresets()

  const disposers: Array<() => void> = []
  disposers.push(registerSkills(ctx.skills, packageRoot))

  if (config.announceToAgent !== false) {
    disposers.push(ctx.systemPrompt.section({
      name: `plugin:${name}`,
      order: SECTION_ORDER,
      text: KSTOCK_GUIDANCE,
    }))
  }

  // 三库存储 + agent 工具（15 个 *_store 工具；registerTools:false 可关闭）
  const library = new LibraryStore()
  if (config.registerTools !== false && ctx.tools !== undefined) {
    for (const def of libraryToolDefs(library)) {
      disposers.push(ctx.tools.register(def))
    }
  }

  disposers.push(registerWorkbenchRpc(ctx as never, new WorkbenchService(packageRoot), library))

  return () => {
    for (const dispose of disposers) {
      try {
        dispose()
      } catch {
        // 回收失败不阻断卸载
      }
    }
  }
}
