"""场地租用接口：维护拍摄场地，覆盖签约场地、确认进场、办理退场等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.location import LocationService

router = APIRouter(prefix="/api/location", tags=["场地租用"])

service = LocationService()

LIST_FIELDS = ["场地编号", "场地名称", "场地类型", "所属区域", "可租时段", "场地费用", "对接联系人", "租用状态"]
STATUSES = ["待洽谈", "已签约", "使用中", "已退场"]


def scope(
    场地编号: str | None = Query(default=None, description="按场地编号检索"),
    场地名称: str | None = Query(default=None, description="按场地名称检索"),
    场地类型: str | None = Query(default=None, description="按场地类型检索"),
    所属区域: str | None = Query(default=None, description="按所属区域检索"),
    status: str | None = Query(default=None, description="待洽谈、已签约、使用中、已退场"),
) -> dict[str, str]:
    """汇总当前筛选条件；列表、详情、导出共用同一范围。"""
    return {
        **{field: value for field, value in (
            ("场地编号", 场地编号),
            ("场地名称", 场地名称),
            ("场地类型", 场地类型),
            ("所属区域", 所属区域),
        ) if value and value.strip()},
        **({"status": status} if status and status.strip() else {}),
    }


# /export 必须在 /{entry_id} 之前注册，避免被动态路径吞掉
@router.get("/export")
def export_entries(filters: dict[str, str] = Depends(scope)) -> dict[str, Any]:
    """导出场地租用清单：与列表页保持同一筛选范围，只导出命中的记录。"""
    items, total = service.list_entries(filters=filters, page=1, size=10000)
    return {"module": "location", "total": total, "filters": filters, "items": items}


@router.get("", response_model=PageResult[dict])
def list_entries(
    filters: dict[str, str] = Depends(scope),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1),
) -> PageResult[dict]:
    """按场地编号、名称、类型、所属区域与状态过滤场地租用列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(filters=filters, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int, filters: dict[str, str] = Depends(scope)) -> dict:
    """读取单条拍摄场地明细；不在当前筛选范围或不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id, filters)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"拍摄场地 {entry_id} 不在当前筛选范围内或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条拍摄场地，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="拍摄场地已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条拍摄场地执行签约场地、确认进场、办理退场；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
