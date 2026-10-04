# KStock 2.0 适配升级实施计划（v1.2.2 → v1.3.0）

> 状态：✅ 已实施（v1.3.0）｜ 基线：v1.2.2 快照（31b6999）→ 计划（36f5fd1）→
> 上游重适配（3caca0e）→ 四库实现（6f3c96e）
> 上游：KStock 2.0.0-rc.2（用户口径）/ 本地仓 2.0.0-rc.3（vendor/skills @ 84d2d1ae）
> 决策记录：**报告库走 agent 工具通道**（与三库同构的 `report_*` 工具），
> 不做「curl 到插件 RPC」形态——dsh 的 RPC 是浏览器→宿主通道，agent 的
> bash 里 curl 不到；工具形态让 html-report 与 10 个场景手册的改写最自然，
> 且与既有 15 个三库工具同一纪律（写入只走工具、UI 只读）。

## 1. 背景与差距（分析结论）

v1.2.2 对齐的是 KStock 1.x（30 技能 / 三库 / `render_html_report` 内置工具）。
KStock 2.0 的变化：

| # | 上游变化 | 对本插件的影响 |
|---|---|---|
| 1 | 技能 30 → 42：新增 10 个场景编排手册（stock-due-diligence / stock-screening-theme / strategy-backtest-theme / factor-analysis-theme / chan-stock-theme / cb-panorama / market-linkage / index-futures-theme / option-etf-theme / option-futures-linkage-theme）+ html-report + market-scan-workflow | 需新增适配 11 个、排除 1 个（market-scan-workflow 依赖 QiLin `workflow` 工具，dsh 无对应编排原语） |
| 2 | 产品模型三库 → **四库**：新增报告库（quant-reports：SQLite 索引 + HTML 落盘、**无版本链、同 report_id 覆盖**、sha256、单份 8MB 上限） | dsh 侧新增报告库存储 + 工具 + 工作台第四 tab |
| 3 | 归档通道：场景技能与 html-report 用 `curl POST http://127.0.0.1:18001/kstock-api/*`（策略三步 create/version/run；报告一步） | KStock 桌面端本地 API 在 dsh 不存在 → 改写为同名 agent 工具调用 |
| 4 | 引擎脚本修复漂移 ~21 文件：stock-analysis 19 文件（缠论 v2 动力学全套/评分器映射/pandas3 `T→min`/None 守卫等）+ common 2 文件（tushare_client 去 set_token 化、market_data_cache.py 缓存层级重写） | 重跑适配即同步；但 market_data_cache.py 补丁锚点失效 → **`npm run adapt` 当前必失败**，需先修补丁 |
| 5 | industry-analysis 阶段四重写（render_html_report → html-report 技能 + 报告库归档）、a-stock-screener/news-search 各 1 处新引用 | 适配脚本的 `INDUSTRY_LINE_REWRITES` 过时，需按新正文重写 |
| 6 | 新宿主语义措辞：html-report 基目录占位符、`present` 内置工具、sandbox-path-guide 引用、产物分区纪律（scripts/data/reports） | 新增改写规则 + 残留检查 |

## 2. 工作分解

### A. 适配脚本 `scripts/adapt-kstock-skills.mjs`

1. **SPEC +11**：10 个场景手册（category `场景编排`，插在 industry-analysis 之后）
   + html-report（category `呈现`，插在 chart-visualization 之前）；
   `EXCLUDED_SKILLS` 增加 `market-scan-workflow`（同 sandbox-path-guide 待遇）。
2. **market_data_cache.py 补丁重写**（rc.3 新锚点）：
   - docstring 第 2 条候选 `~/.kstock/cache/market-data` → `<宿主 home>/dsh-skills-stock/cache/market-data`（dsh 数据根口径）；
   - `cache_dir()` 默认候选块：`~/.kstock` 改为 `$QILIN_HOME → $DSH_HOME → ~/.dsh` + `/dsh-skills-stock` 解析，探测失败仍落系统临时区保底（上游新逻辑已自带「绝不因缓存失败」语义，dsh 补丁只换持久目录）。
