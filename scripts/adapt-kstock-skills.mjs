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
  { dir: 'stock-due-diligence', name: 'stock-due-diligence', category: '场景编排',
    whenToUse: '用户问「XX 股票怎么样 / 个股深度分析 / 尽调 / 全维度研报」等单股深度问题时使用；并行编排 stock-analysis 引擎群 + financial-statement 三表 + valuation-model PE-Band，产出单文件 HTML 尽调看板' },
  { dir: 'stock-screening-theme', name: 'stock-screening-theme', category: '场景编排',
    whenToUse: '用户问「帮我选股 / 筛选 XX 特征的股票 / 高股息低估蓝筹 / 找标的」等选股流水线类问题时使用；编排 a-stock-screener 筛选 → 批量个股快评 → html-report 汇总看板' },
  { dir: 'strategy-backtest-theme', name: 'strategy-backtest-theme', category: '场景编排',
    whenToUse: '用户问「写个策略回测 / 双均线策略表现 / 参数扫描 / 走前验证」等策略研究类问题时使用；编排 strategy-research 引擎 + 自建 driver 拉真实数据 + html-report 回测看板' },
  { dir: 'factor-analysis-theme', name: 'factor-analysis-theme', category: '场景编排',
    whenToUse: '用户要走完整因子研究流程（单因子检验 IC/IR/分层 → 多因子合成 → 六因子选股）并要 HTML 看板交付时使用；编排 factor-research 引擎群' },
  { dir: 'chan-stock-theme', name: 'chan-stock-theme', category: '场景编排',
    whenToUse: '用户问「缠论分析 / 笔段中枢 / 背驰 / 三类买卖点 / MACD 背驰选股」等缠论类问题时使用；编排 stock-analysis 缠论双引擎 + chart-visualization + html-report 缠论看板' },
  { dir: 'cb-panorama', name: 'cb-panorama', category: '场景编排',
    whenToUse: '用户问「可转债全景 / 转债市场温度 / 转债估值 / 双低策略池 / 转债周报」等可转债市场类问题时使用；编排 cb-analysis 周度综合引擎 + 问财看板 + html-report 全景看板' },
  { dir: 'market-linkage', name: 'market-linkage', category: '场景编排',
    whenToUse: '用户问「市场联动 / 大盘联动 / 资金面情绪面全景 / 今天市场怎么样」等市场全景类问题时使用；编排 market-linkage-engine 8 维引擎 + 分维度并行解读 + html-report 联动看板（引擎本体是 market-linkage-engine）' },
  { dir: 'index-futures-theme', name: 'index-futures-theme', category: '场景编排',
    whenToUse: '用户问「期指分析 / 股指期货 / IF IC IH IM / 基差 / 贴水升水 / 期指多空持仓」等股指期货类问题时使用；编排 futures-analysis 四维引擎 + html-report 期指专题看板' },
  { dir: 'option-etf-theme', name: 'option-etf-theme', category: '场景编排',
    whenToUse: '用户问「期权 ETF 分析 / 7 大期权 ETF / ETF 份额与期权波动率 / 50ETF 300ETF 创业板 科创50」等期权 ETF 类问题时使用；并行编排 etf-analysis + option-futures-linkage + market-linkage-engine + html-report 专题看板' },
  { dir: 'option-futures-linkage-theme', name: 'option-futures-linkage-theme', category: '场景编排',
    whenToUse: '用户问「期指期权联动 / 期权 PCR 与期指方向 / 期权持仓变化与期货持仓印证」等期权×期货交叉验证类问题时使用；编排 option-futures-linkage 联动引擎 + futures-analysis / options-volatility 两翼 + html-report 联动看板' },
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
  { dir: 'html-report', name: 'html-report', category: '呈现',
    whenToUse: '需要把完成的研究交付为可视化 HTML 看板并归档报告库时使用（结构化报告 JSON → 纯标准库渲染器 → 单文件自包含 HTML，report_archive 工具归档）；个股/行业/因子/策略/选股等场景报告交付的统一出口',
    note: '本技能渲染器为纯标准库 Python（scripts/render_report.py），无外部依赖；归档一步在 dsh 下改用 report_archive 工具（KStock 桌面端本地 API 的 curl 模板已替换）。' },
  { dir: 'chart-visualization', name: 'chart-visualization', category: '呈现',
    whenToUse: '需要把数据画成专业图表（26 种：雷达/折线/柱状/饼图/K线/热力等，Node.js 生成 ECharts 单文件 HTML）时使用',
    note: '本技能脚本为 Node.js（scripts/generate.js），需要 Node ≥18 与 npm 安装 echarts，无数据密钥。' },
  { dir: 'common', name: 'common', category: '基础设施',
    whenToUse: 'kk_common 公共数据网关库（finance_data_gateway/tushare_client/iwencai_client/缓存/格式化），是其他分析技能脚本运行的前置依赖，一般不单独触发；排查数据网关、Tushare/问财客户端问题时使用' },
]

