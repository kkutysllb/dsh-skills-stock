# 研报搜索技能

财经研究报告搜索引擎，调用同花顺问财的财经资讯搜索接口，专门搜索和分析主流投研机构发布的研究报告。

## 功能特点

- **研究报告搜索**: 专门搜索各类财经研究报告和分析文章
- **专业查询处理**: 自动拆解复杂查询为多个专业查询，生成标准化关键词
- **数据质量评估**: 自动评估搜索结果的专业性和完整性
- **关键信息提取**: 提取分析逻辑、投资评级、目标价等关键信息
- **多种输出格式**: 支持CSV、JSON、Markdown等多种输出格式
- **批量处理**: 支持从文件读取多个查询并批量处理
- **错误处理**: 完善的错误处理和重试机制
- **详细日志**: 详细的运行日志和调试信息
- **跨平台支持**: 支持Windows、macOS、Linux操作系统
- **规范遵守**: 符合iwencai-skill-creator所有规范要求
- **响应透明传递**: 严格遵循iwencai-gateway-spec规范，API响应透明传递给调用方

## 数据来源

**所有研究搜索结果均来源于同花顺问财财经资讯搜索接口**，使用时请注明数据来源。

## 响应透明传递规范

本技能严格遵循iwencai-gateway-spec规范，特别是**响应透明传递要求**：

### 核心原则
- **禁止对API响应进行任何修改**：不得对网关返回的`data`、`result`、`response`等字段进行二次解析、清洗、重组
- **直接透传完整响应**：API客户端返回完整的HTTP响应体，原封不动传递给调用方
- **错误透明传递**：API返回的错误状态码与错误Body也应完整传递，不得替换为自定义错误信息

### 使用说明
1. **AI代理调用时**：必须使用`api_client.py`模块，保持响应透明传递
2. **CLI工具使用时**：可以使用`data_processor.py`进行用户界面友好的后处理
3. **代码生成时**：优先展示透明传递的API调用方式

### 违规示例（禁止）
```python
# ❌ 违规：对API响应做了二次组装
def call_api(...):
    resp = requests.post(url, headers=headers, json=payload)
    data = resp.json()
    result = {"code": 0, "data": data["result"], "msg": "success"}  # 禁止：自行包装
    return result
```

### 合规示例（推荐）
```python
# ✅ 合规：透明传递API响应
def call_api(...):
    resp = requests.post(url, headers=headers, json=payload)
    return resp  # 或 return resp.json() 直接返回原始响应
```

## 安装要求

- Python 3.7+
- requests库（通过requirements.txt安装）

## 快速开始

### 1. 获取API密钥

所有技能都需要 IWENCAI_API_KEY 环境变量才能使用。如果用户尚未配置，按以下步骤引导：

步骤 1：获取 API Key
在浏览器内打同花顺i问财SkillHub页面：https://www.iwencai.com/skillhub

步骤 2：登录

步骤 3：点击具体的Skill，打开弹窗查看详情，在安装方式-Agent用户-找到您的IWENCAI_API_KEY这一段，复制

步骤 4：配置环境变量
获取到 API Key 后，直接复制指引文字发送给AI助手，或手动设置环境变量：

### 2. 设置环境变量

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

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 基本使用

```bash
# 搜索研究报告
python research_report_search.py -q "人工智能行业研究报告"

# 搜索最近30天的研究报告
python research_report_search.py -q "芯片行业" -d 30

# 限制返回结果数量
python research_report_search.py -q "新能源汽车" -l 5

# 导出为CSV格式
python research_report_search.py -q "人工智能" -o results.csv -f csv

# 导出为JSON格式
python research_report_search.py -q "人工智能" -o results.json -f json

# 导出为Markdown报告格式
python research_report_search.py -q "医药行业" -o report.md -f markdown
```

### 5. 测试API连接
```bash
python research_report_search.py --test
```

### 6. curl示例
```bash
# 使用环境变量中的 API Key
curl -X POST "https://openapi.iwencai.com/v1/comprehensive/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $IWENCAI_API_KEY" \
  -H "X-Claw-Call-Type: normal" \
  -H "X-Claw-Skill-Id: report-search" \
  -H "X-Claw-Skill-Version: 2.0.0" \
  -H "X-Claw-Plugin-Id: none" \
  -H "X-Claw-Plugin-Version: none" \
  -H "X-Claw-Trace-Id: $(python -c 'import secrets; print(secrets.token_hex(32))')" \
  -d '{
    "channels": ["report"],
    "app_id": "AIME_SKILL",
    "query": "人工智能行业研究报告"
  }'
```

## 批量处理

```bash
# 从文件读取多个查询并批量处理
python research_report_search.py -i queries.txt -o ./results

# 指定输出格式为JSON
python research_report_search.py -i queries.txt -o ./results -f json
```

## 时间范围搜索

