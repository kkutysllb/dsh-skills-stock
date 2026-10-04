#!/usr/bin/env node
/**
 * KStock 技能包 → dsh-skills-stock 适配器（开发期工具，产物物化进包）。
 *
 * 方向：KStock 仓 vendor/skills/public/<name>/ → 本包 skills/<dir>/。
 * KStock 的技能体系（QiLin SKILL.md 规范：frontmatter name+description +
 * required-secrets，正文指导 agent 跑 scripts/ 下的 Python CLI）与 dsh 的
 * runtime skill 模型（正文 markdown + resourceBase 相对资源解析）同构，
 * 适配只处理两类宿主差异：
 *
 * 1. QiLin 沙箱语义 → dsh 语义（纯文本替换，规则见 BODY_RULES）：
 *    /mnt/skills/public/<name> 绝对路径 → 相对技能包根的路径；
 *    /mnt/user-data → 当前工作目录；render_html_report 看板工具 → 直接落盘
 *    单文件 HTML；密钥「由系统注入沙箱环境」→ 凭据文件 source 约定。
 * 2. 密钥通道：dsh 的 bash 子进程会剥离名字含 TOKEN/KEY/SECRET/PASSWORD
 *    的进程环境变量（subprocess scrub），故正文统一改写为
 *    「数据根 secrets.env 凭据文件 + 运行前 source」的约定；数据根 =
 *    <宿主 home>/dsh-skills-stock（宿主 home 按 $QILIN_HOME → $DSH_HOME →
 *    ~/.dsh 解析，不写死用户 home 字面量）；
 *    Python 脚本本身只读 os.environ，bash 内 export 即可达，无需改脚本。
 *
 * 脚本级修补（SCRIPT_PATCHES）仅 4 处硬编码路径：两个 *_cli.py 的
 * COMMON_CANDIDATE_PATHS 改为按脚本位置解析同级 common 包；
 * strategy-research 两个 analysis 模块 docstring 示例路径改占位说明；
 * common/market_data_cache.py 的缓存目录从 ~/.kstock 写死改为宿主 home
 * 口径（<数据根>/cache/market-data，与凭据/三库同根）。
 *
 * 用法：node scripts/adapt-kstock-skills.mjs
 * 环境变量：KSTOCK_REPO 可覆盖 KStock 仓位置（缺省 ../KStock）。
 * 产物可复现：同步排除 __pycache__/build/egg-info，SKILL.md 重写 frontmatter
 * 为最小 schema，manifest.json 由本脚本单一产出（smoke 脚本对账）。
 */
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PACKAGE_ROOT = resolve(__dirname, '..')
const KSTOCK_REPO = process.env.KSTOCK_REPO
  ? resolve(process.env.KSTOCK_REPO)
  : resolve(PACKAGE_ROOT, '..', 'KStock')
const SRC_PUBLIC = join(KSTOCK_REPO, 'vendor', 'skills', 'public')
const OUT_SKILLS = join(PACKAGE_ROOT, 'skills')

/* ═══════════════ 技能清单（单一事实源，顺序即 manifest 顺序） ═══════════════
 * dir: KStock 源目录名（= 输出目录名）；name: dsh 注册名（必须 kebab-case，
 * backtrader_strategies 因下划线改名）；whenToUse: 目录路由提示；
 * category: 便于 README 分组的类别；note: 追加到适配说明的特殊约定。 */
