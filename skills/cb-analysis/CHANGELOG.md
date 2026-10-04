# Changelog

## [1.2.0] - 2026-08-11

### Added
- 新增 Tushare 可转债数据访问层 `scripts/cb_data.py`（11 个子命令）：
  - 8 个接口封装：basic / daily / issue / call / share / rate / rating / holders
  - 3 个聚合命令：
    - **profile** 个券全维度档案（一次聚合 basic+issue+share+rate+rating+holders+call+ytm）
    - **terms** 条款时间线（强赎公告历史 + 评级变迁 + 当前转股价 + 下修判断）
    - **ytm** 到期收益率测算（cb_rate 现金流贴现 + 二分法反解，年化）
  - rate_clause 解析器：cb_basic.rate_clause 字符串 → 结构化现金流表
  - 全字段金额自动换算（元 → 亿元，标注 _yi 后缀）
  - NaN/None 递归清洗（JSON 输出无 NaN）
- SKILL.md v1.2.0：新增 cb-data / cb-profile / cb-terms / cb-ytm capability；
  新增「引擎5: Tushare 数据访问层」执行方式；Tushare 接口清单（8 可用 + 4 不可用）。

### Fixed
- analyze_weekly_cb.py / cb_data.py 的 kk_common 路径推断改为向上 3 级到 public/，
  再进 common/src（与 market-linkage-engine 一致），修复沙箱/受限环境的 import 失败。

### 接口可用性调研
- ✅ 可用：cb_basic / cb_daily / cb_issue / cb_call / cb_share / cb_rate / cb_rating / top10_cb_holders
- ❌ 需单独权限（未接入）：cb_factor_pro / cb_price_chg / yc_cb
- 备注：cb_rate 字段需显式 fields="ts_code,rate_freq,rate_start_date,rate_end_date,coupon_rate"
  才能取全（默认只返回 ts_code）；cb_call 状态分布（5 类）：已满足强赎条件 827 / 公告不强赎 538 /
  公告实施强赎 368 / 公告提示强赎 153 / 公告到期赎回 114。

## [1.1.0] - 2026-08-02

### Added
- 新增可转债周度全景综合引擎 analyze_weekly_cb.py（Tushare Pro，ISO 自然周聚合）：
  市场温度（中证转债指数 000832.CSI 周涨跌/周均成交/近 N 周对比）、市场规模与结构
  （存续只数/总余额/新上市/退市/条款事件）、估值全景（均价/平均溢价率/双低/价格分档）、
  资金与情绪（周成交总额/周均日成交）、双低策略池 TOP10、综合研判（0-100 分评分与
  积极/风险信号）；支持 --weeks 回溯与 --json 输出。
- SKILL.md v1.1.0：新增 cb-weekly capability 与「引擎4: 周度综合引擎」执行方式、
  周度口径说明；requires / required-secrets 新增 TUSHARE_TOKEN。

## [1.0.0] - 2026-07-03

### Added
- Initial standardized package structure.
