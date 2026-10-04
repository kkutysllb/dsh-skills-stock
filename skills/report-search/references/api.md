# 财经报告搜索接口文档

## 接口概述

- **接口名称**: 财经报告搜索接口
- **接口说明**: 搜索财经领域的报告文章，返回相关的文章信息列表
- **接口版本**: v1

## 基础信息

- **Base URL**: `https://openapi.iwencai.com`
- **接口路径**: `/v1/comprehensive/search`
- **请求方式**: POST
- **Content-Type**: `application/json`
- **API Key 环境变量**: `IWENCAI_API_KEY`

## 请求说明

### 请求头

```
Content-Type: application/json
```

### 请求参数

请求体为 JSON 格式，包含以下参数：

#### 固定参数

| 参数名 | 类型 | 说明 | 值 |
|--------|------|------|-----|
| channels | LIST | 搜索渠道类型 | `["report"]` |
| app_id | STRING | 应用ID | `AIME_SKILL` |

#### 可变参数

| 参数名 | 类型 | 说明 | 必填 |
|--------|------|------|------|
| query | STRING | 用户问句，即搜索关键词 | 是 |

### 请求示例

```json
{
  "channels": ["report"],
  "app_id": "AIME_SKILL",
  "query": "人工智能行业研究报告"
}
```

## 响应说明

### 响应格式

响应为 JSON 格式，主要包含 `data` 字段，该字段是一个文章信息列表。

### 响应结构

```json
{
  "data": [
    {
      "title": "文章标题",
      "summary": "文章摘要",
      "url": "文章网址",
      "publish_date": "文章发布时间"
    }
  ]
}
```

### 字段说明

#### data 字段

| 字段名 | 类型 | 说明 | 格式 |
|--------|------|------|------|
| title | STRING | 文章标题 | - |
| summary | STRING | 文章摘要 | - |
| url | STRING | 文章网址 | URL格式 |
| publish_date | STRING | 文章发布时间 | `YYYY-MM-DD HH:MM:SS` |

### 响应示例

```json
{
  "data": [
    {
      "title": "2024年人工智能行业发展趋势报告",
      "summary": "本报告分析了2024年人工智能行业的发展趋势，包括技术突破、应用场景、市场规模等方面的内容...",
      "url": "https://example.com/reports/ai-trends-2024",
      "publish_date": "2024-01-15 09:30:00"
    },
    {
      "title": "金融科技AI应用研究报告",
      "summary": "报告详细介绍了人工智能在金融科技领域的应用现状和未来发展方向...",
      "url": "https://example.com/reports/fintech-ai-applications",
      "publish_date": "2024-01-14 14:20:00"
    },
    {
      "title": "智能制造AI解决方案分析",
      "summary": "本报告分析了人工智能在智能制造领域的解决方案和应用案例...",
      "url": "https://example.com/reports/smart-manufacturing-ai",
      "publish_date": "2024-01-13 11:15"
    }
  ]
}
```

## 使用说明

### 环境变量设置

在使用此接口前，需要设置 API Key 环境变量：

```bash
export IWENCAI_API_KEY="your_api_key_here"
```

### 调用示例（Python）

```python
import os
import requests
import json

# API配置
BASE_URL = "https://openapi.iwencai.com"
ENDPOINT = "/v1/comprehensive/search"
API_KEY = os.getenv("IWENCAI_API_KEY")

# 请求头
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# 请求体
payload = {
    "channels": ["report"],
    "app_id": "AIME_SKILL",
    "query": "人工智能行业研究报告"
}

# 发送请求
response = requests.post(
    f"{BASE_URL}{ENDPOINT}",
    headers=headers,
    json=payload
)

# 处理响应
if response.status_code == 200:
    data = response.json()
    articles = data.get("data", [])
    for article in articles:
        print(f"标题: {article['title']}")
        print(f"摘要: {article['summary']}")
        print(f"链接: {article['url']}")
        print(f"发布时间: {article['publish_date']}")
        print("---")
else:
    print(f"请求失败: {response.status_code}")
    print(response.text)
```

### 调用示例（JavaScript/Node.js）

```javascript
const axios = require('axios');

// API配置
const BASE_URL = 'https://openapi.iwencai.com';
const ENDPOINT = '/v1/comprehensive/search';
const API_KEY = process.env.IWENCAI_API_KEY;

// 请求头
const headers = {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${API_KEY}`
};

// 请求体
const payload = {
  channels: ['report'],
  app_id: 'AIME_SKILL',
  query: '人工智能行业研究报告'
};

// 发送请求
axios.post(`${BASE_URL}${ENDPOINT}`, payload, { headers })
  .then(response => {
    const articles = response.data.data || [];
    articles.forEach(article => {
      console.log(`标题: ${article.title}`);
      console.log(`摘要: ${article.summary}`);
      console.log(`链接: ${article.url}`);
      console.log(`发布时间: ${article.publish_date}`);
      console.log('---');
    });
  })
  .catch(error => {
    console.error('请求失败:', error.response?.status || error.message);
    console.error('错误信息:', error.response?.data || error.message);
  });
```

## 注意事项

1. **API Key**: 需要申请有效的 API Key 并设置为 `IWENCAI_API_KEY` 环境变量
2. **参数固定值**: `channels` 参数必须为 `["report"]`，`app_id` 参数必须为 `AIME_SKILL`
3. **搜索关键词**: `query` 参数支持中文关键词，建议使用具体的搜索词以获得更准确的结果
4. **响应数据**: 返回的文章数据按发布时间倒序排列
5. **错误处理**: 如果请求失败，请检查网络连接、API Key 和请求参数
6. **数据来源**: 所有数据均来源于同花顺问财财经资讯搜索接口，使用时请注明数据来源

## 常见问题

### Q: 如何获取 API Key？
A: 需要向接口提供方申请有效的 API Key。

### Q: 搜索不到结果怎么办？
A: 可以尝试调整搜索关键词，使用更具体或更通用的词汇。

### Q: 返回的文章数量有限制吗？
A: 接口文档未明确说明返回数量限制，实际返回数量可能受搜索条件和系统限制影响。

### Q: publish_date 字段的时区是什么？
A: 文档未明确说明时区，通常为北京时间（UTC+8）。

---

**文档版本**: 1.0  
**最后更新**: 基于 api_prompt.txt 生成  
**接口状态**: 正常