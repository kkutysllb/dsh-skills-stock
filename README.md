# dsh-skills-stock

DSH 原生 **A 股量化投研技能包**：把本地桌面产品 [KStock](../KStock) 的核心产品
能力适配为 dsh（deepseek-harness）插件 —— 30 个 runtime skill（个股研究 /
选股与策略 / 可转债·ETF·期货·期权专项 / 市场全景 / 数据查询 / 图表呈现）、
**策略库 / 因子库 / 选股库**三库工作区（15 个 agent 工具 + 侧边栏工作台 UI）、
设置页**数据源**凭据配置。

形态对齐家族插件（dsh-super-ppts / dsh-kylin-automation）：**不用**插件自造
Agent 预设（DSH 0.1.16 起 agent-presets 按 agent.cordis.yml 组合挂载，插件
自造预设已失效），人设路由经 systemPrompt 能力通告承载；激活时幂等清理
历史版本写入的预设目录。

## 插件清单

| 类别 | 技能 |
|---|---|
| 个股研究（6） | stock-analysis（十四维分析引擎）、financial-statement（三表勾稽/造假红旗/杜邦）、earnings-forecast（盈利预测/SUE）、earnings-revision（盈利修正）、valuation-model（PE-Band/PB-ROE/估值陷阱）、dcf（DCF 建模 + Excel） |
| 选股与策略（5） | a-stock-screener（自然语言选股编排）、selection-strategies（十大策略）、factor-research（IC/IR/分层回测）、strategy-research（策略设计/参数扫描/walk-forward）、backtrader-strategies（8 策略适配器库） |
| 品种专项（6） | cb-analysis（可转债全链路）、etf-analysis（13 维）、futures-analysis（股指期货四维）、option-futures-linkage（期指期权联动）、options-payoff（BS 定价/Greeks/多腿盈亏）、options-volatility（波动率曲面） |
| 市场全景（2） | market-linkage-engine（8 维市场联动）、industry-analysis（行业六维画像/产业链） |
| 数据查询（9） | tushare-data（Tushare 官方适配层）+ 问财八件套：zhishu-query / announcement-search / news-search / report-search / business-query / macro-query / event-query / hithink-futures |
| 呈现与基建（2） | chart-visualization（26 种 ECharts 图表，Node.js）、common（kk_common 公共数据网关库，被其他技能自动引用） |

## 安装

```sh
# npm registry（推荐：版本可被插件管理检测，用户手动更新）
dsh plugin --profile web add dsh-skills-stock

# GitHub 直装 / install straight from GitHub
dsh plugin --profile web add github:kkutysllb/dsh-skills-stock

# 本地路径安装 / install from a local checkout
git clone git@github.com:kkutysllb/dsh-skills-stock.git
dsh plugin --profile web add ./dsh-skills-stock
```

安装后重启 dsh 生效：

- 30 个技能注册为 runtime skill（rank 250，项目级 `.dsh/skills` 同名技能可
  覆盖），所有 agent 会话可见，`/技能名` 可显式激活；
- 15 个三库工具（`strategy_*` / `factor_*` / `selection_*` 各 5 件套）注册为
  agent 原生工具，宿主全局可用（`registerTools: false` 可关闭）；
- workspace 侧边栏出现「**投研工作台**」独立面板（三库 tab）；
- 设置页出现「**数据源**」菜单项（凭据配置）；
- systemPrompt 注入一段有界能力通告（需求路由 + 三库纪律 + 跨技能约定，
  `announceToAgent: false` 可关闭）。

## QiLin（麒麟）双通道适配（v1.2.2 起）

manifest 同时声明 `qilin` 与 `dsh` 两个通道的 `bundle.patch` / `client`：
QiLin（dsh 0.1.6-alpha.2 合并后）的插件管理器只认原生键
`qilin.bundle.patch`（缺失会报「没有声明组合包」），DSH 宿主仍读
`dsh.*`；两通道指向同一份 `cordis.patch.yml` 与 client 交付物，
行为完全一致。

## 麒麟（QiLin）引擎安装

```bash
# npm registry（推荐：版本可被插件管理检测，用户手动更新）
qilin plugin --profile qilin add dsh-skills-stock

# GitHub 直装 / install straight from GitHub
qilin plugin --profile qilin add github:kkutysllb/dsh-skills-stock
```

