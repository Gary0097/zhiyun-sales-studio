# -*- coding: utf-8 -*-
"""Sales Studio HTTP and Agent entrypoint."""

from __future__ import annotations

import json
import sys
import sqlite3
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from qwenpaw.plugins.api import PluginApi

try:
    from .sales_engine import analyze_performance, analyze_sales_bi, segment_customers
    from .sales_workflow import SalesWorkflowStore
except ImportError:
    backend_dir = str(Path(__file__).resolve().parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from sales_engine import analyze_performance, analyze_sales_bi, segment_customers
    from sales_workflow import SalesWorkflowStore

router = APIRouter()
import httpx
from uuid import uuid4
from fastapi.responses import StreamingResponse
PLUGIN_VERSION = "0.2.0"


def _store() -> SalesWorkflowStore:
    try:
        return SalesWorkflowStore()
    except (OSError, sqlite3.Error) as exc:
        raise HTTPException(status_code=503, detail=f"销售持久化依赖不可用：{exc}") from exc


class OrdersRequest(BaseModel):
    orders: list[dict[str, Any]] = Field(max_length=100000)


class CustomersRequest(BaseModel):
    customers: list[dict[str, Any]] = Field(max_length=100000)


class PerformanceRequest(BaseModel):
    records: list[dict[str, Any]] = Field(max_length=100000)


class ArtifactReviewRequest(BaseModel):
    action: str
    reviewer: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=2000)


@router.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "available", "version": PLUGIN_VERSION}


@router.post("/bi/analyze")
async def bi_analyze(request: OrdersRequest) -> dict[str, Any]:
    try:
        return analyze_sales_bi(request.orders)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/customers/segment")
async def customers_segment(request: CustomersRequest) -> dict[str, Any]:
    try:
        return segment_customers(request.customers)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/performance/analyze")
async def performance_analyze(request: PerformanceRequest) -> dict[str, Any]:
    try:
        return analyze_performance(request.records)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/artifacts/bi")
async def create_bi_artifact(request: OrdersRequest) -> dict[str, Any]:
    try:
        payload = analyze_sales_bi(request.orders)
        return _store().create_artifact("bi", "销售BI分析", payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"销售持久化依赖不可用：{exc}") from exc


@router.post("/artifacts/customers")
async def create_customers_artifact(request: CustomersRequest) -> dict[str, Any]:
    try:
        payload = segment_customers(request.customers)
        return _store().create_artifact("customers", "客户价值分层", payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"销售持久化依赖不可用：{exc}") from exc


@router.post("/artifacts/performance")
async def create_performance_artifact(request: PerformanceRequest) -> dict[str, Any]:
    try:
        payload = analyze_performance(request.records)
        return _store().create_artifact("performance", "销售业绩统计", payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"销售持久化依赖不可用：{exc}") from exc


@router.get("/artifacts")
async def list_artifacts(kind: str | None = None, limit: int = 100) -> dict[str, Any]:
    try:
        return _store().list_artifacts(kind, limit)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"销售持久化依赖不可用：{exc}") from exc


@router.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str) -> dict[str, Any]:
    try:
        return _store().get_artifact(artifact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="销售工件不存在") from exc


@router.post("/artifacts/{artifact_id}/reviews")
async def review_artifact(artifact_id: str, request: ArtifactReviewRequest) -> dict[str, Any]:
    try:
        return _store().review_artifact(artifact_id, request.action, request.reviewer, request.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="销售工件不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/artifacts/{artifact_id}/export")
async def export_artifact(artifact_id: str) -> Response:
    try:
        content, media_type = _store().export_artifact(artifact_id)
        return Response(content=content, media_type=media_type,
                        headers={"Content-Disposition": 'attachment; filename="sales-artifact.json"'})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="销售工件不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def run_and_review_sales_bi(orders: list[dict[str, Any]]) -> dict[str, Any]:
    """Run a sales BI aggregation over real orders and persist a reviewable artifact."""
    payload = analyze_sales_bi(orders)
    return _store().create_artifact("bi", "销售BI分析", payload)


def segment_review_customers(customers: list[dict[str, Any]]) -> dict[str, Any]:
    """Segment real customers with RFM scoring and persist a reviewable artifact."""
    payload = segment_customers(customers)
    return _store().create_artifact("customers", "客户价值分层", payload)


