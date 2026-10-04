---
name: report-search
description: 收录了主流投研机构发布的研究报告，帮你快速获取专业、深度的分析逻辑、投资评级、目标价等重要投研决策信息。
version: 2.0.0
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物（报告 HTML、图表、JSON、Excel）一律写入**当前工作目录**（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# 研报搜索技能

## 版本
当前技能版本：2.0.0（与X-Claw-Skill-Version头一致）

## 首次使用 - 获取 API Key
所有技能都需要 IWENCAI_API_KEY 环境变量才能使用。 如果用户尚未配置，按以下步骤引导：

步骤 1：获取 API Key
在浏览器内打同花顺i问财SkillHub页面：https://www.iwencai.com/skillhub

步骤 2：登录

步骤 3：点击具体的Skill，打开弹窗查看详情，在安装方式-Agent用户-找到您的IWENCAI_API_KEY这一段，复制

步骤 4：配置环境变量
获取到 API Key 后，直接复制指引文字发送给AI助手，或手动设置环境变量：

## 技能概述

本技能是一个财经研究报告搜索引擎，通过调用同花顺问财的财经资讯搜索接口，专门搜索和分析主流投研机构发布的研究报告，帮助用户获取专业的分析逻辑、投资评级、目标价等重要投研决策信息。本技能符合iwencai-skill-creator规范，确保所有API调用遵循问财OpenAPI网关的标准要求。

## 技能功能

### 1. 研究报告搜索
- 搜索各类财经研究报告和分析文章
- 覆盖主流投研机构、证券公司、研究机构等
- 支持中文关键词搜索，专注于研究报告类型
- 符合iwencai-gateway-spec规范，包含完整的X-Claw-* Header

### 2. 智能查询处理能力
- 自动拆解复杂查询为多个专业查询
- 示例：用户问"人工智能和芯片行业的研究报告"可以拆分为"人工智能行业研究报告"和"芯片行业研究报告"
- 根据查询复杂度决定调用接口的次数
- 生成标准化的专业查询关键词

### 3. 数据质量评估与扩展
- 自动评估搜索结果的专业性和相关性
- 检查研究报告是否包含分析逻辑、投资评级、目标价等关键信息
- 如有必要，可调用其他技能或工具扩展数据源
- 对搜索结果进行专业质量评估

### 4. 专业数据处理与返回
- 对研究搜索结果进行专业排序、过滤和摘要
- 提取关键信息：分析逻辑、投资评级、目标价、风险提示等
- **⚠️ 重要警告：根据问财OpenAPI网关规范条件六，API原始响应必须透明传递**
- **必须遵守**：不得对API响应进行二次解析、清洗、重组或再加工
- **透明传递要求**：
  - 直接返回API原始响应JSON，不做任何包装
  - 错误响应也必须原样传递，不得替换为自定义错误信息
  - 网络层错误（超时、连接失败等）可提供技术性错误信息
- 将透明传递的响应数据返回给大模型进行处理
- 大模型负责生成专业、深度的回答格式

## 接口规范

### HTTP Header 要求
所有发往问财 OpenAPI 网关的请求必须包含以下 Header：

| Header | 取值说明 |
|--------|----------|
| `X-Claw-Call-Type` | `normal`：正常请求；`retry`：失败后的重试。按实际调用场景二选一。 |
| `X-Claw-Skill-Id` | 技能标识，固定为 `report-search`。 |
| `X-Claw-Skill-Version` | 当前技能版本号，固定为 `2.0.0`。 |
| `X-Claw-Plugin-Id` | 插件 ID，固定为 `none`。 |
| `X-Claw-Plugin-Version` | 插件版本，固定为 `none`。 |
| `X-Claw-Trace-Id` | **每次请求必须新生成**的**全局唯一**追踪 ID；**长度为 64 个字符**（使用 64 位十六进制字符串）。 |

