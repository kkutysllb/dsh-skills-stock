---
name: news-search
description: 财经领域为主的资讯搜索引擎，囊获了各类型媒体：官媒、主流财经媒体、垂直行业网站、知名上市公司/非上市公司官网等，可以帮助你了解最新财经事件、政策动态、行业革新、企业业务进展等等。
version: 1.0.0
---

# 新闻搜索技能

## 版本
当前技能版本：1.0.0（与X-Claw-Skill-Version头一致）

## 技能概述

本技能是一个财经领域为主的资讯搜索引擎，通过调用同花顺问财的财经资讯搜索接口，帮助用户获取最新的财经新闻、政策动态、行业革新和企业业务进展等信息。本技能严格遵守问财OpenAPI网关规范。

## 首次使用 - 获取 API Key

所有技能都需要 IWENCAI_API_KEY 环境变量才能使用。 如果用户尚未配置，按以下步骤引导：

步骤 1：获取 API Key
在浏览器内打同花顺i问财SkillHub页面：https://www.iwencai.com/skillhub

步骤 2：登录

步骤 3：点击具体的Skill，打开弹窗查看详情，在安装方式-Agent用户-找到您的IWENCAI_API_KEY这一段，复制

步骤 4：配置环境变量
获取到 API Key 后，直接复制指引文字发送给AI助手，或手动设置环境变量：

**Unix/Linux/macOS (bash/zsh):**
```bash
export IWENCAI_API_KEY="your_api_key_here"
```

**Windows (PowerShell):**
```powershell
$env:IWENCAI_API_KEY="your_api_key_here"
```

**Windows (CMD):**
```cmd
set IWENCAI_API_KEY=your_api_key_here
```

## 技能功能

### 1. 财经资讯搜索
- 搜索各类财经新闻和资讯
- 覆盖官媒、主流财经媒体、垂直行业网站、知名上市公司/非上市公司官网等
- 支持中文关键词搜索

### 2. 查询处理能力
- 自动拆解复杂查询为多个简单查询
- 示例：用户问"最近人工智能和芯片行业有什么新闻？"可以拆分为"人工智能最新动态"和"芯片行业新闻"两个查询
- 根据查询复杂度决定调用接口的次数

### 3. 数据评估与扩展
- 自动评估搜索结果是否能回答用户问题
- 如有必要，可调用其他技能或工具扩展数据
- 对搜索结果进行质量评估

### 4. 数据处理与返回
- 对搜索结果进行排序、过滤和摘要处理
- **⚠️ 重要警告：根据问财OpenAPI网关规范条件六，API原始响应必须透明传递**
- **必须遵守**：不得对API响应进行二次解析、清洗、重组或再加工
- **透明传递要求**：
  - 直接返回API原始响应JSON，不做任何包装
  - 错误响应也必须原样传递，不得替换为自定义错误信息
  - 网络层错误（超时、连接失败等）可提供技术性错误信息
- 将透明传递的响应数据返回给大模型进行处理
- 大模型负责生成用户友好的回答格式

## 接口信息

### 基础信息
- **Base URL**: `https://openapi.iwencai.com`
- **接口路径**: `/v1/comprehensive/search`
- **请求方式**: POST
- **认证方式**: API Key (Bearer Token)

### 问财OpenAPI网关规范要求

所有发往问财OpenAPI网关的请求必须遵守以下规范：

#### 1. HTTP请求头要求
所有请求必须在Header中包含以下字段：

| Header | 取值说明 |
|--------|----------|
| `X-Claw-Call-Type` | `normal`：正常请求；`retry`：失败后的重试。按实际调用场景二选一。 |
| `X-Claw-Skill-Id` | 技能标识，填写 `news-search`。 |
| `X-Claw-Skill-Version` | 当前技能版本号，填写 `1.0.0`。 |
| `X-Claw-Plugin-Id` | 插件ID，当前阶段统一填写 `none`。 |
| `X-Claw-Plugin-Version` | 插件版本，当前阶段统一填写 `none`。 |
| `X-Claw-Trace-Id` | **每次请求必须新生成**的**全局唯一**追踪ID；**长度为64个字符**（推荐64位十六进制字符串）。 |