def review_sales_performance(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Attribute real sales results to people, compare to targets and persist a reviewable artifact."""
    payload = analyze_performance(records)
    return _store().create_artifact("performance", "销售业绩统计", payload)

# ==== 默认智能体接入（AgentDock / Skill 问数） ====
CONSOLE_CHAT_URL = "http://127.0.0.1:8088/api/console/chat"
CHAT_TIMEOUT_SECONDS = 300
DEFAULT_AGENT_ID = "customer_followup"

APP_CONTEXT = (
"你是「智云 AI OS」销售协同中心的智能体助手。你可以调用 `run_and_review_sales_bi`、`segment_review_customers`、`review_sales_performance` 等工具，基于真实销售数据回答销售 BI、客户分层和业绩复盘问题。当用户询问销售分析、客户分层或业绩时，请先调用对应工具再给出结论；不要凭空编造数据。"
)


class AgentChatRequest(BaseModel):
    """Client payload for the streaming in-app agent chat."""

    text: str = Field(min_length=1, max_length=4000, description="User message")
    session_id: str | None = Field(default=None, description="Persistent conversation id")
    user_id: str | None = Field(default="default", description="Calling user id")
    app_id: str | None = Field(default="zhiyun-sales-studio")
    context: str | None = Field(default=None, description="Optional system context")
    history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Prior turns [{role, text}] for multi-turn context",
    )


def _build_input(body: AgentChatRequest) -> list[dict[str, Any]]:
    """Build the console ``input`` message list from the dock payload."""
    context = body.context or APP_CONTEXT
    input_messages: list[dict[str, Any]] = []
    if context:
        input_messages.append(
            {"role": "system", "content": [{"type": "text", "text": context}]}
        )
    for turn in body.history:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role")
        text = turn.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        mapped_role = "assistant" if role in ("bot", "assistant") else "user"
        input_messages.append(
            {"role": mapped_role, "content": [{"type": "text", "text": text}]}
        )
    input_messages.append(
        {"role": "user", "content": [{"type": "text", "text": body.text}]}
    )
    return input_messages


@router.post("/agent/chat")
async def agent_chat(body: AgentChatRequest) -> StreamingResponse:
    """Proxy a user message to the real console chat and stream its SSE reply."""
    session_id = body.session_id or f"zhiyun-sales-studio-{uuid4().hex}"
    user_id = body.user_id or "default"

    payload = {
        "input": _build_input(body),
        "session_id": session_id,
        "user_id": user_id,
        "stream": True,
        "metadata": {
            "app_id": body.app_id or "zhiyun-sales-studio",
            "source_kind": "agent_dock",
            "data_mode": "real",
        },
    }

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async with httpx.AsyncClient(timeout=CHAT_TIMEOUT_SECONDS) as client:
                async with client.stream(
                    "POST",
                    CONSOLE_CHAT_URL,
                    json=payload,
                    headers={"X-Agent-Id": DEFAULT_AGENT_ID},
                ) as response:
                    if response.status_code != 200:
                        err_body = await response.aread()
                        text = err_body.decode("utf-8", errors="replace")
                        yield f"data: {json.dumps({'error': text})}\n\n"
                        return
                    async for line in response.aiter_lines():
                        if line == "":
                            yield "\n"
                        else:
                            yield line + "\n"
        except httpx.TimeoutException:
            yield f"data: {json.dumps({'error': '智能体响应超时，请稍后重试'})}\n\n"
        except Exception as exc:  # pragma: no cover - defensive
            yield f"data: {json.dumps({'error': f'调用智能体失败: {exc}'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )



class SalesStudioPlugin:
    def register(self, api: PluginApi) -> None:
        api.register_http_router(router, prefix="/zhiyun-sales-studio", tags=["zhiyun-sales-studio"])
        api.register_tool(
            tool_name="run_and_review_sales_bi",
            tool_func=run_and_review_sales_bi,
            description="对真实销售订单做营收/单量/客单价、月度趋势、品类与区域结构、Top产品与异常预警汇总并生成可审阅工件。",
            icon="📊",
            tool_type="internal",
        )
        api.register_tool(
            tool_name="segment_review_customers",
            tool_func=segment_review_customers,
            description="按近度、频次、金额对真实客户做RFM评分，划分VIP/高价值/普通/待唤醒并输出流失风险与建议，等待具名审阅。",
            icon="👥",
            tool_type="internal",
        )
        api.register_tool(
            tool_name="review_sales_performance",
            tool_func=review_sales_performance,
            description="对真实销售结果按人员归属统计营收、单量、目标达成率与排名，生成可审阅业绩工件。",
            icon="🏆",
            tool_type="internal",
        )


plugin = SalesStudioPlugin()