// QiLin 宿主专属语义，dsh 无对应物：
// - sandbox-path-guide：沙箱路径规范技能（dsh 相对路径以 resourceBase 解析）
// - market-scan-workflow：依赖 QiLin 原生 workflow 编排工具（agent/pipeline/
//   parallel 钩子 + JS 脚本），dsh 无此编排原语；待 dsh 提供后再评估适配
const EXCLUDED_SKILLS = new Set(['sandbox-path-guide', 'market-scan-workflow'])
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
  // ── KStock 2.0 宿主语义（桌面端本地 API / 内置 present 工具 / 沙箱规范技能）──
  // 报告库归档：curl 模板措辞 → report_archive 工具
  rules.push([/用 html-report 技能 SKILL\.md 中的 curl 模板/g, '用 report_archive 工具（契约见 html-report 技能）'])
  rules.push([/html-report SKILL\.md 的 curl 模板/g, 'html-report 技能的 report_archive 工具'])
  rules.push([/把 reports\/ 下的两份产物归档进报告库（POST \/kstock-api\/reports）/g,
    '把 reports/ 下渲染出的 HTML 看板归档进报告库（report.json 是渲染输入，不必归档）'])
  // html-report 基目录占位符 → dsh 技能包根口径
  rules.push([/<html-report 基目录>/g, '<html-report 技能包根>'])
  rules.push([/基目录 = html-report 技能加载结果给出的 Base directory/g, '技能包根 = 激活提示 skill_resources 给出的资源基目录'])
  // QiLin 内置 present 工具 → 文件绝对路径交付
  rules.push([/归档后用 `present` 呈现/g, '归档后向用户给出文件绝对路径交付'])
  rules.push([/`present` 呈现/g, '向用户给出文件绝对路径交付'])
  rules.push([/，present 呈现/g, '，向用户给出文件绝对路径交付'])
  // KStock 报告库 API 回执字段 → report_archive 工具回执口径
  rules.push([/归档成功返回 `report_id` 与 `content_url`。/g, '归档成功返回 `report_id` 与落盘绝对路径（content_path）。'])
  // KStock 桌面工作台 → dsh 投研工作台
  rules.push([/量化工作台 → 报告库/g, '投研工作台 → 报告库'])
  rules.push([/「量化工作台/g, '「投研工作台'])
  // 沙箱规范技能引用 → 顶部适配说明（内联产物分区纪律）；容忍跨行断行
  rules.push([/见[ \t]*(\n[ \t]*)?sandbox-path-guide/g, '见顶部「dsh 适配说明」'])
  // 场景手册归档行的 URL 尾注（curl 模板本体在 html-report，dsh 走工具）
  rules.push([/\n?\s*`POST \/kstock-api\/reports`（模板读取的是 `reports\/` 下的两份产物）；/g, ''])
  // KStock 密钥路径 → dsh 数据根凭据文件
  rules.push([/~\/kstock\/config\/secrets\.env/g, '<数据根>/secrets.env'])
  // 桌面端本地 API 三步入库的引子句（围栏块本体由 rewriteArchiveBlocks 整块替换）
  rules.push([/引擎本机\s*`http:\/\/127\.0\.0\.1:18001`，\s*\n\s*三步（均 curl POST，失败不阻塞交付）：/g,
    'dsh 下走本插件注册的同名四库 agent 工具（投研工作台对应库面板随时回看），三步（工具调用，失败不阻塞交付）：'])
  rules.push([/引擎本机\s*\n?\s*`http:\/\/127\.0\.0\.1:18001`，\s*三步（均 curl POST，失败不阻塞交付）：/g,
    'dsh 下走本插件注册的同名四库 agent 工具（投研工作台对应库面板随时回看），三步（工具调用，失败不阻塞交付）：'])
  // PATCH 更新语义（dsh 无 PATCH）：既有 id 迭代
  rules.push([/不要 POST 新(策略|因子|方案)——`PATCH \/kstock-api\/\w+\/\{id\}`\s*\n\s*更新 (?:hypothesis|criteria 摘要)；/g,
    '不要 *_create 新$1——用 *_list 定位既有 id 后迭代；'])
  rules.push([/ ?POST 新版本/g, '*_save_version 落新版本'])
  return rules
}