### 基础信息
- **Base URL**: `https://openapi.iwencai.com`
- **接口路径**: `/v1/comprehensive/search`
- **请求方式**: POST（优先使用 POST）
- **认证方式**: API Key (Bearer Token)

### 认证要求
在请求头中需要携带API Key进行认证：
```
Authorization: Bearer {IWENCAI_API_KEY}
```
其中 `IWENCAI_API_KEY` 是用户申请的有效API密钥，需要设置为环境变量。

### 请求参数
```json
{
  "channels": ["report"],
  "app_id": "AIME_SKILL",
  "query": "搜索关键词"
}
```

**重要参数说明**：
- `channels`: 固定为 `["report"]`，表示搜索研究报告类型
- `app_id`: 固定为 `AIME_SKILL`
- `query`: 用户搜索关键词，支持中文

### 响应透明传递要求（Non-Negotiable）
**核心原则：Skill 生成的代码必须透明传递 API 响应，不得对返回内容做任何修改、过滤、重组或再加工后再交付给调用方。**

1. **禁止行为**：
   - 不得对网关返回的 `data`、`result`、`response` 等字段进行二次解析、清洗、重组；
   - 不得自行添加、删除、修改返回结果的任何键值或结构；
   - 不得在 Skill 生成的代码中将 API 原始响应包装成另一套 `result` / `output` / `data` 等结构再返回；
   - 不得在返回前对响应内容做任何「业务逻辑层」的处理（如字段映射、类型转换、格式化等），这些应由调用方决定如何处理。

2. **要求行为**：
   - **直接透传**：对网关返回的完整 HTTP 响应体（Body），应在获取后**原封不动**地传递给调用方（或返回给 LLM）；
   - **透明返回**：若使用 Python 等语言实现，返回值应为对 API 响应的直接赋值或简单的 `return response`，不做任何中间 transformation；
   - **错误传递**：API 返回的错误状态码与错误 Body 也应完整传递，不得替换为自定义错误信息（除非是网络层超时、连接失败等技术性错误）。

3. **正确实现示例**：
```python
# ✅ 正确：直接返回API响应
def search_reports(query: str):
    response = requests.post(url, headers=headers, json=payload)
    # 直接返回API响应，不做任何处理
    return response.json()
```

4. **错误实现示例**：
```python
# ❌ 错误：对API响应做了二次组装
def search_reports(query: str):
    resp = requests.post(url, headers=headers, json=payload)
    data = resp.json()
    result = {"code": 0, "data": data["result"], "msg": "success"}  # 禁止：自行包装
    return result
```

## 使用说明

### 环境变量配置

#### Unix/Linux/macOS (bash/zsh)
```bash
export IWENCAI_API_KEY="your_api_key_here"
```

#### Windows PowerShell
```powershell
$env:IWENCAI_API_KEY="your_api_key_here"
```

#### Windows CMD
```cmd
set IWENCAI_API_KEY=your_api_key_here
```

### 命令行使用
```bash
# 基本搜索
python research_report_search.py -q "人工智能行业研究报告"

# 限制结果数量
python research_report_search.py -q "芯片行业" -l 5

# 导出为CSV格式
python research_report_search.py -q "新能源汽车" -o results.csv -f csv

# 批量处理
python research_report_search.py -i queries.txt -o ./results -f json

# 时间范围搜索
python research_report_search.py -q "医药行业" --date-from "2024-01-01" --date-to "2024-03-31"

# 获取帮助
python research_report_search.py -h
```

### curl 示例
```bash
# 生成64位十六进制Trace ID
TRACE_ID=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# 使用环境变量中的 API Key
curl -X POST "https://openapi.iwencai.com/v1/comprehensive/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $IWENCAI_API_KEY" \
  -H "X-Claw-Call-Type: normal" \
  -H "X-Claw-Skill-Id: report-search" \
  -H "X-Claw-Skill-Version: 2.0.0" \
  -H "X-Claw-Plugin-Id: none" \
  -H "X-Claw-Plugin-Version: none" \
  -H "X-Claw-Trace-Id: $TRACE_ID" \
  -d '{
    "channels": ["report"],
    "app_id": "AIME_SKILL",
    "query": "人工智能行业研究报告"
  }'
```