装完在 QiLin 设置 → 插件里可见、可启停；三库（stock/library/secrets）
数据根按 `$QILIN_HOME → $DSH_HOME → ~/.dsh` 解析，与 QiLin/KStock
语义映射表（本仓已有）一致。

### 注意事项（QiLin）

- **必须经 `qilin plugin add` 装进 profile**：包会落到 profile 私有的
  `~/.qilin/profiles/<name>/node_modules`——裸包名原生解析的第一跳。
  **不要**手工把包目录放进共享的 `~/.qilin/profiles/node_modules`：
  dsh alpha.2 合并后的 runtime+enforce 解析把该目录划为安装保留区，
  放那里的 bundle 层包激活时直接 `failed to import`。
- **引擎版本**：运行需要带 dsh 兼容层的 QiLin 3.0.0+；插件**管理**
  （设置页展示/启停）要求 3.0.2+（alpha.2 合并后只认
  `qilin.bundle.patch` 原生键）。
- **运行时解析**：dsh alpha.2 起依赖解析默认运行时模式（PR #4471），
  插件运行期导入由 profile 安装图经进程内 generation 解析；引擎包按
  框架契约声明于 peerDependencies，由宿主安装副本统一解析。

## 投研工作台（侧边栏面板）

工作台是 dsh agent 能力的作业界面，沿用 KStock 产品闭环——**库内容由 agent
入库，面板只读 + 驱动**：

- **三个 tab：策略库 / 因子库 / 选股库**。列表显示名称、状态徽章、当前版本
  与最近运行核心指标（收益/夏普、IC/IR、命中数）；详情含身份卡（投资假设 /
  选股口径）、**版本时间线**（逐版本 change_note + 最新标记）、**运行归档表**
  （勾选 2-4 个做指标并排对比 + 曲线叠加：策略库叠加**净值曲线**——各运行
  归一到同起点 1，因子库叠加**累计 IC 曲线**——逐期累加，KStock 桌面端
  EquityOverlay/IcOverlay 同款几何与配色；曲线负载不随详情常驻传输，勾选后
  经 `library_runs` 端点按需拉取）。
- **新建研究任务 / 重跑本版本**：把预填好的任务 prompt 经会话桥
  （setDraft → submit，super-ppts v3 同款，剪贴板降级）投递到 dsh 会话，
  agent 读技能 → 跑回测/检验/选股 → 用工具登记入库 → 用户在面板看结果，
  再一键重跑迭代。
- 存储在数据根 `<宿主 home>/dsh-skills-stock/product/{strategies,factors,selections}/`（object.json
  身份 + versions/ 版本链 + runs/ 运行归档，纯 JSON、agent 的文件工具可直接
  读取），容量上限与乐观锁纪律同 KStock。
- **数据根跟随宿主 home**：`$QILIN_HOME → $DSH_HOME → ~/.dsh`（super-ppts
  同款解析，不写死用户 home 字面量；KCoder 桌面端 `DSH_HOME=~/.kcoder` 时
  数据即在 `~/.kcoder/dsh-skills-stock/`）。v1.0–1.1 的 `~/.dsh-stock` 旧数据
  在插件加载时自动迁移（整项搬移、绝不覆盖目标既有文件）。

## 三库 agent 工具（15 个，注册名与 KStock 对齐）

| 库 | 工具 |
|---|---|
| 策略库 | strategy_list / strategy_create / strategy_get_latest / strategy_save_version / strategy_record_backtest |
| 因子库 | factor_list / factor_create / factor_get_latest / factor_save_version / factor_record_run |
| 选股库 | selection_list / selection_create / selection_get_latest / selection_save_version / selection_record_run |

版本纪律（沿袭 KStock lead_soul）：代码/口径必须经 `*_save_version` 入库
（禁止只留在会话工作区），运行后必须 `*_record_*` 归档（rules/config 原样
抄录，跨版本对比口径才成立）；新版本劣于旧版本如实呈现并在 change_note
写「证伪」。选股库 `criteria_json.summary` 必填，create 自动落 v1。

## 设置页「数据源」