3. **新改写规则**（bodyRules / 专项函数）：
   - 归档块重写器：含 `kstock-api/<lib>` 的 ```bash 围栏块 → 该库的 dsh 工具三步（strategies → strategy_create/save_version/record_backtest；factors → factor_*；selections → selection_*；reports → report_archive 单步）；
   - 句级：`引擎本机 \`http://127.0.0.1:18001\`，三步（均 curl POST…）：` → 四库工具措辞；`html-report SKILL.md 中的 curl 模板` → `html-report 技能的 report_archive 工具`；`` `present` 呈现 `` / `，present 呈现` → 给出文件绝对路径交付；`<html-report 基目录>` → `<html-report 技能包根>`（Base directory 说明改 skill_resources 口径）；`量化工作台` → `投研工作台`；`PATCH /kstock-api/<lib>/{id}` → 既有 id 迭代措辞；`见 sandbox-path-guide` → 见顶部适配说明；`~/.kstock/config/secrets.env` → `<数据根>/secrets.env`。
4. **头部适配说明新增产物分区纪律**：scripts/ data/ reports/ 三目录归位（从工作区根执行）。
5. **RESIDUAL_PATTERNS 扩充**：`kstock-api|127.0.0.1:18001`、`` `present` ``/`present 呈现`、`sandbox-path-guide`、`~/.kstock`、`均 curl POST`、`PATCH /kstock-api`、`◆TODO◆`、`workflow 工具` —— 发现即失败，防规则漏网。
6. 重跑 `npm run adapt`：同步 stock-analysis 19 文件 + common 2 文件修复 + 11 个新技能物化；产物自检全绿。

### B. 报告库（四库对齐）

1. **`src/reports.ts`（新增）**：`ReportStore`——
   - 布局 `<数据根>/product/reports/<report_id>/report.json`（meta）+ `content.html`（全文 0600，临时文件 + rename 原子写）；
   - `archive()`：title/content 必填；content ≤8MB（KStock MAX_REPORT_BYTES 同量级）；report_id 调用方可给（白名单 `/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/`，防路径穿越），缺省按 `thread_id + title` sha1 稳定派生（`rpt_` 前缀）→ 同 id 重复归档即覆盖更新（updated 标记、sha256/size/updated_at 刷新）；
   - `list()`：轻量 meta 投影（不含 content），updated_at 倒序；
   - `get(id, withContent)`；`delete(id)`；
   - 错误复用 `LibraryError`（toolEnvelope/RPC 错误信封统一处理）。
2. **`src/tools.ts` +3 工具**（15 → 18）：
   - `report_archive`：归档/覆盖更新，thread_id 自动绑定来源会话；
   - `report_list`：报告清单（title/symbol/type/generated_at/risk/size）；
   - `report_get`：读 meta，`content: true` 时返回 HTML 全文（默认只回路径，防上下文灌爆）。
3. **`src/rpc.ts` +2 端点**：`reports_list` / `reports_get`（工作台 UI 只读纪律同三库）。
4. **`src/index.ts`**：实例化 ReportStore → 注册工具 → 传入 RPC。

### C. 工作台第四 tab（client）

1. `runtime.ts`：`WorkbenchTab = LibraryTab | 'reports'`；`loadReports()`（reports_list）、`openReport(id)`（reports_get content:true）、`closeReport()`；PanelState 增 `reports` 列表态 + `reportDetail`。
2. `WorkbenchView.tsx`：四 tab；reports tab 列表（标题/symbol/类型/时间/风险/大小）→ 详情（meta + `<iframe srcdoc>` 内嵌预览 + blob URL 新窗口打开按钮）；版本时间线/运行对比仅三库渲染。
3. `locales.ts` / `styles.ts`：报告库词条（zh/en）+ iframe/详情样式。
4. `RunCompare.tsx` 类型随 WorkbenchTab 收紧不受影响（reports 无 runs，不进入对比路径）。

### D. 通告 / 冒烟 / 文档 / 版本