**Windows PowerShell 示例：**
```powershell
# 生成64位十六进制Trace ID
$TRACE_ID = python -c "import secrets; print(secrets.token_hex(32))"

# 调用研报搜索接口
$headers = @{
    "Content-Type" = "application/json"
    "Authorization" = "Bearer $env:IWENCAI_API_KEY"
    "X-Claw-Call-Type" = "normal"
    "X-Claw-Skill-Id" = "report-search"
    "X-Claw-Skill-Version" = "2.0.0"
    "X-Claw-Plugin-Id" = "none"
    "X-Claw-Plugin-Version" = "none"
    "X-Claw-Trace-Id" = $TRACE_ID
}

$body = @{
    channels = @("report")
    app_id = "AIME_SKILL"
    query = "人工智能行业研究报告"
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://openapi.iwencai.com/v1/comprehensive/search" -Method Post -Headers $headers -Body $body
```

## 使用场景

### 何时调用本技能
1. **行业研究报告搜索**: 当用户需要了解特定行业的专业研究报告时
2. **公司分析报告查询**: 当用户需要获取特定公司的深度分析报告时
3. **投资评级查询**: 当用户需要了解投资评级和目标价信息时
4. **趋势分析报告**: 当用户需要获取行业趋势和专业分析时
5. **投研决策支持**: 当用户需要专业投研信息支持决策时

### 调用示例
1. 用户问："人工智能行业的最新研究报告有哪些？"
2. 用户问："特斯拉的投资评级和目标价是多少？"
3. 用户问："芯片行业的深度分析报告有哪些？"
4. 用户问："新能源车行业的投资前景分析报告？"
5. 用户问："医药行业的研究报告和投资建议？"

## 技能内部逻辑

### 查询处理流程
1. **接收用户查询**: 获取用户的专业搜索需求
2. **查询拆解分析**: 分析查询复杂度，决定是否需要拆分为多个专业子查询
3. **专业查询生成**: 生成标准化的专业查询关键词，优化搜索效果
4. **API调用执行**: 生成并执行API调用代码，使用Bearer Token认证和X-Claw-* Header
5. **数据质量评估**: 检查返回的研究报告是否专业、完整，能否回答用户问题
6. **专业数据处理**: 对搜索结果进行专业排序、过滤、摘要和关键信息提取
7. **结果整合返回**: 将处理后的专业结果返回给大模型，生成深度回答

### 代码生成要求
- 生成完整的API调用代码，包括Bearer Token认证、X-Claw-* Header、64字符Trace ID
- 处理网络异常和接口错误，实现专业重试机制
- **严格遵守响应透明传递要求**：返回完整的API响应，不得对响应内容做任何修改、过滤、重组
- 确保代码符合Python最佳实践，可读性和可维护性高
- **注意**：仅在用户明确要求进行数据处理时，才在返回给用户前进行适当的格式化展示，但API调用本身必须保持透明传递

## 数据来源标注

**重要**: 所有研究搜索结果均来源于同花顺问财财经资讯搜索接口，在回答用户问题时必须明确标注数据来源。

示例标注格式：
- "根据同花顺问财提供的研究报告数据..."
- "数据来源：同花顺问财财经资讯搜索（研究报告）"
- "同花顺问财研究报告显示..."
- "基于同花顺问财的研究报告分析..."

## 技术实现

### Python代码要求
- 使用Python 3.7+版本
- 优先使用Python标准库和官方包
- 常用库允许使用：requests, pandas, numpy等
- 尽量减少第三方库依赖
- 代码结构清晰，模块化设计

### 配置文件要求
- 必须包含 `config.example.json` 配置文件示例
- 必须实现 `config.py` 配置管理模块
- API密钥必须从环境变量 `IWENCAI_API_KEY` 获取，不得硬编码

