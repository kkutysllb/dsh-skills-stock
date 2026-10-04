/** 本机路径解析（super-ppts 同款宿主 home 口径）：插件数据根跟随宿主 home
 * 下的 dsh-skills-stock/，不写死用户 home 字面量——KCoder 桌面端把
 * DSH_HOME 指到 ~/.kcoder，插件数据必须跟着走。v1.0–1.1 的 ~/.dsh-stock
 * 旧位置在 apply 时幂等迁移（整项搬移、绝不覆盖目标既有文件）。 */

import { existsSync, mkdirSync, readdirSync, renameSync, rmSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

/** 用户 home（测试可覆写 HOME）。 */
export function userHome(): string {
  const fromEnv = process.env.HOME
  return fromEnv !== undefined && fromEnv.trim() !== '' ? fromEnv : homedir()
}

/** 宿主主目录解析（零依赖复刻宿主 home-paths 优先级）：
 * `$QILIN_HOME`（非空白）→ `$DSH_HOME`（非空白）→ `~/.dsh`。 */
export function harnessHome(): string {
  const fromEnv = process.env.QILIN_HOME ?? process.env.DSH_HOME
  return fromEnv !== undefined && fromEnv.trim() !== '' ? fromEnv : join(userHome(), '.dsh')
}

/** 插件数据根：<宿主 home>/dsh-skills-stock（secrets.env / product / cache 都在其下）。 */
export function stockHome(): string {
  return join(harnessHome(), 'dsh-skills-stock')
}

/** 凭据文件：<数据根>/secrets.env（0600）。 */
export function secretsPath(): string {
  return join(stockHome(), 'secrets.env')
}

/** v1.0–1.1 的数据位置（用户 home 下的 .dsh-stock 字面量），仅作迁移源。 */
export function legacyStockHomes(): string[] {
  return [...new Set([join(userHome(), '.dsh-stock'), join(homedir(), '.dsh-stock')])]
}

/** 旧数据根幂等迁移到当前数据根：逐项搬移、目标已存在则跳过（绝不覆盖）；
 * 搬空后删除旧目录。迁移失败不抛——宁可让用户重配凭据，也不能阻断加载。 */
export function migrateLegacyStockHome(): void {
  try {
    const root = stockHome()
    for (const legacy of legacyStockHomes()) {
      if (legacy === root || !existsSync(legacy)) continue
      mkdirSync(root, { recursive: true })
      for (const entry of readdirSync(legacy)) {
        const target = join(root, entry)
        if (existsSync(target)) continue
        renameSync(join(legacy, entry), target)
      }
      if (readdirSync(legacy).length === 0) rmSync(legacy, { recursive: true, force: true })
    }
  } catch {
    // 迁移失败不阻断插件加载
  }
}

/** 旧预设候选位（去重）：v1.0.0 开发期写入过 <宿主 home>/.agent-presets/
 * dsh-skills-stock；DSH 0.1.16 起插件自造预设已失效，apply 时幂等清理。 */
export function legacyPresetDirs(): string[] {
  const dirs = new Set<string>([
    join(harnessHome(), '.agent-presets', 'dsh-skills-stock'),
    join(userHome(), '.dsh', '.agent-presets', 'dsh-skills-stock'),
  ])
  return [...dirs]
}
