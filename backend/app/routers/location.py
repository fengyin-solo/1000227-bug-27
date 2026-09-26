"""场地租用接口：维护拍摄场地，覆盖签约场地、确认进场、办理退场等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.location import LocationService

router = APIRouter(prefix="/api/location", tags=["场地租用"])

service = LocationService()

LIST_FIELDS = ["场地编号", "场地名称", "场地类型", "所属区域", "可租时段", "场地费用", "对接联系人", "租用状态"]
STATUSES = ["待洽谈", "已签约", "使用中", "已退场"]


def _scope_filters(code: str | None, name: str | None, category: str | None) -> dict[str, str]:
    """把查询参数整理成服务层认识的筛选条件，空白条件直接丢弃。"""
    raw = {"场地编号": code, "场地名称": name, "场地类型": category}
    return {field: value.strip() for field, value in raw.items() if value and value.strip()}


@router.get("", response_model=PageResult[dict])
def list_entries(
    code: str | None = Query(default=None, alias="场地编号", description="按场地编号模糊检索"),
    name: str | None = Query(default=None, alias="场地名称", description="按场地名称模糊检索"),
    category: str | None = Query(default=None, alias="场地类型", description="按场地类型模糊检索"),
    status: str | None = Query(default=None, description="待洽谈、已签约、使用中、已退场"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按场地编号、场地名称、场地类型与状态过滤场地租用列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    filters = _scope_filters(code, name, category)
    items, total = service.list_entries(filters=filters, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries(
    code: str | None = Query(default=None, alias="场地编号", description="按场地编号模糊检索"),
    name: str | None = Query(default=None, alias="场地名称", description="按场地名称模糊检索"),
    category: str | None = Query(default=None, alias="场地类型", description="按场地类型模糊检索"),
    status: str | None = Query(default=None, description="待洽谈、已签约、使用中、已退场"),
) -> dict[str, Any]:
    """导出场地租用清单：与列表页共用同一筛选范围，并在结果里回显生效的筛选条件。"""
    filters = _scope_filters(code, name, category)
    items, total = service.export_entries(filters=filters, status=status)
    scope: dict[str, Any] = {"filters": filters, "status": status}
    return {"module": "location", "total": total, "scope": scope, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条拍摄场地明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"拍摄场地 {entry_id} 不存在或已归档")
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