`TUSHARE_TOKEN` / `IWENCAI_API_KEY` 的配置状态徽章 + 受控保存表单。密钥只
写入本机数据根 `<宿主 home>/dsh-skills-stock/secrets.env`（权限 0600，原子覆写、合并语义、不回显
不上传），走 `/dsh-skills-stock` RPC 通道（与 `/api` 同一套 Host/Origin +
浏览器认证围栏，POST-only JSON）。

dsh 宿主会把名字含 TOKEN/KEY/SECRET/PASSWORD 的进程环境变量从 bash 子进程
剥离，因此技能脚本统一走凭据文件约定：Agent 运行脚本前在同一条 bash 命令里
`set -a; source <数据根>/secrets.env; set +a` 再执行（各技能 SKILL.md 的
「凭据配置」节已写明）。无密钥也能用的技能：options-payoff / options-volatility
/ chart-visualization 及全部纯方法论章节；akshare 兜底无需密钥。Python 依赖
（pandas / numpy / scipy / tushare / akshare 等）按脚本报错提示 `pip install`；
`common` 公共库由技能脚本自动 `pip install -e` 安装。

## 能力通告（原「股票分析专家」预设的替代）

systemPrompt 通告按**需求形态**路由到技能线，并固化：数据纪律（Tushare >
问财 > 免费源兜底，缺失如实标注禁止编造）、交付形态（研究报告 = 单文件离线
HTML 落当前工作目录）、三库入库纪律与合规边界（仅供研究参考，不构成投资建议）。

## 与 KStock 的适配关系

真源：KStock 仓 `vendor/skills/public/`（上游 KSkills 精选子集 + 本地补丁，
QiLin 沙箱语义）与 `~/.kstock/product/` 三库产品模型。本仓由
`scripts/adapt-kstock-skills.mjs` 单向适配物化技能层，三库为同构重建
（SQLite → JSON 文件）：

| QiLin/KStock 语义 | dsh 适配 |
|---|---|
| 技能挂载于 `/mnt/skills/public/<name>` 沙箱路径 | 相对路径以 resourceBase（技能包根）解析；cd 命令用 `<本技能包根>` 占位符 |
| 密钥由 required-secrets 声明、沙箱激活时注入环境 | `<数据根>/secrets.env` 凭据文件 + 运行前 source（dsh 剥离敏感进程环境变量） |
| `render_html_report` 内置看板工具交付报告 | 直接编写单文件 HTML 落盘当前工作目录 |
| 三库 SQLite 索引（kstock.db）+ /mnt 挂载 | `<数据根>/product/` 纯 JSON 文件（agent fs 工具可直接读），语义同构（乐观锁/版本链/运行归档/容量上限） |
| 桌面端策略库/因子库/选股库视图 | 侧边栏投研工作台三 tab（列表/版本时间线/运行对比/会话桥重跑） |
| `*_store` 15 工具（LangChain BaseTool） | 同名工具（dsh 原生 tool 定义，全局注册） |
| 沙箱路径规范技能 sandbox-path-guide | 不适配（dsh 无此语义） |

脚本级修补仅 4 处硬编码路径（两个 `*_cli.py` 的 common 候选路径改为按脚本
位置解析、strategy-research 两个 analysis 模块的 docstring 示例）；适配规则
与技能清单（SPEC）都集中在 adapt 脚本内，KStock 上游更新后重跑即可再生成。

## 开发

```sh
pnpm install
npm run adapt      # 从 KStock 重新适配技能（KSTOCK_REPO 可指定仓路径）
npm run check      # tsc 类型检查 + esbuild 构建（lib/ 随仓提交）
npm run smoke      # 冒烟：清单 / 适配纯度 / host apply / RPC / 三库 / 工具 / 通告 / client
npm run sync:mirror   # 镜像到 dsh-plugins 仓（--check 对账）
```

发版约定（同家族插件）：本仓为开发真源，改动推送前先 `sync:mirror` 同步到
dsh-plugins 仓并提交，保证两个安装入口一致。

## 免责声明

本插件全部技能输出仅供研究与教育参考，不构成任何投资建议；数据来源为第三方
接口（Tushare / 同花顺问财 / akshare），准确性与时效性不作保证；投资决策及
其风险由使用者自行承担。

## License

MIT