const SPEC = [
  { dir: 'stock-analysis', name: 'stock-analysis', category: '个股研究',
    whenToUse: '用户要深度分析某只 A 股个股（技术面/财务面/财报解读/筹码/估值/缠论/波浪/谐波/舆情/股东任一维度）、出个股研报、或问某股票值不值得买时使用；十四维一体分析引擎' },
  { dir: 'financial-statement', name: 'financial-statement', category: '个股研究',
    whenToUse: '用户要解读三大报表、盈利质量评分、财务造假红旗检测、杜邦分析时使用' },
  { dir: 'earnings-forecast', name: 'earnings-forecast', category: '个股研究',
    whenToUse: '用户要券商盈利预测数据（EPS/净利润一致预期、评级分布、目标价）或盈利超预期（SUE/PEAD）分析时使用' },
  { dir: 'earnings-revision', name: 'earnings-revision', category: '个股研究',
    whenToUse: '用户要分析盈利预期修正、业绩指引变化、分析师上调/下调动向时使用' },
  { dir: 'valuation-model', name: 'valuation-model', category: '个股研究',
    whenToUse: '用户要相对估值分析（PE-Band、PB-ROE、历史分位、多模型交叉验证）或估值陷阱检测时使用' },
  { dir: 'dcf', name: 'dcf', category: '个股研究',
    whenToUse: '用户要对公司做 DCF 绝对估值建模（含 Excel 模型输出）时使用' },
  { dir: 'selection-strategies', name: 'selection-strategies', category: '选股与策略',
    whenToUse: '用户要按既定选股策略跑批（价值投资/高股息/成长股/动量突破/技术突破/超跌反弹/涨停龙头/资金追踪/缠论背驰/多因子横截面十大策略）时使用' },
  { dir: 'a-stock-screener', name: 'a-stock-screener', category: '选股与策略',
    whenToUse: '用户用自然语言描述选股条件（如「低估值高股息、市值 100-300 亿、ROE 大于 15」）要一批候选股票时使用；对话式选股编排器' },
  { dir: 'factor-research', name: 'factor-research', category: '选股与策略',
    whenToUse: '用户要做因子研究（IC/IR 分析、分层回测、因子合成、六因子选股）时使用' },
  { dir: 'strategy-research', name: 'strategy-research', category: '选股与策略',
    whenToUse: '用户要设计、开发或回测量化策略（内置策略模板、参数网格扫描、walk-forward 滚动回测）时使用' },
  { dir: 'backtrader_strategies', name: 'backtrader-strategies', category: '选股与策略',
    whenToUse: 'backtrader 回测执行时被 strategy-research 等技能引用的 8 策略适配器库；用户明确要这 8 个适配策略（动量突破/资金追踪/高股息/价值投资等）的回测实现细节时使用' },
  { dir: 'cb-analysis', name: 'cb-analysis', category: '品种专项',
    whenToUse: '用户要分析可转债（转债行情、转股溢价率、双低策略、强赎/下修、六维分析、周度引擎）时使用' },
  { dir: 'etf-analysis', name: 'etf-analysis', category: '品种专项',
    whenToUse: '用户要分析或筛选 ETF（13 维分析、费率/规模/流动性筛选器）时使用' },
  { dir: 'futures-analysis', name: 'futures-analysis', category: '品种专项',
    whenToUse: '用户要分析股指期货（IF/IH/IC/IM 行情、基差、持仓、成交结构）时使用' },
  { dir: 'option-futures-linkage', name: 'option-futures-linkage', category: '品种专项',
    whenToUse: '用户要股指期货与期权联动分析（五个维度联动信号）时使用' },
  { dir: 'options-payoff', name: 'options-payoff', category: '品种专项',
    whenToUse: '用户要期权定价（BS 模型/Greeks）、多腿组合到期盈亏结构计算时使用；纯本地计算无需外部数据' },
  { dir: 'options-volatility', name: 'options-volatility', category: '品种专项',
    whenToUse: '用户要波动率曲面、隐含/历史波动率比较、波动率交易信号分析时使用；纯本地计算' },
  { dir: 'market-linkage-engine', name: 'market-linkage-engine', category: '市场全景',
    whenToUse: '用户要市场全景体检（股/债/汇/商品/流动性等 8 维联动评分，日度/周度）时使用' },
  { dir: 'industry-analysis', name: 'industry-analysis', category: '市场全景',
    whenToUse: '用户要行业层面研究（行业画像、估值排名、产业链图谱、景气度、投研观点）时使用' },
  { dir: 'tushare-data', name: 'tushare-data', category: '数据查询',
    whenToUse: '需要从 Tushare Pro 取结构化数据（行情/基本面/估值/资金流/宏观五类）且已知接口名时使用；官方数据适配层，唯一直连 Tushare 的位置' },
  { dir: 'zhishu-query', name: 'zhishu-query', category: '数据查询',
    whenToUse: '用户要查指数数据（行情、成分股、指数估值）时使用（问财通道）' },
  { dir: 'announcement-search', name: 'announcement-search', category: '数据查询',
    whenToUse: '用户要查上市公司公告（原文检索、公告类型筛选）时使用（问财通道）' },
  { dir: 'news-search', name: 'news-search', category: '数据查询',
    whenToUse: '用户要查财经新闻、个股舆情、市场资讯时使用（问财通道）' },
  { dir: 'report-search', name: 'report-search', category: '数据查询',
    whenToUse: '用户要查券商研报（观点、评级、盈利预测汇总）时使用（问财通道）' },
  { dir: 'business-query', name: 'business-query', category: '数据查询',
    whenToUse: '用户要查公司经营数据（主营构成、客户/供应商、参控股公司、重大合同）时使用（问财通道）' },
  { dir: 'macro-query', name: 'macro-query', category: '数据查询',
    whenToUse: '用户要查宏观数据（GDP/CPI/PMI/社融/利率/汇率等）时使用（问财通道）' },
  { dir: 'event-query', name: 'event-query', category: '数据查询',
    whenToUse: '用户要查市场或公司事件（增减持、质押、回购、并购重组、解禁等）时使用（问财通道）' },
  { dir: 'hithink-futures', name: 'hithink-futures', category: '数据查询',
    whenToUse: '用户要查商品期货/期权合约行情、基差、仓单等基础数据时使用（问财通道）' },
  { dir: 'chart-visualization', name: 'chart-visualization', category: '呈现',
    whenToUse: '需要把数据画成专业图表（26 种：雷达/折线/柱状/饼图/K线/热力等，Node.js 生成 ECharts 单文件 HTML）时使用',
    note: '本技能脚本为 Node.js（scripts/generate.js），需要 Node ≥18 与 npm 安装 echarts，无数据密钥。' },
  { dir: 'common', name: 'common', category: '基础设施',
    whenToUse: 'kk_common 公共数据网关库（finance_data_gateway/tushare_client/iwencai_client/缓存/格式化），是其他分析技能脚本运行的前置依赖，一般不单独触发；排查数据网关、Tushare/问财客户端问题时使用' },
]

