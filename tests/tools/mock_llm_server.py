"""轻量 Mock LLM Server，模拟 OpenAI-compatible chat/completions API。

用于 page_agent E2E 测试，返回固定的 page-agent AgentOutput tool call，
让 execute 流程能完整走通而不依赖真实 LLM。
"""

from __future__ import annotations

import json

from aiohttp import web


def _build_done_response(request_id: str = "mock-1") -> dict:
    """构造一个让 page-agent 立即完成的 AgentOutput tool call 响应。"""
    return {
        "id": request_id,
        "object": "chat.completion",
        "model": "mock-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_mock_1",
                            "type": "function",
                            "function": {
                                "name": "AgentOutput",
                                "arguments": json.dumps({
                                    "thinking": "Mock: completing immediately",
                                    "action": {
                                        "done": {
                                            "text": "Mock task completed",
                                            "success": True,
                                        }
                                    },
                                }),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
        },
    }


async def _handle_completions(request: web.Request) -> web.Response:
    """处理 POST /chat/completions 请求。"""
    body = await request.json()
    request_id = body.get("model", "mock") + "-resp"
    return web.json_response(_build_done_response(request_id))


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/chat/completions", _handle_completions)
    return app