1. **`guidance.ts`**：30 → 41 个技能；三库 → 四库；路由新增场景编排一行 + html-report；四库工具一句（报告库 report_archive 同 id 覆盖）；保留全部既有约定关键词（smoke 断言）。
2. **`smoke-plugin.mjs`**：EXPECTED_SKILL_COUNT = 41；工具断言 18（含 report_* 名单）；残留模式与适配脚本对齐扩充；新增报告库 RPC/存储断言（归档→列表→读回→覆盖更新→8MB 拒绝→非法 id 拒绝→路径穿越拒绝）；client 断言四 tab + reports_list/reports_get。
3. **`README.md` / `package.json` / `cordis.patch.yml`**：41 技能表（场景编排/呈现归类）、四库与 18 工具口径、适配关系表补三行（html-report 渲染器直用、curl 三步 → 工具调用、workflow 工具排除）；版本 1.2.2 → **1.3.0**；patch 头注释 30 → 41。
4. `npm run check && npm run smoke` 全绿（lib/ 随仓提交，重新构建）。

## 3. 不做 / 后续

- `market-scan-workflow` 不适配（QiLin `workflow` 编排工具 dsh 无对应物）；若未来 dsh 提供子代理编排原语再评估。
- `report_delete` 工具与工作台删除按钮暂缓（KStock 有删除标记语义，v1.3 先收口归档/查看/对比主链路）。
- 工作台报告详情不做全文搜索/标签筛选（KStock 桌面端也未提供）。

## 4. 验收清单（实施结果）

- [x] `npm run adapt` 对 rc.3 上游全量重跑成功，残留检查全绿（新增 7 条模式），幂等复跑零差异。
- [x] stock-analysis 19 文件、common 2 文件与上游一致（除白名单补丁点，漂移复检逐技能归零）。
- [x] skills/ 含 41 个技能目录 + manifest；html-report 正文无 curl/present/18001 残留；场景手册归档节为工具调用三步。
- [x] 18 个 agent 工具注册；report_archive 归档 → reports_list 可见 → reports_get 取回 HTML 全文；同 id 覆盖（sha256 刷新/updated 标记）、8MB 拒绝、report_id 白名单拒绝穿越，均入冒烟断言。
- [x] 工作台四 tab；报告库列表/内嵌 iframe 预览（sandbox 全关）/blob 新窗口打开，构建产物 lib/client.js 含 reports_list/reports_get 与 kss-report-frame。
- [x] `npm run check`（tsc + esbuild）与 `npm run smoke`（369 项 PASS / 0 FAIL）全绿；版本 1.3.0，README/patch 头注释四库口径。

## 4.1 实施期修正记录（与原设计的差异，均为验证驱动）

1. **报告归档断链修正（实测驱动，commit bd78b60）**：真实任务中 agent 交付了
   55KB 单行压缩 HTML 看板但拒绝调用 report_archive——工具原设计只收
   `content` 内联全文，LLM 逐字转录必有损坏风险（bash 不能调工具、read 工具
   给带行号转写）。已增 `content_path` 文件通道（宿主端直读，绝对路径或相对
   会话 cwd），`content` 保留给小块内容；技能正文/场景手册/通告同步口径。
2. **错误类型**：B1 原文「错误复用 LibraryError」，实现为同构 `ReportError`
   （tools/RPC 信封同样映射 code/message，避免存储模块间循环依赖）。
3. **双通道边界修复（设计核查驱动）**：`harnessHome()` 原实现 `QILIN_HOME ??
   DSH_HOME` 在「QILIN_HOME 设为空白 + DSH_HOME 有效」时会跳过 DSH_HOME
   直落 ~/.dsh，与 docstring 及 common 缓存补丁的 or 链语义不一致；已改为
   空白视为未设置并继续向下解析，冒烟固化（优先级 + 空白回落两项断言）。

## 4.2 双通道确认（dsh + 麒麟）

manifest 两通道同源：`dsh.bundle.patch` 与 `qilin.bundle.patch` 指向同一份
`./cordis.patch.yml`，`dsh.client` 与 `qilin.client` 同平台（web）同 inject
（6 项）——即同一交付物，行为完全一致；数据根解析 `$QILIN_HOME →
$DSH_HOME → ~/.dsh`（含空白回落）由冒烟两项断言固化。qilin CLI 本机未装，
无法做端到端麒麟安装验证；结构对账 + 冒烟断言为当前可执行的最高确认强度。

## 5. 发版待办（不在本次代码修改范围）

- `npm run sync:mirror` 同步 dsh-plugins 镜像仓并在对方仓提交推送（发版约定，涉及第二仓库的对外推送，留发布时执行）。
- npm 发布 / GitHub tag v1.3.0。
