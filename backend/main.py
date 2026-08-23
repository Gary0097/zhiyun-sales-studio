# -*- coding: utf-8 -*-
"""Sales Studio HTTP and Agent entrypoint."""

from __future__ import annotations

import json
import sys
import sqlite3
from pathlib import Path
from typing import Any

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
PLUGIN_VERSION = "0.1.0"


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
