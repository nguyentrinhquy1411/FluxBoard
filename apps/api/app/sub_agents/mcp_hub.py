from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.schemas.validation import JsonRpcError, JsonRpcRequest, JsonRpcResponse

Handler = Callable[[dict[str, Any]], Awaitable[Any]]


class MCPTransport(ABC):
    @abstractmethod
    async def send(self, request: JsonRpcRequest) -> JsonRpcResponse:
        raise NotImplementedError


class StdioTransport(MCPTransport):
    def __init__(self, handler: Handler) -> None:
        self.handler = handler

    async def send(self, request: JsonRpcRequest) -> JsonRpcResponse:
        try:
            result = await self.handler(request.params)
            return JsonRpcResponse(result=result, id=request.id)
        except Exception as exc:
            return JsonRpcResponse(
                error=JsonRpcError(code=-32000, message=str(exc)),
                id=request.id,
            )


class HttpSseTransport(MCPTransport):
    def __init__(self, endpoint: str, client: httpx.AsyncClient | None = None) -> None:
        self.endpoint = endpoint
        self.client = client or httpx.AsyncClient(timeout=30)

    async def send(self, request: JsonRpcRequest) -> JsonRpcResponse:
        response = await self.client.post(
            self.endpoint,
            content=json.dumps(request.model_dump(mode="json")),
            headers={"content-type": "application/json"},
        )
        response.raise_for_status()
        return JsonRpcResponse.model_validate(response.json())


class MCPHub:
    def __init__(self, transport: MCPTransport) -> None:
        self.transport = transport

    async def call_tool(self, method: str, params: dict[str, Any]) -> JsonRpcResponse:
        return await self.transport.send(JsonRpcRequest(method=method, params=params))
