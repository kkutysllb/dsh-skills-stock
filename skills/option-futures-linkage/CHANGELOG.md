# Changelog

本项目所有重要变更均会记录于此文件。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [1.1.0] - 2026-08-10

### 修复（Critical）
- **IV 反解在沙箱/受限环境连续失败问题**：此前 `option_futures_analyzer.py` 顶部 `try: from scipy.stats import norm`，缺失时设 `norm = None`，注释声称"无 scipy 时降级（IV 用近似公式）"，但 `implied_vol` 第 108 行 `if norm is None: return None` 直接短路，**降级路径从未实现**，导致 ATM IV / 加权 IV / Risk Reversal / IV 斜率在无 scipy 环境下全部为 None。

### 变更
- 新增 `_norm_cdf`（Abramowitz & Stegun 26.2.17 近似，误差 < 1e-7）、`_norm_pdf`、`_HAS_SCIPY` 标志。
- `bs_price`：有 scipy 用 `scipy.stats.norm.cdf`，否则用 `_norm_cdf`。
- `implied_vol`：有 scipy 用 `brentq`（区间二分），无 scipy 用 Newton-Raphson 迭代（vega 作导数，初值取 Brenner-Subrahmanyam 近似，100 次迭代上限，越界返回 None）。
- **验证**：模拟无 scipy 环境下 IF 主力（S=3800, K=3800, T=30/365）反解 call iv=6.16%、put iv=7.14%，回填 BS 价格误差 < 1e-6，与 scipy 结果方向量级一致。

### 文档
- SKILL.md `requires.packages` 移除 scipy，新增 `optionalPackages: ["scipy"]`。
- SKILL.md `metadata.openclaw.install` 新增 `pip-optional-scipy` 条目，标注可选。
- 版本号 1.0.0 → 1.1.0（SKILL.md `version` + `metadata.openclaw.version`）。

## [1.0.0] - 2026-08-02

### 新增
- 首个版本：期指期权联动分析引擎。
- 支持 IF/IH/IC/IM 四大期指 × 对应期权 5 维联动信号分析（日/周双粒度）。
- 期权维度：PCR、ATM/加权 IV（BS 反解）、IV 斜率、Risk Reversal、认沽认购 IV 差。
- 期指维度：主力识别、均线趋势、持仓变化、基差信号。
- 联动评分（-6~+6）与策略建议。
