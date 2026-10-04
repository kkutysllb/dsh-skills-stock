#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同花顺问财 OpenAPI 统一客户端

严格遵循 Iwencai (问财) OpenAPI 网关规范：
- 每次请求携带 8 个 X-Claw-* Header
- X-Claw-Trace-Id 为每次新生成的 64 字符十六进制唯一 ID
- Authorization Bearer 仅从环境变量 IWENCAI_API_KEY 读取
- 使用 Python3 标准库，跨平台兼容

用法:
    from kk_common import IwencaiClient
    client = IwencaiClient(skill_name="hithink-market-query")
    result = client.query("贵州茅台最新价格")
"""

import json
import os
import secrets
import urllib.error
import urllib.request
from typing import Optional, Union


DEFAULT_API_URL = "https://openapi.iwencai.com/v1/query2data"
DEFAULT_TIMEOUT = 30


class APIError(Exception):
    """问财 API 错误异常类"""

    def __init__(self, message: str, status_code: int = None, response: Union[str, dict, None] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response


def generate_trace_id() -> str:
    """生成 64 字符十六进制全局唯一追踪 ID。"""
    return secrets.token_hex(32)


def build_headers(api_key: str, trace_id: str, skill_name: str,
                  skill_version: str = "1.0.0", call_type: str = "normal") -> dict:
    """构造符合问财网关规范的请求头。"""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Claw-Call-Type": call_type,
        "X-Claw-Skill-Id": skill_name,
        "X-Claw-Skill-Version": skill_version,
        "X-Claw-Plugin-Id": "none",
        "X-Claw-Plugin-Version": "none",
        "X-Claw-Trace-Id": trace_id,
    }


class IwencaiClient:
    """
    同花顺问财 OpenAPI 客户端。

    Args:
        skill_name: 技能标识，如 "hithink-market-query"
        skill_version: 技能版本号
        api_key: API 密钥，默认从环境变量 IWENCAI_API_KEY 读取
        api_url: API 端点地址
        timeout: 请求超时时间（秒）
    """

    def __init__(
        self,
        skill_name: str = "hithink-market-query",
        skill_version: str = "1.0.0",
        api_key: Optional[str] = None,
        api_url: str = DEFAULT_API_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.skill_name = skill_name
        self.skill_version = skill_version
        self.api_key = api_key or os.environ.get("IWENCAI_API_KEY", "")
        self.api_url = api_url
        self.timeout = timeout

    def _resolve_api_key(self, cli_api_key: Optional[str] = None) -> str:
        """获取 API 密钥：优先 CLI 参数，其次构造时设置的，最后环境变量。"""
        key = cli_api_key or self.api_key
        if not key:
            raise APIError(
                "API 密钥未设置。请通过参数或环境变量 IWENCAI_API_KEY 指定。\n"
                "首次使用获取指引：打开 https://www.iwencai.com/skillhub → 登录 → 点击 Skill → "
                "安装方式-Agent用户-复制您的 IWENCAI_API_KEY。"
            )
        return key

    def query(
        self,
        query: str,
        page: str = "1",
        limit: str = "10",
        api_key: Optional[str] = None,
        call_type: str = "normal",
        timeout: Optional[int] = None,
    ) -> dict:
        """
        调用问财数据查询接口。

        Args:
            query: 查询字符串
            page: 分页参数
            limit: 每页条数
            api_key: 临时覆盖 API 密钥
            call_type: 调用类型，normal 或 retry
            timeout: 请求超时时间（秒）

        Returns:
            包含 datas、code_count、chunks_info、trace_id、claw_headers 等字段的字典
        """
        api_key = self._resolve_api_key(api_key)
        api_url = self.api_url
        trace_id = generate_trace_id()
        actual_timeout = timeout if timeout is not None else self.timeout

        payload = {
            "query": query,
            "page": page,
            "limit": limit,
            "is_cache": "1",
            "expand_index": "true",
        }

        headers = build_headers(api_key, trace_id, self.skill_name, self.skill_version, call_type)
        claw_headers = {k: v for k, v in headers.items() if k.startswith("X-Claw-")}
        request = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=actual_timeout) as response:
                response_body = response.read().decode("utf-8")

                if not response_body.strip():
                    return {"text_response": "", "trace_id": trace_id, "claw_headers": claw_headers}

                try:
                    parsed = json.loads(response_body)
                    if isinstance(parsed, dict):
                        parsed["trace_id"] = trace_id
                        parsed["claw_headers"] = claw_headers
                        return parsed
                    elif isinstance(parsed, list):
                        return {"data": parsed, "trace_id": trace_id, "claw_headers": claw_headers}
                    else:
                        return {"text_response": str(parsed), "trace_id": trace_id, "claw_headers": claw_headers}
                except json.JSONDecodeError:
                    return {"text_response": response_body, "trace_id": trace_id, "claw_headers": claw_headers}

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            if error_body.strip():
                try:
                    error_json = json.loads(error_body)
                    raise APIError(f"HTTP 错误 {e.code}: {e.reason}", status_code=e.code, response=error_json)
                except json.JSONDecodeError:
                    raise APIError(f"HTTP 错误 {e.code}: {e.reason}", status_code=e.code, response=error_body)
            else:
                raise APIError(f"HTTP 错误 {e.code}: {e.reason}", status_code=e.code, response="")
        except urllib.error.URLError as e:
            raise APIError(f"网络错误: {e.reason}")

    def query_with_pagination(
        self,
        query: str,
        max_pages: int = 1,
        page_size: int = 10,
    ) -> dict:
        """
        支持翻页的查询，自动获取多页数据。

        Args:
            query: 查询字符串
            max_pages: 最大翻页数
            page_size: 每页条数

        Returns:
            合并后的查询结果
        """
        all_datas = []
        total_code_count = 0
        final_trace_id = ""
        final_claw_headers = {}

        for page_num in range(1, max_pages + 1):
            result = self.query(query=query, page=str(page_num), limit=str(page_size))
            datas = result.get("datas", [])
            all_datas.extend(datas)
            total_code_count = int(result.get("code_count", 0))
            final_trace_id = result.get("trace_id", "")
            final_claw_headers = result.get("claw_headers", {})

            if page_num * page_size >= total_code_count:
                break

        return {
            "success": True,
            "query": query,
            "code_count": total_code_count,
            "returned_count": len(all_datas),
            "pages_fetched": min(max_pages, (total_code_count + page_size - 1) // page_size),
            "datas": all_datas,
            "trace_id": final_trace_id,
            "claw_headers": final_claw_headers,
        }

    def format_output(self, result: dict, query: str, page: str, limit: str) -> dict:
        """
        将原始 API 响应格式化为标准输出结构。
        与原 cli.py 中的 main() 逻辑兼容。
        """
        if "text_response" in result:
            return result

        if "datas" not in result:
            # 网关层错误，直接透传
            return result

        datas = result["datas"]
        code_count = int(result.get("code_count", 0))
        current_page = int(page)
        current_limit = int(limit)
        has_more = current_page * current_limit < code_count

        output = {
            "success": True,
            "query": query,
            "code_count": code_count,
            "returned_count": len(datas),
            "page": page,
            "limit": limit,
            "has_more": has_more,
            "datas": datas,
        }

        if has_more:
            output["pagination_tip"] = (
                f"共查到 {code_count} 条数据，当前返回第 {page} 页的 {len(datas)} 条。"
                f"如需更多数据，请使用 --page 参数翻页。"
            )

        if not datas:
            output["empty_data_tip"] = (
                "未查询到符合条件的数据。建议放宽或简化查询条件后重试。"
                "如仍无数据，可引导用户访问同花顺问财: https://www.iwencai.com/unifiedwap/chat"
            )

        return output
