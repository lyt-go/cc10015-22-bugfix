"""可视化配置 分析看板接口：汇总指标、参数运行、配置与数据快照同事务持久化。"""
from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.schemas import ActionPayload, ActionResult, EntryPayload
from app.services.chart_config import SWITCH_STRATEGIES, ChartConfigService
from app.store import TransactionError

router = APIRouter(prefix="/api/chart_config", tags=["可视化配置"])
service = ChartConfigService()
LIST_FIELDS = ["图表编号", "图表类型", "数据来源", "横轴字段", "纵轴字段", "分组字段", "刷新间隔", "分享链接"]
STATUSES = ["草稿", "待校验", "已发布", "已停用"]


class ChartConfigUpdatePayload(BaseModel):
    """保存图表配置的载荷：values 为配置字段，strategy 为来源切换策略。"""

    values: dict[str, Any]
    strategy: str = "recompute_first"


def csv_cell(value: Any) -> str:
    text = str(value) if value is not None else ""
    if text and text[0] in "=+-@":
        text = "'" + text
    return '"' + text.replace('"', '""') + '"'


def _raise_transaction(exc: TransactionError) -> HTTPException:
    # 事务已在服务层整体回滚，这里转成 409 让前端提示并保留上一版完整快照
    return HTTPException(status_code=409, detail=str(exc))


@router.get("/summary")
def get_summary() -> dict[str, Any]:
    # 汇总卡片基于已持久化快照统计，刷新页面不再随机跳动
    return {"metrics": service.summary()}


@router.get("")
def list_results() -> dict[str, Any]:
    return {"items": service.list_results()}


@router.get("/export")
def export_entries() -> StreamingResponse:
    items = service.list_results()
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    all_keys = ["id"]
    if items:
        all_keys = list(items[0].keys())
    writer.writerow(all_keys)
    for item in items:
        writer.writerow([csv_cell(item.get(k, "")) for k in all_keys])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=chart_config.csv"})


@router.post("/run")
def run_analysis(payload: EntryPayload) -> dict[str, Any]:
    results = service.run_analysis(payload.values)
    return {"items": results}


@router.get("/archive")
def list_archive() -> dict[str, Any]:
    """归档的旧配置与旧快照，供 V022 留档核对。"""
    return {"items": service.list_archive()}


@router.get("/audit")
def list_audit() -> dict[str, Any]:
    """快照持久化与一致性操作留痕。"""
    return {"items": service.list_audit()}


@router.post("")
def create_entry(payload: EntryPayload) -> ActionResult:
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="图表配置与首版数据快照已同时保存", entry=entry)


@router.put("/{entry_id}")
def update_entry(entry_id: int, payload: ChartConfigUpdatePayload) -> ActionResult:
    """保存图表配置：配置与数据快照在同一事务提交，失败整体回滚。"""
    if payload.strategy not in SWITCH_STRATEGIES:
        raise HTTPException(status_code=400,
                            detail=f"切换策略仅支持：{'、'.join(SWITCH_STRATEGIES)}")
    try:
        entry, message = service.update_entry(entry_id, payload.values, strategy=payload.strategy)
    except TransactionError as exc:
        raise _raise_transaction(exc) from exc
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/confirm-switch")
def confirm_switch(entry_id: int) -> ActionResult:
    """freeze_first 策略下确认待切换：归档旧快照并按新来源整体重算。"""
    try:
        entry, message = service.confirm_switch(entry_id)
    except TransactionError as exc:
        raise _raise_transaction(exc) from exc
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions")
def run_action(entry_id: int, payload: ActionPayload) -> ActionResult:
    """提交校验、确认发布、停用图表：状态与快照在同一事务内流转。"""
    entry, action_message = service.run_action(entry_id, payload.action.strip())
    if entry is None:
        return ActionResult(ok=False, message=action_message)
    return ActionResult(ok=True, message=action_message, entry=entry)


@router.post("/{entry_id}/verify")
def verify_snapshot(entry_id: int) -> dict[str, Any]:
    """按页面显示核对快照与配置；残留错位时事务内整体回滚。"""
    try:
        return service.verify_snapshot(entry_id)
    except TransactionError as exc:
        raise _raise_transaction(exc) from exc


@router.get("/{entry_id}/metric-handoff")
def metric_handoff(entry_id: int) -> dict[str, Any]:
    """V022：指标定义模块读取图表快照中的指标标识并校验横纵轴统计粒度。"""
    try:
        return service.read_snapshot_for_metric(entry_id)
    except TransactionError as exc:
        raise _raise_transaction(exc) from exc


@router.get("/{entry_id}")
def get_entry(entry_id: int) -> dict:
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"图表配置 {entry_id} 不存在")
    return entry