const EXCLUDED_SKILLS = new Set(['sandbox-path-guide']) // QiLin 沙箱专属，dsh 无此语义
const EXCLUDED_ENTRIES = new Set(['__pycache__', 'node_modules', 'build'])
const EXCLUDED_SUFFIXES = ['.pyc', '.DS_Store']
const EXCLUDED_PATTERNS = [/\.egg-info$/]

if (!existsSync(SRC_PUBLIC)) {
  console.error(`找不到 KStock 技能源目录：${SRC_PUBLIC}（可用 KSTOCK_REPO 环境变量指定仓库路径）`)
  process.exit(1)
}

/* ═══════════════ frontmatter 解析与重建 ═══════════════ */

/** 从 frontmatter 文本提取顶层标量字段（容忍引号；嵌套块跳过）。 */
function parseFrontmatterScalars(fmText) {
  const out = {}
  let current = null
  for (const line of fmText.split('\n')) {
    const top = line.match(/^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$/)
    if (top) {
      current = top[1]
      const value = top[2].trim()
      if (value !== '' && value !== '|' && value !== '>' && value !== '-') {
        out[current] = value.replace(/^["']|["']$/g, '')
      } else if (value === '') {
        delete out[current] // 嵌套块或空值：标量视角视为不存在
      }
      continue
    }
    if (current === 'description' && /^\s{2,}\S/.test(line)) {
      out.description = (out.description ?? '') + ' ' + line.trim() // 折叠续行
    }
  }
  return out
}

/** 重建最小 frontmatter（dsh 不解析它，但保持可读与 smoke 可对账）。 */
function rebuildFrontmatter(scalars, dir) {
  const lines = ['---', `name: ${scalars.name ?? dir}`]
  if (scalars.description) lines.push(`description: ${scalars.description}`)
  if (scalars.version) lines.push(`version: ${scalars.version}`)
  if (scalars.license) lines.push(`license: ${scalars.license}`)
  if (scalars.author) lines.push(`author: ${scalars.author}`)
  lines.push('source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）')
  lines.push('---', '')
  return lines.join('\n')
}

/** 从 frontmatter 抓 required-secrets 声明的环境变量名（逐行扫描块内容）。 */
function parseRequiredSecrets(fmText) {
  const lines = fmText.split('\n')
  const out = []
  let inBlock = false
  for (const line of lines) {
    if (/^required-secrets:/.test(line)) {
      inBlock = true
      continue
    }
    if (!inBlock) continue
    if (/^[-\s]/.test(line)) {
      for (const m of line.matchAll(/\b([A-Z][A-Z0-9_]{2,})\b/g)) {
        const name = m[1]
        if ((name.includes('TOKEN') || name.includes('KEY') || name.includes('SECRET')) && !out.includes(name)) {
          out.push(name)
        }
      }
      continue
    }
    break // 顶层下一个键：块结束
  }
  return out
}

/* ═══════════════ 正文适配规则 ═══════════════ */

/** 通用路径/措辞替换。selfDir = 当前技能源目录名；aliases 处理改名技能。
 * 自引用绝对路径统一改为 <本技能包根> 占位符（相对形式 `cd .` 会让
 * python3 -m 在工作目录下找不到模块，必须换到真实包根再执行）。 */
function bodyRules(selfDir, aliases) {
  const rules = []
  // common 公共库：所有技能的同级邻居
  rules.push([/\/mnt\/skills\/public\/common(?![\w-])/g, '../common'])
  // 自身目录：占位符（激活提示给出绝对路径，执行前替换）
  rules.push([new RegExp(`/mnt/skills/public/${selfDir}/`, 'g'), '<本技能包根>/'])
  rules.push([new RegExp(`/mnt/skills/public/${selfDir}(?![\\w-])`, 'g'), '<本技能包根>'])
  // 其他目录（含改名别名）：../<目标名>
  for (const [from, to] of Object.entries(aliases)) {
    rules.push([new RegExp(`/mnt/skills/public/${from}(?![\\w-])`, 'g'), `../${to}`])
  }
  // 兜底：残留的其他技能路径
  rules.push([/\/mnt\/skills\/public\/([\w-]+)\//g, '../$1/'])
  rules.push([/\/mnt\/skills\/public\/([\w-]+)(?![\w-])/g, '../$1'])
  // 工作区与缓存
  rules.push([/\/mnt\/user-data\/workspace/g, '.'])
  rules.push([/\/mnt\/user-data/g, '.'])
  rules.push([/\/mnt\/cache\/market-data/g, '<数据根>/cache/market-data'])
  // 密钥注入措辞：QiLin 沙箱激活注入 → 凭据文件 source
  rules.push([/`TUSHARE_TOKEN` 由系统注入沙箱环境，脚本直接读取/g,
    '`TUSHARE_TOKEN` 从凭据文件注入运行环境（运行前 source 凭据文件，见「凭据配置」），脚本直接读取'])
  rules.push([/lead_soul\.md 场景第/g, '产品场景手册场景第'])
  return rules
}

/** industry-analysis 阶段四：render_html_report/present_files → 直接落盘单文件 HTML。
 * 逐行精准替换（块级整段匹配对空行/措辞漂移脆弱）。 */
const INDUSTRY_LINE_REWRITES = [
  ['### 阶段四：报告生成（内置 render_html_report 工具）',
    '### 阶段四：报告生成（单文件 HTML 直接落盘）'],
  ['本技能**不自行编写报告或绘图代码**，而是调用内置 `render_html_report` 工具统一渲染。流程：',
    'dsh 宿主没有 render_html_report 看板工具，本技能在 dsh 下改为**直接编写并交付单文件 HTML 报告**（写入当前工作目录，双击浏览器可离线打开）。流程：'],
  ['2. 为每个图表按 `charts[].{tool, title, alt, args}` 结构构造，图表以内嵌 SVG 渲染，**禁止使用远程图片 URL**。至少 3 个图表。args 的完整字段规范以工具描述中的契约说明为准。',
    '2. 图表用内嵌 SVG 或 CSS 绘制（可复用 chart-visualization 技能生成 ECharts 图表后以内嵌方式合入），**禁止使用远程图片 URL**。至少 3 个图表。'],
  ['3. 调用 `render_html_report(report_json, filename="report.html")`；若完整 JSON 已保存为 `./*.json`，改用 `render_html_report_from_file(report_json_path="./report.json", filename="report.html")`，禁止先把大 JSON 读入上下文；渲染成功后用 `present_files` 交付。',
    '3. 用文件写入工具把完整报告落盘为 `行业分析报告-<行业名>-<日期>.html`，并向用户给出文件绝对路径；**不要**把整份 HTML 贴进对话，也不要把大 JSON 读入上下文。'],
]

function transformBody(body, item, aliases) {
  let out = body
  for (const [pattern, replacement] of bodyRules(item.dir, aliases)) out = out.replace(pattern, replacement)
  if (item.dir === 'industry-analysis') {
    for (const [from, to] of INDUSTRY_LINE_REWRITES) out = out.replace(from, to)
  }
  return out
}

/** 正文头部适配说明 + 尾部凭据配置。 */
function adaptNotes(item, secrets) {
  const head = [
    `> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。`,
    `> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 \`scripts/\`、\`references/\`、\`../common\` 等相对路径以该目录为基准解析；\`<本技能包根>\` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。`,
    `> - 产物（报告 HTML、图表、JSON、Excel）一律写入**当前工作目录**（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。`,
    `> - 数据缺失时如实标注「缺失」，**禁止编造数据**。`,
  ]
  if (item.note) head.push(`> - ${item.note}`)
  head.push('')

  let tail = ''
  if (secrets.length > 0) {
    const rows = secrets.map((s) => {
      const desc = s === 'TUSHARE_TOKEN' ? 'Tushare Pro 数据接口（行情/财务/宏观主源）' : '同花顺问财 OpenAPI（自然语言数据查询）'
      const where = s === 'TUSHARE_TOKEN' ? 'tushare.pro 个人主页' : '问财开放平台控制台'
      return `| \`${s}\` | ${desc} | ${where} |`
    }).join('\n')
    tail = [
      '## 凭据配置（dsh 适配）',
      '',
      '本技能脚本运行需要以下密钥（缺失时脚本会明确报错，不会编造数据）：',
      '',
      '| 环境变量 | 用途 | 获取渠道 |',
      '|---|---|---|',
      rows,
      '',
      'dsh 宿主会把名字含 TOKEN/KEY/SECRET/PASSWORD 的进程环境变量从 bash 子进程中剥离，',
      '因此统一走**凭据文件**约定。插件数据根（下称「数据根」）= 宿主 home 下的',
      '`dsh-skills-stock/`，宿主 home 按 `$QILIN_HOME → $DSH_HOME → ~/.dsh` 解析',
      '（未设环境变量时即 `~/.dsh/dsh-skills-stock`；工作台设置页「数据源」会显示绝对路径）：',
      '',
      '1. 把密钥写入 `<数据根>/secrets.env`（权限 0600）：',
      '   ```bash',
      ...secrets.map((s) => `   ${s}=你的密钥`),
      '   ```',
      '2. 运行技能脚本时，在同一条 bash 命令里先加载再执行（bash 内 export 的变量可以传给子进程）：',
      '   ```bash',
      '   set -a; source <数据根>/secrets.env; set +a',
      '   cd scripts && python3 <脚本名> <参数>',
      '   ```',
      '',
      'Python 依赖（pandas/numpy/scipy/tushare/akshare 等）按脚本报错提示 `pip install` 即可；',
      '`../common` 公共库由脚本自动 `pip install -e` 安装（候选路径已按 dsh 插件布局解析）。',
      '',
    ].join('\n')
  }
  return { head: head.join('\n'), tail }
}

/* ═══════════════ 脚本级修补 ═══════════════ */

const CLI_CANDIDATES_OLD = `COMMON_CANDIDATE_PATHS = [
    "/mnt/skills/public/common",
    "/Users/libing/kk_Projects/KStock/vendor/skills/public/common",
]`

/** dsh 布局：<skills>/common 与 <skills>/<本技能>/scripts/ 本脚本同级解析。 */
function cliCandidatesNew() {
  return [
    'import os as _os',
    '',
    'COMMON_CANDIDATE_PATHS = [',
    '    _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "common"),',
    '    "/mnt/skills/public/common",',
    ']',
  ].join('\n')
}

const SCRIPT_PATCHES = [
  {
    file: ['valuation-model', 'scripts', 'pe_band_cli.py'],
    apply(text) {
      return text.replace(CLI_CANDIDATES_OLD, cliCandidatesNew())
    },
  },
  {
    file: ['financial-statement', 'scripts', 'financial_cli.py'],
    apply(text) {
      return text.replace(CLI_CANDIDATES_OLD, cliCandidatesNew())
    },
  },
  {
    // strategy-research 两个 analysis 模块的 docstring 用法示例：
    // QiLin 沙箱绝对路径 → 技能包根占位说明（正文已给出基目录解析规则）
    file: ['strategy-research', 'scripts', 'analysis', 'param_sweep.py'],
    apply(text) {
      return text.replace(
        '/mnt/skills/public/strategy-research/scripts/analysis',
        '<strategy-research-技能根>/scripts/analysis',
      )
    },
  },
  {
    file: ['strategy-research', 'scripts', 'analysis', 'walk_forward.py'],
    apply(text) {
      return text.replace(
        '/mnt/skills/public/strategy-research/scripts/analysis',
        '<strategy-research-技能根>/scripts/analysis',
      )
    },
  },
  {
    // common 缓存目录：~/.kstock 写死 → 宿主 home 口径（数据根 dsh-skills-stock/，
    // 与 host 侧 stockHome() 同一解析）。默认从「父目录存在才启用」改为始终
    // 解析——写路径已有 makedirs(exist_ok=True)，dsh 上缓存从旁路变为可用。
    file: ['common', 'src', 'kk_common', 'market_data_cache.py'],
    apply(text) {
      let out = text
      const doc2Old = [
        '  2. /mnt/cache/market-data（沙箱挂载视图，LocalSandbox 把它映射回',
        '     ~/.kstock/cache/market-data，与 gateway 进程视图同一物理目录）；',
      ].join('\n')
      if (!out.includes(doc2Old)) throw new Error('market_data_cache.py docstring 第 2 条未命中')
      out = out.replace(doc2Old, '  2. /mnt/cache/market-data（QiLin 沙箱挂载视图；dsh 宿主上不存在，自动跳过）；')
      const doc3Old = '  3. ~/.kstock/cache/market-data（gateway / 开发态直跑视图）。'
      if (!out.includes(doc3Old)) throw new Error('market_data_cache.py docstring 第 3 条未命中')
      out = out.replace(doc3Old, [
        '  3. <宿主 home>/dsh-skills-stock/cache/market-data（dsh 数据根；宿主 home',
        '     按 $QILIN_HOME → $DSH_HOME → ~/.dsh 解析，与插件凭据/三库同根）。',
      ].join('\n'))
      const homeOld = [
        '    home = os.path.expanduser("~")',
        '    if home and home != "~":',
        '        default = os.path.join(home, ".kstock", "cache", "market-data")',
        '        if os.path.isdir(os.path.dirname(default)):',
        '            return default',
        '    return None',
      ].join('\n')
      if (!out.includes(homeOld)) throw new Error('market_data_cache.py 默认目录块未命中')
      out = out.replace(homeOld, [
        '    # dsh-skills-stock 数据根：跟随宿主 home（$QILIN_HOME → $DSH_HOME →',
        '    # ~/.dsh），缓存落在 <数据根>/cache/market-data，首次写入自动建目录。',
        '    root = os.getenv("QILIN_HOME", "").strip() or os.getenv("DSH_HOME", "").strip() \\',
        '        or os.path.join(os.path.expanduser("~"), ".dsh")',
        '    return os.path.join(root, "dsh-skills-stock", "cache", "market-data")',
      ].join('\n'))
      return out
    },
  },
]

/* ═══════════════ 主流程 ═══════════════ */

function copyDirFiltered(src, dest) {
  mkdirSync(dest, { recursive: true })
  for (const name of readdirSync(src)) {
    if (EXCLUDED_ENTRIES.has(name) || EXCLUDED_SUFFIXES.some((s) => name.endsWith(s))) continue
    if (EXCLUDED_PATTERNS.some((p) => p.test(name))) continue
    const full = join(src, name)
    if (statSync(full).isDirectory()) copyDirFiltered(full, join(dest, name))
    else cpSync(full, join(dest, name))
  }
}

rmSync(OUT_SKILLS, { recursive: true, force: true })
mkdirSync(OUT_SKILLS, { recursive: true })

// 改名别名表：交叉引用按「源目录名 → 目标注册名」重写
const aliases = Object.fromEntries(SPEC.filter((s) => s.dir !== s.name).map((s) => [s.dir, s.name]))

const manifest = { skills: [] }
const audit = []

for (const item of SPEC) {
  const srcDir = join(SRC_PUBLIC, item.dir)
  if (!existsSync(srcDir)) {
    console.error(`✗ 源技能缺失：${item.dir}（${srcDir}）`)
    process.exit(1)
  }
  if (EXCLUDED_SKILLS.has(item.dir)) continue

  const destDir = join(OUT_SKILLS, item.name)
  copyDirFiltered(srcDir, destDir)

  // 脚本级修补（路径硬编码等；未命中的补丁在收尾时报错）
  const patched = []
  for (const patch of SCRIPT_PATCHES) {
    if (patch.file[0] !== item.dir) continue
    const patchPath = join(destDir, ...patch.file.slice(1))
    const before = readFileSync(patchPath, 'utf8')
    const after = patch.apply(before)
    if (after === before) {
      console.error(`✗ 脚本补丁未命中：${patch.file.join('/')}`)
      process.exit(1)
    }
    writeFileSync(patchPath, after)
    patched.push(patch.file.join('/'))
  }

  const skillMdPath = join(destDir, 'SKILL.md')
  const raw = readFileSync(skillMdPath, 'utf8')
  const fmMatch = raw.match(/^---\n([\s\S]*?)\n---\n?/)
  if (!fmMatch) {
    console.error(`✗ ${item.dir}/SKILL.md 无 frontmatter`)
    process.exit(1)
  }
  const scalars = parseFrontmatterScalars(fmMatch[1])
  const secrets = parseRequiredSecrets(fmMatch[1])
  const body = raw.slice(fmMatch[0].length).replace(/^\n+/, '')
  const { head, tail } = adaptNotes(item, secrets)
  // frontmatter name 以 dsh 注册名为准（改名技能如 backtrader_strategies）
  const adapted = rebuildFrontmatter({ ...scalars, name: item.name }, item.name)
    + '\n' + head + '\n' + transformBody(body, item, aliases).trimEnd() + '\n\n' + tail
  writeFileSync(skillMdPath, adapted)

  manifest.skills.push({
    dir: item.name,
    name: item.name,
    description: scalars.description ?? '',
    whenToUse: item.whenToUse,
    category: item.category,
    requiredSecrets: secrets,
  })
  audit.push(`${item.dir} → ${item.name}（secrets: ${secrets.length ? secrets.join('+') : '无'}${patched.length ? '；脚本补丁: ' + patched.length : ''}）`)
}

writeFileSync(join(OUT_SKILLS, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n')

/* 自检：适配产物不得残留 QiLin 宿主语义（发现即失败，防止规则漏网）。 */
const RESIDUAL_PATTERNS = [
  [/\/mnt\/(skills|user-data|cache)/, '残留 /mnt 沙箱路径'],
  [/render_html_report\(|render_html_report_from_file|present_files|`render_html_report` 工具/, '残留 QiLin 内置工具引用'],
  [/由系统注入沙箱环境/, '残留沙箱密钥注入措辞'],
  [/wait_for_background_task/, '残留 QiLin 后台任务工具引用'],
]
let residuals = 0
for (const item of manifest.skills) {
  const text = readFileSync(join(OUT_SKILLS, item.dir, 'SKILL.md'), 'utf8')
  for (const [pattern, label] of RESIDUAL_PATTERNS) {
    if (pattern.test(text)) {
      console.error(`✗ ${item.dir}: ${label}`)
      residuals += 1
    }
  }
}
if (residuals > 0) process.exit(1)

console.log(`适配完成：${manifest.skills.length} 个技能 → skills/`)
for (const line of audit) console.log('  · ' + line)