#### 2. 认证要求
使用OAuth2.0/JWT风格认证：
```
Authorization: Bearer {IWENCAI_API_KEY}
```
其中 `IWENCAI_API_KEY` 必须从环境变量读取，禁止硬编码在代码中。

#### 3. 请求参数
```json
{
  "channels": ["news"],
  "app_id": "AIME_SKILL",
  "query": "搜索关键词"
}
```

### curl示例（脱敏）
```bash
# 生成64位十六进制Trace ID
TRACE_ID=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# 调用新闻搜索接口
curl -X POST "https://openapi.iwencai.com/v1/comprehensive/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $IWENCAI_API_KEY" \
  -H "X-Claw-Call-Type: normal" \
  -H "X-Claw-Skill-Id: news-search" \
  -H "X-Claw-Skill-Version: 1.0.0" \
  -H "X-Claw-Plugin-Id: none" \
  -H "X-Claw-Plugin-Version: none" \
  -H "X-Claw-Trace-Id: $TRACE_ID" \
  -d '{
    "channels": ["news"],
    "app_id": "AIME_SKILL",
    "query": "人工智能"
  }'
```

**Windows PowerShell示例：**
```powershell
# 生成64位十六进制Trace ID
$TRACE_ID = python -c "import secrets; print(secrets.token_hex(32))"

# 调用新闻搜索接口
$headers = @{
    "Content-Type" = "application/json"
    "Authorization" = "Bearer $env:IWENCAI_API_KEY"
    "X-Claw-Call-Type" = "normal"
    "X-Claw-Skill-Id" = "news-search"
    "X-Claw-Skill-Version" = "1.0.0"
    "X-Claw-Plugin-Id" = "none"
    "X-Claw-Plugin-Version" = "none"
    "X-Claw-Trace-Id" = $TRACE_ID
}

$body = @{
    channels = @("news")
    app_id = "AIME_SKILL"
    query = "人工智能"
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://openapi.iwencai.com/v1/comprehensive/search" -Method Post -Headers $headers -Body $body
```

## 问财OpenAPI网关核心规范（必须遵守）

### 条件六：返回结果透明传递（Non-Negotiable）

**核心原则：技能生成的代码必须透明传递API响应，不得对返回内容做任何修改、过滤、重组或再加工后再交付给调用方。**

#### 1. 禁止行为
- 不得对网关返回的 `data`、`result`、`response` 等字段进行二次解析、清洗、重组
- 不得自行添加、删除、修改返回结果的任何键值或结构
- 不得在技能生成的代码中将API原始响应包装成另一套 `result` / `output` / `data` 等结构再返回
- 不得在返回前对响应内容做任何「业务逻辑层」的处理（如字段映射、类型转换、格式化等），这些应由调用方决定如何处理

#### 2. 要求行为
- **直接透传**：对网关返回的完整HTTP响应体（Body），应在获取后**原封不动**地传递给调用方（或返回给LLM）
- **透明返回**：若使用Python等语言实现，返回值应为对API响应的直接赋值或简单的 `return response`，不做任何中间transformation
- **错误传递**：API返回的错误状态码与错误Body也应完整传递，不得替换为自定义错误信息（除非是网络层超时、连接失败等技术性错误）

#### 3. 正确实现示例
```python
# ✅ 正确：直接返回API响应
def search_news(query: str):
    response = requests.post(url, headers=headers, json=payload)
    # 直接返回API响应，不做任何处理
    return response.json()  # 或者 response.text / response.content
```

#### 4. 错误实现示例
```python
# ❌ 错误：对API响应做了二次组装
def search_news(query: str):
    resp = requests.post(url, headers=headers, json=payload)
    data = resp.json()
    result = {"code": 0, "data": data["result"], "msg": "success"}  # 禁止：自行包装
    return result
```

## 使用场景

### 何时调用本技能
1. **财经新闻搜索**: 当用户需要了解特定行业、公司或主题的最新财经新闻时
2. **政策动态查询**: 当用户需要了解最新的财经政策、法规变化时
3. **行业趋势分析**: 当用户需要了解某个行业的最新发展动态和趋势时
4. **企业信息查询**: 当用户需要了解特定上市公司或非上市公司的业务进展时
5. **市场动态跟踪**: 当用户需要了解股票市场、债券市场等金融市场的最新动态时