### 目录结构要求
```
研报搜索/
├── README.md              # 技能说明文档（中文）
├── SKILL.md              # 技能主文档（包含YAML frontmatter）
├── references/           # 参考文档目录
│   └── api.md           # 接口文档副本
└── scripts/             # 源代码目录
    ├── __main__.py      # 命令行入口点
    ├── config.py        # 配置管理模块
    ├── config.example.json # 配置文件示例
    ├── requirements.txt # Python依赖文件
    ├── setup.py         # 安装配置
    ├── research_report_search.py # 主程序文件
    ├── api_client.py    # API客户端模块
    ├── data_processor.py # 数据处理模块
    ├── cli.py           # CLI接口模块
    ├── example_usage.py # 使用示例
    └── test_basic.py    # 基础测试
```

### CLI接口要求
- 支持 `python research_report_search.py` 调用方式
- 支持 `python -m scripts.research_report_search` 调用方式
- 提供完整的命令行参数和帮助文档
- 支持多种输出格式：csv, json, text, markdown

### API透明传递与CLI数据处理区分说明
1. **API客户端模块 (api_client.py)**：
   - 严格遵守响应透明传递要求，返回完整的API响应
   - 不进行任何数据清洗、重组或业务逻辑处理
   - 仅处理网络层错误和认证问题

2. **CLI工具与数据处理模块 (cli.py, data_processor.py)**：
   - 这些模块仅用于命令行工具的后处理功能
   - 当使用CLI工具时，可以对API响应进行格式化、过滤等用户界面友好的处理
   - 但在技能被AI调用时，必须使用API客户端模块的透明传递方式

3. **重要原则**：
   - 当技能被AI代理调用时，必须生成使用api_client.py的代码，并保持响应透明传递
   - 当用户直接使用CLI工具时，可以使用data_processor.py进行后处理
   - SKILL.md中的代码示例应优先展示透明传递的API调用方式

## 注意事项

1. **数据专业性**: 专注于研究报告类型，确保返回结果的深度和专业性
2. **认证合规**: 必须使用Bearer Token认证方式，符合公网访问要求
3. **来源标注**: 必须明确标注数据来源于同花顺问财
4. **错误处理**: 实现完善的错误处理和重试机制
5. **性能优化**: 考虑接口调用频率限制，实现合理的请求间隔
6. **用户体验**: CLI接口要直观易用，提供清晰的专业反馈
7. **规范遵守**: 必须遵守iwencai-skill-creator的所有规范要求

## 凭据配置（dsh 适配）

本技能脚本运行需要以下密钥（缺失时脚本会明确报错，不会编造数据）：

| 环境变量 | 用途 | 获取渠道 |
|---|---|---|
| `IWENCAI_API_KEY` | 同花顺问财 OpenAPI（自然语言数据查询） | 问财开放平台控制台 |

dsh 宿主会把名字含 TOKEN/KEY/SECRET/PASSWORD 的进程环境变量从 bash 子进程中剥离，
因此统一走**凭据文件**约定。插件数据根（下称「数据根」）= 宿主 home 下的
`dsh-skills-stock/`，宿主 home 按 `$QILIN_HOME → $DSH_HOME → ~/.dsh` 解析
（未设环境变量时即 `~/.dsh/dsh-skills-stock`；工作台设置页「数据源」会显示绝对路径）：

1. 把密钥写入 `<数据根>/secrets.env`（权限 0600）：
   ```bash
   IWENCAI_API_KEY=你的密钥
   ```
2. 运行技能脚本时，在同一条 bash 命令里先加载再执行（bash 内 export 的变量可以传给子进程）：
   ```bash
   set -a; source <数据根>/secrets.env; set +a
   cd scripts && python3 <脚本名> <参数>
   ```

Python 依赖（pandas/numpy/scipy/tushare/akshare 等）按脚本报错提示 `pip install` 即可；
`../common` 公共库由脚本自动 `pip install -e` 安装（候选路径已按 dsh 插件布局解析）。