/* KStock 桌面端本地 API（127.0.0.1:18001）的 curl 入库围栏块 → dsh 四库工具等价步骤。
 * 含 kstock-api/<lib> 的 ```bash 块整块替换为对应库的工具调用清单。 */
const ARCHIVE_TOOL_BLOCKS = {
  strategies: `1. \`strategy_create\`（{name, hypothesis}）建策略资产，返回 \`strategy_id\`；
2. \`strategy_save_version\`（{strategy_id, code, params, change_note, parent_version}）存代码版本：code=策略信号/回测核心代码全文（≤512KB）；parent_version 传 \`strategy_get_latest\` 读到的当前版本（乐观锁）；
3. \`strategy_record_backtest\`（{strategy_id, version, data_start, data_end, rules, metrics, equity?, trades?}）存回测结果：rules 原样抄录 A 股交易规则（可带 \`report_id\` 建看板链）；metrics 面板渲染键 total_return_pct / annual_return_pct / sharpe_ratio / max_drawdown_pct / win_rate_pct / trade_count；equity=净值序列（≤2MB），trades=交易清单（≤4MB）。`,
  factors: `1. \`factor_create\`（{name, hypothesis, category}）建因子资产，返回 \`factor_id\`；
2. \`factor_save_version\`（{factor_id, code, params, change_note, parent_version}）存因子代码版本（code 全文入库，禁止只留在会话工作区）；
3. \`factor_record_run\`（{factor_id, version, universe, data_start, data_end, config, metrics, ic_series?, layers?}）存检验结果：config 原样抄录检验配置；metrics 含 ic_mean / ir 等核心键；ic_series=逐期 IC（≤2MB），layers=分层回测（≤4MB）。`,
  selections: `1. \`selection_create\`（{name, criteria}）建选股方案（一句话口径），返回 \`selection_id\`；
2. \`selection_save_version\`（{selection_id, criteria_json, change_note, parent_version}）存口径版本：criteria_json.summary 必填；
3. \`selection_record_run\`（{selection_id, version, trade_date, universe, rules, metrics, report?, picks?}）存执行结果：picks=[{code,name,score,strategies,rank}]（code 带交易所后缀），report=报告全文。`,
  reports: `调用 \`report_archive\` 工具归档（投研工作台「报告库」随时查看）：{title, content, symbol?, report_type?, generated_at?, period_start?, period_end?, risk_level?, coverage_status?}，content 传 \`reports/<主题名>.html\` 全文（≤8MB）。`,
}

function rewriteArchiveBlocks(body) {
  return body.replace(/```bash\n([\s\S]*?)```/g, (block, inner) => {
    for (const lib of ['strategies', 'factors', 'selections', 'reports']) {
      if (inner.includes(`kstock-api/${lib}`)) return ARCHIVE_TOOL_BLOCKS[lib]
    }
    return block
  })
}