### 调用示例
1. 用户问："最近人工智能行业有什么新政策？"
2. 用户问："特斯拉最近的业务进展如何？"
3. 用户问："芯片行业的最新动态有哪些？"
4. 用户问："央行最近发布了什么货币政策？"

## 技能内部逻辑

### 查询处理流程
1. **接收用户查询**: 获取用户的搜索需求
2. **查询拆解**: 分析查询复杂度，决定是否需要拆分为多个子查询
3. **API调用**: 生成并执行API调用代码
4. **数据评估**: 检查返回的数据是否足够回答用户问题
5. **数据处理**: 对搜索结果进行排序、过滤和摘要
6. **结果返回**: 将处理后的结果返回给大模型

### 代码生成要求
- 生成完整的API调用代码，包括认证、请求构造、错误处理
- 处理网络异常和接口错误
- 实现重试机制
- 支持并发处理（可选）

## 数据来源标注

**重要**: 所有搜索结果均来源于同花顺问财，在回答用户问题时必须明确标注数据来源。

示例标注格式：
- "根据同花顺问财的数据..."
- "数据来源：同花顺问财财经资讯搜索"
- "同花顺问财数据显示..."

## 技术实现

### Python代码要求
- 使用Python标准库和常用库
- 代码结构清晰，模块化设计
- 包含完整的错误处理
- 支持配置文件和环境变量
- 实现日志记录功能
- 尽量少依赖第三方库
- 确保代码的可读性和可维护性

### CLI接口要求
- 提供友好的命令行接口支持
- 支持以下命令行参数：
  - `--query` 或 `-q`: 搜索关键词
  - `--output` 或 `-o`: 输出文件路径
  - `--input` 或 `-i`: 输入文件路径（批量处理）
  - `--format` 或 `-f`: 输出格式（csv, json, text）
  - `--limit` 或 `-l`: 结果数量限制
  - `--help` 或 `-h`: 显示帮助信息
- 提供详细的帮助文档和示例用法
- 支持管道操作和输入输出重定向
- 支持文件到文件处理，即CLI允许 `input-paths` 和 `output-paths`
- 数据表格保存为CSV格式
- 图片URL下载为文件
- 支持批量处理和分页查询

### 大数据处理能力
- 探索api接口的输出，考虑数据量较大的情况
- 支持文件到文件处理
- 数据表格保存为CSV格式
- 图片URL下载为文件
- 支持批量处理和分页查询

### 错误处理
- 网络异常处理
- API认证失败处理
- 请求频率限制处理
- 数据解析错误处理

### 性能优化
- 支持大数据量处理
- 实现缓存机制（可选）
- 支持并发查询（可选）
- 优化响应时间

## 注意事项

### API使用规范
1. API密钥需要从环境变量安全获取：`IWENCAI_API_KEY`
2. 注意请求频率限制，避免被限制访问
3. 请求参数中的`channels`和`app_id`为固定值，不要修改
4. `query`参数支持中文关键词搜索

### 数据使用规范
1. 引用数据时必须注明来源：同花顺问财
2. 确保数据处理的准确性和完整性
3. 遵循数据隐私和安全规范
4. 不得将数据用于商业用途或违反相关法律法规

### 技能调用规范
1. 技能描述使用中文
2. 提供清晰的调用说明
3. 支持多种查询场景
4. 确保技能稳定性和可靠性

## 技能验证

### 验收标准
1. 技能能够正确安装和运行
2. 能够成功调用财经资讯搜索接口
3. 能够处理各种查询场景
4. 支持大数据量的处理和导出
5. 代码质量高，符合Python最佳实践
6. 数据来源标注清晰准确
7. 技能描述使用中文

### 测试用例
1. 简单查询测试：搜索"人工智能"
2. 复杂查询测试：搜索"人工智能和芯片行业最新动态"
3. 错误处理测试：无效API密钥测试
4. 性能测试：大数据量查询测试
5. 格式测试：不同输出格式测试

## 更新日志

### v1.0.0 (初始版本)
- 实现基础财经资讯搜索功能
- 支持查询拆解和合并
- 实现完整错误处理机制
- 添加数据来源标注功能
- 提供详细的使用文档
