"""场地租用业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "location"
REQUIRED_FIELDS = ["场地编号", "场地名称", "场地类型"]
FILTER_FIELDS = ["场地编号", "场地名称", "场地类型"]
STATUS_ORDER = ["待洽谈", "已签约", "使用中", "已退场"]
ACTION_RULES = {"签约场地": "已签约", "确认进场": "使用中", "办理退场": "已退场"}
NEGATIVE_ACTIONS = []


def _scoped_rows(
    filters: dict[str, str] | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """列表、分页、导出共用同一份筛选口径，保证各接口看到的是同一范围。"""
    rows = store.rows(MODULE)
    for field, value in (filters or {}).items():
        if field not in FILTER_FIELDS:
            continue
        needle = str(value or "").strip()
        if needle:
            rows = [row for row in rows if needle in str(row.get(field, ""))]
    if status:
        rows = [row for row in rows if row.get("status") == status]
    return rows


class LocationService:
    def list_entries(
        self,
        *,
        filters: dict[str, str] | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = _scoped_rows(filters, status)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def export_entries(
        self,
        *,
        filters: dict[str, str] | None = None,
        status: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = _scoped_rows(filters, status)
        return rows, len(rows)

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"拍摄场地 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于场地租用可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"拍摄场地已{action}"