function transformBody(body, item, aliases) {
  let out = body
  for (const [pattern, replacement] of bodyRules(item.dir, aliases)) out = out.replace(pattern, replacement)
  out = rewriteArchiveBlocks(out)
  return out
}

/** 正文头部适配说明 + 尾部凭据配置。 */
function adaptNotes(item, secrets) {
  const head = [
    `> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。`,
    `> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 \`scripts/\`、\`references/\`、\`../common\` 等相对路径以该目录为基准解析；\`<本技能包根>\` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。`,
    `> - 产物写入**当前工作目录**，并按 scripts/（脚本）/ data/（引擎中间产物）/ reports/（报告 JSON 与 HTML）三目录归位（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。`,
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
    // common 缓存目录（KStock 2.0 重写后的锚点）：持久候选从 ~/.kstock 写死
    // 改为宿主 home 口径（<数据根>/cache/market-data，与 host 侧 stockHome()
    // 同一解析）。上游新逻辑自带「探测失败落系统临时区、绝不因缓存失败」
    // 语义，dsh 侧只替换持久目录候选；docstring 第 3 条（临时区保底）不动。
    file: ['common', 'src', 'kk_common', 'market_data_cache.py'],
    apply(text) {
      let out = text
      const doc2Old = [
        '  2. ~/.kstock/cache/market-data（宿主直跑视图：非沙箱进程可写时启用，',
        '     持久复用）；',
      ].join('\n')
      if (!out.includes(doc2Old)) throw new Error('market_data_cache.py docstring 第 2 条未命中')
      out = out.replace(doc2Old, [
        '  2. <宿主 home>/dsh-skills-stock/cache/market-data（dsh 数据根，与凭据/',
        '     三库同根；宿主 home 按 $QILIN_HOME → $DSH_HOME → ~/.dsh 解析）；',
      ].join('\n'))
      const homeOld = [
        '        home = os.path.expanduser("~")',
        '        _resolved_dir = None',
        '        if home and home != "~":',
        '            _resolved_dir = _probe_writable_dir(',
        '                os.path.join(home, ".kstock", "cache", "market-data")',
        '            )',
      ].join('\n')
      if (!out.includes(homeOld)) throw new Error('market_data_cache.py 默认目录块未命中')
      out = out.replace(homeOld, [
        '        # dsh-skills-stock 数据根：跟随宿主 home（$QILIN_HOME → $DSH_HOME →',
        '        # ~/.dsh），缓存落 <数据根>/cache/market-data；探测失败仍落临时区。',
        '        root = os.getenv("QILIN_HOME", "").strip() or os.getenv("DSH_HOME", "").strip() \\',
        '            or os.path.join(os.path.expanduser("~"), ".dsh")',
        '        _resolved_dir = _probe_writable_dir(',
        '            os.path.join(root, "dsh-skills-stock", "cache", "market-data")',
        '        )',
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
  [/render_html_report\(|render_html_report_from_file|present_files/, '残留 QiLin 内置工具引用'],
  [/由系统注入沙箱环境/, '残留沙箱密钥注入措辞'],
  [/wait_for_background_task/, '残留 QiLin 后台任务工具引用'],
  [/kstock-api|127\.0\.0\.1:18001/, '残留 KStock 桌面端本地 API 引用'],
  [/`present`|present 呈现/, '残留 QiLin present 工具引用'],
  [/sandbox-path-guide/, '残留 sandbox-path-guide 技能引用'],
  [/~\/kstock/, '残留 ~/.kstock 宿主路径'],
  [/均 curl POST/, '残留 curl 入库措辞'],
  [/PATCH \/kstock-api/, '残留 PATCH 入库措辞'],
  [/◆TODO◆|workflow 工具的 meta 参数/, '残留 QiLin workflow 模板语义'],
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
