#!/usr/bin/env node
/**
 * dsh-skills-stock 插件冒烟测试（零依赖，node scripts/smoke-plugin.mjs）。
 *
 * 覆盖面：
 * 1. 清单一致性：skills/manifest.json ↔ 磁盘技能目录 ↔ SKILL.md frontmatter
 *   name ↔ package.json files 白名单；dsh 注册名必须 kebab-case（宿主
 *   /^[a-z0-9]+(-[a-z0-9]+)*$/ 硬校验）；
 * 2. 适配纯度：适配产物不得残留 QiLin/KStock 宿主语义（/mnt 沙箱路径、
 *   render_html_report/present 调用、沙箱密钥注入措辞、桌面端本地 API
 *   kstock-api/18001、sandbox-path-guide 引用、~/.kstock 路径）；
 *   带密钥技能必须有「凭据配置」节，无密钥技能不得有；
 * 3. host：lib/index.js apply() 全流程（stub ctx：30 × skills.register +
 *   1 × systemPrompt.section + 1 × webServer RPC 通道 + 旧预设目录清理；
 *   disposer 回收；enabled:false / announceToAgent:false）；
 * 4. RPC 语义：handleWorkbenchRpc 直测 status/skills/save_secrets
 *   （HOME 重定向的临时 secrets.env：合并写、0600、值不回传、坏输入拒绝）；
 * 5. 能力通告：技能路由覆盖全部技能名 + 跨技能约定关键词在场；
 * 6. client 产物：lib/client.js 走 __ModuleLoader__ 契约、注册
 *   sidebar.panellist + main 官方 slot、面板含数据源/技能库区块；
 * 7. cordis.patch.yml id 与插件名对账；无 presets/ 残留。
 *
 * 隔离：HOME 重定向到临时目录并清空 QILIN_HOME/DSH_HOME，测试不触碰真实用户数据。
 */