```bash
# 搜索指定时间范围的研究报告
python research_report_search.py -q "新能源车" --date-from "2024-01-01" --date-to "2024-03-31"

# 搜索最近7天的研究报告
python research_report_search.py -q "人工智能" -d 7
```

## 命令行参数

### 基本搜索参数
- `-q, --query`: 搜索关键词（支持中文）
- `-o, --output`: 输出文件路径
- `-f, --format`: 输出格式（csv, json, text, markdown）
- `-l, --limit`: 结果数量限制（默认10）

### 批量处理参数
- `-i, --input`: 输入文件路径（支持批量查询）
- `--input-format`: 输入文件格式（txt, csv, json）
- `--output-dir`: 输出目录（批量处理时使用）

### 过滤与排序参数
- `--date-from`: 开始日期（YYYY-MM-DD）
- `--date-to`: 结束日期（YYYY-MM-DD）
- `-d, --days`: 最近N天（与date-from/date-to互斥）
- `--sort-by`: 排序字段（date, relevance）
- `--sort-order`: 排序顺序（asc, desc）

### 其他参数
- `-v, --verbose`: 详细输出模式
- `--debug`: 调试模式
- `--test`: 测试API连接
- `--config`: 配置文件路径
- `-h, --help`: 显示帮助信息

## 配置文件

技能使用 `config.example.json` 作为配置文件示例，实际配置应通过环境变量或自定义配置文件设置。

### 配置示例 (config.example.json)
```json
{
  "api": {
    "base_url": "https://openapi.iwencai.com",
    "endpoint": "/v1/comprehensive/search",
    "timeout": 30,
    "max_retries": 3,
    "retry_delay": 1.0
  },
  "search": {
    "channels": ["report"],
    "app_id": "AIME_SKILL",
    "default_limit": 10,
    "default_days": 30,
    "min_articles_for_sufficient": 3
  },
  "output": {
    "default_format": "text",
    "csv_encoding": "utf-8-sig",
    "json_indent": 2
  },
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  },
  "注意": "API密钥应从环境变量 IWENCAI_API_KEY 获取，不要在此配置文件中硬编码",
  "数据来源": "本技能所有数据均来源于同花顺问财财经资讯搜索接口，使用时请注明数据来源"
}
```

## 使用示例

### 示例1：基本搜索
```bash
python research_report_search.py --query "人工智能行业研究报告" --output ai_reports.csv --format csv
```

### 示例2：批量处理
```bash
# queries.txt 内容：
# 人工智能
# 芯片行业
# 新能源汽车
# 医药行业

python research_report_search.py --input queries.txt --output-dir ./reports --format json
```

### 示例3：专业分析报告
```bash
python research_report_search.py --query "特斯拉投资评级目标价" --output tesla_analysis.md --format markdown --limit 5
```

### 示例4：时间范围搜索
```bash
python research_report_search.py --query "央行货币政策" --date-from "2024-01-01" --date-to "2024-03-31" --output monetary_policy.json --format json
```

## 数据来源声明

**重要**：在使用本技能返回的数据时，必须明确标注数据来源：

```
根据同花顺问财提供的研究报告数据，以下是相关分析：

1. 《2024年人工智能行业发展趋势报告》
   数据来源：同花顺问财
   发布时间：2024-01-15
   投资评级：买入
   目标价：120元
   
2. 《金融科技AI应用研究报告》
   数据来源：同花顺问财
   发布时间：2024-01-14
   投资评级：增持
   目标价：95元
```

## 接口规范

本技能严格遵守iwencai-skill-creator规范，所有发往问财 OpenAPI 网关的请求包含以下 Header：

| Header | 取值说明 |
|--------|----------|
| `X-Claw-Call-Type` | `normal`：正常请求；`retry`：失败后的重试 |
| `X-Claw-Skill-Id` | 技能标识：`report-search` |
| `X-Claw-Skill-Version` | 技能版本：`2.0.0` |
| `X-Claw-Plugin-Id` | 插件 ID：`none` |
| `X-Claw-Plugin-Version` | 插件版本：`none` |
| `X-Claw-Trace-Id` | **每次请求必须新生成**的**全局唯一**追踪 ID；**长度为 64 个字符** |

## 注意事项

1. **API密钥安全**: API密钥必须通过环境变量设置，不要硬编码在代码中
2. **认证方式**: 必须使用Bearer Token认证方式
3. **数据来源标注**: 必须明确标注数据来源于同花顺问财
4. **规范遵守**: 必须遵守iwencai-skill-creator的所有规范要求
5. **使用限制**: 遵守接口调用频率限制
6. **错误处理**: 技能包含完善的错误处理和重试机制
7. **跨平台支持**: 支持Windows、macOS、Linux操作系统

## 技术支持

如有问题，请参考：
- `SKILL.md`: 技能详细说明文档
- `references/api.md`: 接口文档
- 示例代码：`scripts/example_usage.py`

---
版本：2.0.0
更新日期：2026-04-17