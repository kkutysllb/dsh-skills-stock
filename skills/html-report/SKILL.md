---
name: html-report
description: KStock 研究报告看板生成与归档——把研究结论整理为结构化报告 JSON，用技能自带渲染器（纯标准库，内联 SVG 图表）产出单文件自包含 HTML 看板，并一键归档进 KStock 报告库。适用于个股/行业/因子/策略/选股等一切需要交付 HTML 看板的场景。
version: 2.1.0
license: MIT
author: kstock
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物写入**当前工作目录**，并按 scripts/（脚本）/ data/（引擎中间产物）/ reports/（报告 JSON 与 HTML）三目录归位（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。
> - 本技能渲染器为纯标准库 Python（scripts/render_report.py），无外部依赖；归档一步在 dsh 下改用 report_archive 工具的 content_path 文件通道（KStock 桌面端本地 API 的 curl 模板已替换）。

# HTML 报告看板（生成 + 归档）

把一份完成的研究整理为可交付、可归档的 HTML 看板。与旧版
`render_html_report` 引擎工具不同，本技能**自带渲染器**：数据契约即
JSON 文件，图表由渲染器直接绘制内联 SVG——没有外部图表工具、没有
URL 契约、没有 dark/light 双文件。

## 何时使用

- 研究任务完成时需要交付「可视化看板」而非纯文字回答
- 个股深度分析、行业对比、财报解读、因子/策略回测总结等场景
- 用户要求「生成报告」「出看板」「导出 HTML」

## 工作流（四步）

以下命令都**从工作区根执行**；报告产物一律写 `reports/`（目录不存在先
`mkdir -p reports`），渲染器脚本用 html-report 技能加载结果给出的基目录
拼接全路径——**不要 cd 进技能目录执行**（技能目录只读，且 IO 文件应保持
工作区相对路径）。

1. **写报告 JSON**：把研究结论整理为报告 JSON（契约见
   `references/report-schema.md`），保存到 `reports/report.json`。
   要求：
   - `title` 必填；每个数字都必须来自你的真实计算/检索结果，禁止编造
   - 图表数据用 `sections[].blocks[].chart` 内联给出（支持
     line / area / bar / scatter / pie / radar）
   - 关键结论同时给文字与图表；风险写进顶层 `risks`
2. **渲染**：
   ```bash
   python3 "<html-report 技能包根>/scripts/render_report.py" \
     reports/report.json -o reports/<主题名>.html
   ```
   纯标准库，任何 Python ≥3.9 环境直接可跑。渲染器对缺字段宽容，
   但会在 stderr 打印告警——**有告警必须修正后重渲**。
3. **自检**：确认输出无 stderr 告警；文件为单文件 HTML（约 20-200KB），
   可直接 `file "reports/<主题名>.html"` 粗检。
4. **归档进报告库**（让用户在「投研工作台 → 报告库」随时查看）：
   调用 `report_archive` 工具归档（投研工作台「报告库」随时查看）：{title, content_path, symbol?, report_type?, generated_at?, period_start?, period_end?, risk_level?, coverage_status?}，`content_path` 传看板文件路径（如 `reports/<主题名>.html`，相对当前工作目录或绝对路径），宿主端直读文件——**禁止把 HTML 读进上下文再内联传参**。
   归档成功返回 `report_id` 与落盘绝对路径（content_path）。同一 `report_id` 重复
   归档是覆盖更新；不传 `report_id` 时按 thread+标题稳定派生。
   归档后向用户给出文件绝对路径交付 `reports/<主题名>.html`。

## 设计底线（渲染器已强制，内容端必须配合）

- **单文件自包含**：无远程图片/字体/脚本。外链只允许 `http(s)` 参考来源
- **数字可溯源**：`references` 给出来源与日期；结论性表述必须能对应到
  数据或引用
- **不给交易建议**：报告只给研究结论、情景条件、风险等级与跟踪指标
- **风险显式化**：顶层 `risks` 非空；`risk_level` 用 低/中/高

## 常见错误

- 图表 series 长度与 x 轴不一致 → 渲染器容忍但图会缺点，尽量对齐
- `metrics.value` 里塞长句 → 指标卡只放短值（如 `15.2%`），说明放 `hint`
- 把整篇报告塞进 summary → summary 是执行摘要（≤200 字），正文进 `sections`
- 归档时忘带 `content` → 服务端 422，`detail` 会说明原因