import { mkdtempSync, mkdirSync, existsSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const EXPECTED_SKILL_COUNT = 41

let failures = 0
function check(name, condition, detail = '') {
  const mark = condition ? 'PASS' : 'FAIL'
  console.log(`\x1b[${condition ? 32 : 31}m${mark}\x1b[0m  ${name}${detail ? ' — ' + detail : ''}`)
  if (!condition) failures += 1
}

/* ═══ 1. 清单一致性 ═══ */

const pkg = JSON.parse(readFileSync(join(packageRoot, 'package.json'), 'utf8'))
const manifest = JSON.parse(readFileSync(join(packageRoot, 'skills', 'manifest.json'), 'utf8'))

check('package.json name = dsh-skills-stock', pkg.name === 'dsh-skills-stock')
check('dsh.bundle.patch 指向存在的 cordis.patch.yml', pkg.dsh?.bundle?.patch === './cordis.patch.yml' && existsSync(join(packageRoot, 'cordis.patch.yml')))
check('main 入口 lib/index.js 存在（构建产物随仓提交）', pkg.main === './lib/index.js' && existsSync(join(packageRoot, 'lib', 'index.js')))
check('exports ./client → lib/client.js 存在', pkg.exports?.['./client'] === './lib/client.js' && existsSync(join(packageRoot, 'lib', 'client.js')))
check('dsh.client 声明 platform=web 与 inject 列表', pkg.dsh?.client?.platform === 'web' && Array.isArray(pkg.dsh?.client?.inject) && pkg.dsh.client.inject.length >= 3)

for (const need of ['lib', 'skills', 'cordis.patch.yml', 'README.md', 'LICENSE']) {
  check(`files 白名单含 ${need}`, Array.isArray(pkg.files) && pkg.files.includes(need))
}

check(`manifest.skills 共 ${EXPECTED_SKILL_COUNT} 个`, Array.isArray(manifest.skills) && manifest.skills.length === EXPECTED_SKILL_COUNT, `实际 ${manifest.skills?.length}`)
check('技能名唯一', new Set(manifest.skills.map((s) => s.name)).size === manifest.skills.length)
check('技能名全部 kebab-case（宿主硬校验 /^[a-z0-9]+(-[a-z0-9]+)*$/）',
  manifest.skills.every((s) => /^[a-z0-9]+(-[a-z0-9]+)*$/.test(s.name)),
  manifest.skills.filter((s) => !/^[a-z0-9]+(-[a-z0-9]+)*$/.test(s.name)).map((s) => s.name).join(', '))

for (const item of manifest.skills) {
  const dir = join(packageRoot, 'skills', item.dir)
  check(`技能目录存在：${item.dir}`, existsSync(join(dir, 'SKILL.md')))
  const raw = readFileSync(join(dir, 'SKILL.md'), 'utf8')
  const fm = raw.startsWith('---\n') ? raw.slice(4, raw.indexOf('\n---\n', 4)) : ''
  const nameMatch = fm.match(/^name:\s*([^"\n]+)\s*$/m)
  check(`frontmatter name 对账：${item.dir}`, !!nameMatch && nameMatch[1].trim() === item.name,
    nameMatch ? `frontmatter=${nameMatch[1].trim()} manifest=${item.name}` : 'frontmatter 无 name 行')
  check(`description 非空且 ≤500 字（catalog 上限）：${item.name}`,
    typeof item.description === 'string' && item.description.length > 10 && item.description.length <= 500,
    `长度 ${item.description?.length}`)
  check(`whenToUse 非空：${item.name}`, typeof item.whenToUse === 'string' && item.whenToUse.length > 10)
  // 正文（frontmatter 之外）不得残留 QiLin 宿主语义
  const body = raw.startsWith('---\n') ? raw.slice(raw.indexOf('\n---\n', 4) + 5) : raw
  const residuals = [
    [/\/mnt\/(skills|user-data|cache)/, '残留 /mnt 沙箱路径'],
    [/render_html_report\(|render_html_report_from_file|present_files/, '残留 QiLin 内置工具调用'],
    [/由系统注入沙箱环境/, '残留沙箱密钥注入措辞'],
    [/wait_for_background_task/, '残留 QiLin 后台任务工具'],
    [/kstock-api|127\.0\.0\.1:18001/, '残留 KStock 桌面端本地 API 引用'],
    [/`present`|present 呈现/, '残留 QiLin present 工具引用'],
    [/sandbox-path-guide/, '残留 sandbox-path-guide 技能引用'],
    [/~\/kstock/, '残留 ~/.kstock 宿主路径'],
    [/均 curl POST/, '残留 curl 入库措辞'],
    [/PATCH \/kstock-api/, '残留 PATCH 入库措辞'],
    [/◆TODO◆|workflow 工具的 meta 参数/, '残留 QiLin workflow 模板语义'],
  ].filter(([p]) => p.test(body)).map(([, label]) => label)
  check(`适配纯度：${item.name}`, residuals.length === 0, residuals.join('; '))
  // 凭据节与 requiredSecrets 对账
  const hasCredSection = body.includes('## 凭据配置')
  const needCred = Array.isArray(item.requiredSecrets) && item.requiredSecrets.length > 0
  check(`凭据配置节对账：${item.name}`, needCred === hasCredSection,
    needCred ? '缺凭据节' : '无密钥却带凭据节')
  if (needCred) {
    for (const secret of item.requiredSecrets) {
      check(`凭据节声明 ${secret}：${item.name}`, body.includes(`\`${secret}\``))
    }
  }
}

/* ═══ 2. host：lib/index.js apply() 全流程 ═══ */

const fakeHome = mkdtempSync(join(tmpdir(), 'stock-smoke-'))
process.env.HOME = fakeHome
// 关键隔离：本机 shell 可能带着全局 QILIN_HOME/DSH_HOME（KCoder 桌面端把
// DSH_HOME 指到 ~/.kcoder）。旧预设清理与状态读写跟随宿主 home，不先删掉
// 就会触碰真实用户数据。
delete process.env.QILIN_HOME
delete process.env.DSH_HOME

// 预置一个历史版本预设目录，apply 后必须被幂等清理（super-ppts 同款语义）；
// 同时预置 v1.1 旧数据根（~/.dsh-stock/secrets.env），apply 后必须迁移到
// <宿主 home>/dsh-skills-stock/（DSH_HOME/QILIN_HOME 未设 → ~/.dsh 下）。
const legacyPresetDir = join(fakeHome, '.dsh', '.agent-presets', 'dsh-skills-stock')
mkdirSync(legacyPresetDir, { recursive: true })
mkdirSync(join(fakeHome, '.dsh-stock'), { recursive: true })
writeFileSync(join(fakeHome, '.dsh-stock', 'secrets.env'), 'TUSHARE_TOKEN=legacy-migrate-test\n', { mode: 0o600 })

const plugin = await import(join(packageRoot, 'lib', 'index.js'))
check('host 命名导出 name/inject/apply', plugin.name === 'dsh-skills-stock' && Array.isArray(plugin.inject) && typeof plugin.apply === 'function')
check('inject 声明 skills + systemPrompt + webServer + connection + tools',
  ['skills', 'systemPrompt', 'webServer', 'connection', 'tools'].every((s) => plugin.inject.includes(s)))

const registered = []
const sections = []
const rpcChannels = []
const toolNames = []
const ctx = {
  skills: {
    register(spec) {
      registered.push(spec)
      return () => { registered.splice(registered.indexOf(spec), 1) }
    },
  },
  systemPrompt: {
    section(spec) {
      sections.push(spec)
      return () => { sections.splice(sections.indexOf(spec), 1) }
    },
  },
  tools: {
    register(definition) {
      toolNames.push(definition.name)
      return () => { toolNames.splice(toolNames.indexOf(definition.name), 1) }
    },
  },
  webServer: {
    register(spec) {
      rpcChannels.push(spec)
      return () => { rpcChannels.splice(rpcChannels.indexOf(spec), 1) }
    },
  },
  connection: { requestRejection: () => undefined },
  effect(fn) {
    const cleanup = fn()
    return () => { if (typeof cleanup === 'function') cleanup() }
  },
}

const dispose = plugin.apply(ctx, {})
check(`注册 ${EXPECTED_SKILL_COUNT} 个 runtime skill`, registered.length === EXPECTED_SKILL_COUNT, `${registered.length}`)
check('注册 18 个 agent 工具（三库 15 + 报告库 3）', toolNames.length === 18, toolNames.join(', '))
check('注册 1 段能力通告 section', sections.length === 1 && sections[0].name === 'plugin:dsh-skills-stock')
check('通告排序为 209', sections[0]?.order === 209)
check('每个 skill 注册带 resourceBase 目录', registered.every((s) => s.resourceBase?.kind === 'directory' && existsSync(s.resourceBase.path)))
check('每个 skill 内容已剥离 frontmatter', registered.every((s) => !s.content.startsWith('---\n')))
check('带密钥 skill 的 metadata 透传 requiredSecrets',
  registered.filter((s) => s.metadata?.requiredSecrets?.length).every((s) => manifest.skills.find((m) => m.name === s.name).requiredSecrets.length > 0))
check('注册 /dsh-skills-stock RPC 通道（prefix）',
  rpcChannels.length === 1 && rpcChannels[0].kind === 'prefix' && rpcChannels[0].path === '/dsh-skills-stock')
check('旧预设目录已被幂等清理', !existsSync(legacyPresetDir))
check('旧数据根 ~/.dsh-stock 已迁移到 <宿主home>/dsh-skills-stock',
  !existsSync(join(fakeHome, '.dsh-stock'))
  && readFileSync(join(fakeHome, '.dsh', 'dsh-skills-stock', 'secrets.env'), 'utf8').includes('legacy-migrate-test'))

dispose()
check('disposer 后 skills/sections/工具/通道全部回收', registered.length === 0 && sections.length === 0 && rpcChannels.length === 0 && toolNames.length === 0)

// enabled:false 短路
{
  const reg2 = []
  const ctx2 = {
    skills: { register: (s) => { reg2.push(s); return () => {} } },
    systemPrompt: { section: () => () => {} },
    webServer: { register: () => () => {} },
    connection: {},
    effect: (fn) => fn(),
  }
  const d2 = plugin.apply(ctx2, { enabled: false })
  check('enabled:false 时零注册', reg2.length === 0 && typeof d2 === 'function')
}

/* ═══ 3. RPC 语义 + 三库存储 + agent 工具（HOME 隔离下直测） ═══ */

{
  const { handleWorkbenchRpc, WorkbenchService, LibraryStore, libraryToolDefs, reportToolDefs } = await import(join(packageRoot, 'lib', 'index.js'))
  const signal = new AbortController().signal
  const serviceHome = mkdtempSync(join(tmpdir(), 'stock-rpc-'))
  process.env.HOME = serviceHome
  const svc = new WorkbenchService(packageRoot)
  const library = new LibraryStore()
  const { ReportStore, MAX_REPORT_BYTES } = await import(join(packageRoot, 'lib', 'index.js'))
  const reportStore = new ReportStore()

  check('status 返回 ok 且含键状态位', await (async () => {
    const r = await handleWorkbenchRpc(svc, library, reportStore, 'status', {}, signal)
    return r.ok === true && typeof r.value?.keys?.TUSHARE_TOKEN === 'boolean'
  })())
  check('status 不回传任何密钥值', await (async () => {
    const r = await handleWorkbenchRpc(svc, library, reportStore, 'status', {}, signal)
    return !JSON.stringify(r).includes('你的') && !('secretsValue' in (r.value ?? {}))
  })())

  const secretsFile = join(serviceHome, '.dsh', 'dsh-skills-stock', 'secrets.env')
  const r2 = await handleWorkbenchRpc(svc, library, reportStore, 'save_secrets', { TUSHARE_TOKEN: 'tok-abc123' }, signal)
  check('save_secrets 合并写入成功', r2.ok === true && r2.value?.saved?.includes('TUSHARE_TOKEN') === true)
  check('secrets.env 已落盘（默认 ~/.dsh/dsh-skills-stock/）', existsSync(secretsFile))
  check('secrets.env 权限 0600', (statSync(secretsFile).mode & 0o777) === 0o600)
  const r3 = await handleWorkbenchRpc(svc, library, reportStore, 'save_secrets', { IWENCAI_API_KEY: 'key-xyz' }, signal)
  const text = readFileSync(secretsFile, 'utf8')
  check('两次写入共存（合并语义）', r3.ok === true && text.includes('TUSHARE_TOKEN=tok-abc123') && text.includes('IWENCAI_API_KEY=key-xyz'))
  const r4 = await handleWorkbenchRpc(svc, library, reportStore, 'save_secrets', { TUSHARE_TOKEN: 'bad\nvalue' }, signal)
  check('含换行的凭据值被拒绝', r4.ok === false)
  check('skills 返回 41 条目录', await (async () => {
    const r = await handleWorkbenchRpc(svc, library, reportStore, 'skills', {}, signal)
    return r.ok === true && r.value?.skills?.length === EXPECTED_SKILL_COUNT
  })())

  // DSH_HOME 正向：数据根必须跟随宿主 home 变量（KCoder ~/.kcoder 场景）
  const dshHomeDir = join(serviceHome, 'dsh-home')
  process.env.DSH_HOME = dshHomeDir
  try {
    const svc2 = new WorkbenchService(packageRoot)
    const lib2 = new LibraryStore()
    const st = await handleWorkbenchRpc(svc2, lib2, reportStore, 'status', {}, signal)
    const expectedSecrets = join(dshHomeDir, 'dsh-skills-stock', 'secrets.env')
    check('status.secretsPath 跟随 DSH_HOME', st.ok === true && st.value?.secretsPath === expectedSecrets)
    const r5 = await handleWorkbenchRpc(svc2, lib2, reportStore, 'save_secrets', { TUSHARE_TOKEN: 'dsh-home-tok' }, signal)
    check('DSH_HOME 下凭据写入成功', r5.ok === true && existsSync(expectedSecrets)
      && readFileSync(expectedSecrets, 'utf8').includes('dsh-home-tok'))
    const obj = lib2.createObject('strategies', { name: 'DSH_HOME 库位' })
    check('三库存储落在 $DSH_HOME/dsh-skills-stock/product', existsSync(join(dshHomeDir, 'dsh-skills-stock', 'product', 'strategies', obj.object_id, 'object.json')))
  } finally {
    delete process.env.DSH_HOME
  }

  // 三库存储：create → 乐观锁 → record_run → RPC 读回
  const created = library.createObject('strategies', { name: '冒烟策略', hypothesis: '测试假设' })
  const strategyId = created.object_id
  check('strategy create 生成 stg_ id', typeof strategyId === 'string' && strategyId.startsWith('stg_'))
  const conflict = (() => { try { library.saveVersion('strategies', strategyId, { code: 'x', change_note: 'n', parent_version: 5 }); return false } catch (e) { return e.code === 'version-conflict' } })()
  check('parent_version 不符报版本冲突', conflict === true)
  const v1 = library.saveVersion('strategies', strategyId, { code: 'def run(): pass', params: { top_n: 5 }, change_note: 'v1', parent_version: 0 })
  check('save_version 落 v1', v1.version === 1)
  const run = library.recordRun('strategies', strategyId, { version: 1, data_start: '20240101', data_end: '20241231', rules: { t_plus_1: true }, metrics: { total_return_pct: 12.5, sharpe_ratio: 1.1 } })
  check('record_run 归档 srun_ id', typeof run.run_id === 'string' && run.run_id.startsWith('srun_'))
  const runEquity = library.recordRun('strategies', strategyId, {
    version: 1,
    metrics: { total_return_pct: 8.1, sharpe_ratio: 0.9 },
    equity: [{ date: '2024-01-01', equity: 1.0 }, { date: '2024-06-30', equity: 1.06 }, { date: '2024-12-31', equity: 1.081 }],
  })
  check('library_detail 读回版本与运行', await (async () => {
    const r = await handleWorkbenchRpc(svc, library, reportStore, 'library_detail', { kind: 'strategies', object_id: strategyId }, signal)
    return r.ok === true && r.value?.versions?.length === 1 && r.value?.runs?.length === 2
  })())
  check('library_detail 运行为轻量投影（剥离 equity 曲线负载）', await (async () => {
    const r = await handleWorkbenchRpc(svc, library, reportStore, 'library_detail', { kind: 'strategies', object_id: strategyId }, signal)
    return r.value?.runs?.every((x) => !('equity' in x) && !('trades' in x)) === true
  })())
  check('library_list latest_run 同样剥离曲线负载', await (async () => {
    const r = await handleWorkbenchRpc(svc, library, reportStore, 'library_list', { kind: 'strategies' }, signal)
    return r.ok === true && r.value?.items?.length === 1
      && r.value.items[0]?.latest_run !== undefined && !('equity' in r.value.items[0].latest_run)
  })())

  // 运行对比端点：整批取回完整曲线（KStock 两段式第二段）
  const runsRpc = await handleWorkbenchRpc(svc, library, reportStore, 'library_runs', { kind: 'strategies', object_id: strategyId, run_ids: [run.run_id, runEquity.run_id] }, signal)
  check('library_runs 返回完整运行（含 equity 曲线）', runsRpc.ok === true
    && runsRpc.value?.runs?.length === 2
    && Array.isArray(runsRpc.value.runs.find((x) => x.run_id === runEquity.run_id)?.equity)
    && runsRpc.value.runs.find((x) => x.run_id === run.run_id)?.equity === undefined)
  const runsOne = await handleWorkbenchRpc(svc, library, reportStore, 'library_runs', { kind: 'strategies', object_id: strategyId, run_ids: [run.run_id] }, signal)
  check('library_runs 少于 2 个 run_id 被拒绝', runsOne.ok === false && runsOne.error?.code === 'invalid')
  const runsFive = await handleWorkbenchRpc(svc, library, reportStore, 'library_runs', { kind: 'strategies', object_id: strategyId, run_ids: ['a', 'b', 'c', 'd', 'e'] }, signal)
  check('library_runs 超过 4 个 run_id 被拒绝', runsFive.ok === false)
  const runsGhost = await handleWorkbenchRpc(svc, library, reportStore, 'library_runs', { kind: 'strategies', object_id: strategyId, run_ids: [run.run_id, 'srun_nosuchrun'] }, signal)
  check('library_runs 未知 run_id 报 not-found', runsGhost.ok === false && runsGhost.error?.code === 'not-found')
  const runsEvil = await handleWorkbenchRpc(svc, library, reportStore, 'library_runs', { kind: 'strategies', object_id: strategyId, run_ids: [run.run_id, '../../etc/passwd'] }, signal)
  check('library_runs 非法字符 run_id 被拒绝（路径穿越）', runsEvil.ok === false && runsEvil.error?.code === 'invalid')
  const badKind = await handleWorkbenchRpc(svc, library, reportStore, 'library_list', { kind: 'nope' }, signal)
  check('非法 kind 被拒绝', badKind.ok === false)
  check('错误信封带 details（宿主连接层客户端必填，缺失会被替换成 invalid server-response）',
    badKind.ok === false && typeof badKind.error?.code === 'string' && typeof badKind.error?.message === 'string'
    && typeof badKind.error?.details === 'object' && badKind.error.details !== null)

  // 选股库：create 自动落 v1 且 criteria_json.summary 必填
  const selCreated = library.createObject('selections', { name: '高股息观察', criteria: '股息率>5% 的沪深300成分' })
  check('selection create 自动落 v1', library.detail('selections', selCreated.object_id).versions.length === 1)
  const noSummary = (() => { try { library.saveVersion('selections', selCreated.object_id, { criteria_json: { pool: 'hs300' }, change_note: 'x', parent_version: 1 }); return false } catch (e) { return e.code === 'invalid' } })()
  check('criteria_json.summary 缺失被拒绝', noSummary === true)

  // 报告库（KStock 2.0 quant-reports 同构）：归档 → 列表 → 读回 → 覆盖 → 边界
  const archived = reportStore.archive({ title: '冒烟看板', content: '<html><body>smoke report</body></html>', symbol: '600519.SH', risk_level: '低' })
  check('report_archive 派生 rpt_ id', typeof archived.report_id === 'string' && archived.report_id.startsWith('rpt_') && archived.updated === false)
  check('report content.html 落盘 0600', (statSync(archived.content_path).mode & 0o777) === 0o600)
  const reread = reportStore.get(archived.report_id, true)
  check('report_get 返回 HTML 全文', typeof reread.content === 'string' && reread.content.includes('smoke report'))
  const reportsList = await handleWorkbenchRpc(svc, library, reportStore, 'reports_list', {}, signal)
  check('reports_list 返回归档报告', reportsList.ok === true && reportsList.value?.items?.length === 1 && reportsList.value.items[0]?.title === '冒烟看板')
  const reportsGet = await handleWorkbenchRpc(svc, library, reportStore, 'reports_get', { report_id: archived.report_id }, signal)
  check('reports_get 默认不带全文', reportsGet.ok === true && reportsGet.value?.content === undefined && typeof reportsGet.value?.content_path === 'string')
  const overwritten = reportStore.archive({ title: '冒烟看板', content: '<html><body>v2</body></html>', report_id: archived.report_id })
  check('同 report_id 重复归档是覆盖更新', overwritten.updated === true && overwritten.sha256 !== archived.sha256 && reportStore.list().length === 1)
  const tooBig = (() => { try { reportStore.archive({ title: 'x', content: 'a'.repeat(MAX_REPORT_BYTES + 1) }); return false } catch (e) { return e.code === 'too-large' } })()
  check('报告超出 8MB 上限被拒绝', tooBig === true)
  const evilId = (() => { try { reportStore.archive({ title: 'x', content: '<p/>', reportId: '../escape' }); return false } catch (e) { return e.code === 'invalid' } })()
  check('report_id 路径穿越被拒绝', evilId === true)
  // content_path 文件通道：宿主端直读（大报告不经 LLM 上下文中转的关键口）
  const w40Dir = join(serviceHome, 'w40')
  mkdirSync(join(w40Dir, 'reports'), { recursive: true })
  writeFileSync(join(w40Dir, 'reports', 'weekly.html'), '<html><body>w40 via path</body></html>')
  const byRel = reportStore.archive({ title: '路径归档·相对', contentPath: 'reports/weekly.html', baseDir: w40Dir })
  check('content_path 相对路径以 baseDir 解析并落盘', byRel.ok === undefined && readFileSync(String(byRel.content_path), 'utf8').includes('w40 via path'))
  const byAbs = reportStore.archive({ title: '路径归档·绝对', contentPath: join(w40Dir, 'reports', 'weekly.html') })
  check('content_path 绝对路径直读', byAbs.size_bytes === Buffer.byteLength('<html><body>w40 via path</body></html>'))
  const unreadable = (() => { try { reportStore.archive({ title: 'x', contentPath: 'nope/missing.html', baseDir: serviceHome }); return false } catch (e) { return e.code === 'invalid' } })()
  check('content_path 不可读报 invalid', unreadable === true)
  const neither = (() => { try { reportStore.archive({ title: 'x' }); return false } catch (e) { return e.code === 'invalid' } })()
  check('content/content_path 均缺省报 invalid', neither === true)
  const ghostReport = await handleWorkbenchRpc(svc, library, reportStore, 'reports_get', { report_id: 'rpt_nosuchreport' }, signal)
  check('reports_get 未知 id 报 not-found', ghostReport.ok === false && ghostReport.error?.code === 'not-found')
  const evilReportGet = await handleWorkbenchRpc(svc, library, reportStore, 'reports_get', { report_id: '../../etc/passwd' }, signal)
  check('reports_get 非法 id 被拒绝（路径穿越）', evilReportGet.ok === false && evilReportGet.error?.code === 'invalid')

  // agent 工具：18 个定义（三库 15 + 报告库 3）+ list/archive 工具可执行
  const defs = [...libraryToolDefs(library), ...reportToolDefs(reportStore)]
  check('libraryToolDefs + reportToolDefs 共 18 个', defs.length === 18, `实际 ${defs.length}`)
  check('报告库工具注册名齐备', ['report_archive', 'report_list', 'report_get']
    .every((name) => defs.some((d) => d.name === name)))
  const archiveTool = defs.find((d) => d.name === 'report_archive')
  const archivedViaTool = await archiveTool.execute({ title: '工具直归档', content: '<p>via tool</p>' }, { agent: { session: { id: 'sess_tool' } } })
  check('report_archive 工具可执行并绑定会话线程', archivedViaTool?.ok === true && archivedViaTool.value?.thread_id === 'sess_tool')
  const archivedViaPath = await archiveTool.execute(
    { title: '工具直归档·路径', content_path: 'reports/weekly.html' },
    { agent: { session: { id: 'sess_tool', header: { cwd: join(serviceHome, 'w40') } } } },
  )
  check('report_archive 工具 content_path 相对会话 cwd 直读', archivedViaPath?.ok === true && typeof archivedViaPath.value?.content_path === 'string')
  check('工具注册名与 KStock 对齐', ['strategy_list', 'factor_save_version', 'selection_record_run', 'strategy_record_backtest', 'factor_get_latest']
    .every((name) => defs.some((d) => d.name === name)))
  const listTool = defs.find((d) => d.name === 'strategy_list')
  const listed = await listTool.execute({}, { agent: { session: { id: 'sess_x', header: { cwd: '/tmp' } } } })
  check('strategy_list 工具可执行', listed?.ok === true && listed.value?.items?.length === 1)

  // 因子库：ic_series 曲线同样走「detail 剥离 + library_runs 整批读回」
  const facCreated = library.createObject('factors', { name: '冒烟因子', hypothesis: '动量因子假设', category: 'momentum' })
  library.saveVersion('factors', facCreated.object_id, { code: 'def fac(df): pass', change_note: 'v1', parent_version: 0 })
  const frunA = library.recordRun('factors', facCreated.object_id, { version: 1, metrics: { ic_mean: 0.032, ir: 0.4 }, ic_series: [{ date: '2024-01', ic: 0.02 }, { date: '2024-02', ic: 0.05 }, { date: '2024-03', ic: 0.026 }] })
  const frunB = library.recordRun('factors', facCreated.object_id, { version: 1, metrics: { ic_mean: -0.01, ir: -0.2 }, ic_series: [0.01, -0.03, 0.02] })
  const facRunsRpc = await handleWorkbenchRpc(svc, library, reportStore, 'library_runs', { kind: 'factors', object_id: facCreated.object_id, run_ids: [frunA.run_id, frunB.run_id] }, signal)
  check('factors library_runs 返回 ic_series（对象/数值两形态）', facRunsRpc.ok === true
    && Array.isArray(facRunsRpc.value?.runs?.[0]?.ic_series) && Array.isArray(facRunsRpc.value?.runs?.[1]?.ic_series))

  process.env.HOME = fakeHome
  rmSync(serviceHome, { recursive: true, force: true })
}

/* ═══ 4. 能力通告路由覆盖 ═══ */

{
  const guidance = plugin.KSTOCK_GUIDANCE ?? sections[0]?.text ?? ''
  const names = manifest.skills.map((s) => s.name)
  const missing = names.filter((n) => !guidance.includes(n))
  check('通告路由覆盖全部技能名', missing.length === 0, missing.join(', '))
  for (const keyword of ['~/.dsh/dsh-skills-stock', '<数据根>/secrets.env', '$QILIN_HOME → $DSH_HOME',
    'TUSHARE_TOKEN', 'IWENCAI_API_KEY', 'set -a; source',
    '禁止编造数据', '不构成投资建议', '当前工作目录', 'skill_resources']) {
    check(`通告含约定关键词「${keyword}」`, guidance.includes(keyword))
  }
}

/* ═══ 5. client 产物静态检查 ═══ */

{
  const client = readFileSync(join(packageRoot, 'lib', 'client.js'), 'utf8')
  check('client 走 __ModuleLoader__ 自注册形态', client.includes('__ModuleLoader__.load') && client.includes('"dsh-skills-stock"'))
  check('client 注册官方 sidebar.panellist + main slot', client.includes('sidebar.panellist')
    && (client.includes('"main"') || client.includes("'main'")) && client.includes('kss-workbench'))
  check('client 注册设置页 settings.section（数据源）', client.includes('settings.section') && client.includes('kstock-data-sources'))
  check('client 工作台为四库 tab（策略/因子/选股/报告）', client.includes('strategies') && client.includes('factors') && client.includes('selections') && client.includes('reports'))
  check('client 报告库走 reports_list/reports_get 端点', client.includes('reports_list') && client.includes('reports_get'))
  check('client 报告详情内嵌 HTML 预览（kss-report-frame iframe）', client.includes('kss-report-frame') && client.includes('srcDoc'))
  check('client 会话桥（setDraft→submit，剪贴板降级）', client.includes('setDraft') && client.includes('submit') && client.includes('clipboard'))
  check('client 面板经 /dsh-skills-stock 通道调用', client.includes('/dsh-skills-stock') && client.includes('library_detail'))
  check('client 运行对比含曲线叠加（library_runs 端点 + 净值归一 + kss-curve SVG）',
    client.includes('library_runs') && client.includes('normalizeEquity') && client.includes('cumulativeIc')
    && client.includes('kss-curve-svg') && client.includes('"polyline"'))
  check('client 不内嵌 react（走宿主静态模块表）', !client.includes('react_dom') && !client.includes('node_modules/react'))
}

/* ═══ 6. cordis.patch.yml 对账 + 无预设残留 ═══ */

{
  const patch = readFileSync(join(packageRoot, 'cordis.patch.yml'), 'utf8')
  check('patch 声明 insert id = 包名', patch.includes('- id: dsh-skills-stock') && patch.includes("name: 'dsh-skills-stock'"))
  check('patch 头注释说明 bundle 注册路径与预设清理', patch.includes('dsh.bundle.patch') && patch.includes('agent-presets'))
  check('包内不存在 presets/ 目录（插件自造预设已失效）', !existsSync(join(packageRoot, 'presets')))
}

/* ═══ 清理与结论 ═══ */

rmSync(fakeHome, { recursive: true, force: true })
console.log('')
if (failures > 0) {
  console.log(`\x1b[31m冒烟失败：${failures} 项\x1b[0m`)
  process.exit(1)
}
console.log('\x1b[32m冒烟通过：清单 + 适配纯度 + host + RPC + 通告 + client + patch 全部检查项 ✓\x1b[0m')
