"""指标定义业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.services.chart_config import ChartConfigService
from app.store import TransactionError, store

MODULE = "metric_def"
LIST_FIELDS = ["指标编号", "指标名称", "计算公式", "统计粒度", "时间窗口", "基准取值", "精度位数", "口径版本"]
REQUIRED_FIELDS = ["指标编号", "指标名称", "计算公式"]
STATUS_ORDER = ["草稿", "待校验", "已生效", "已废弃"]
ACTION_RULES = {"提交校验": "待校验", "标记生效": "已生效", "标记废弃": "已废弃"}
NEGATIVE_ACTIONS = []


class MetricDefService:
    def list_entries(
        self,
        *,
        filters: dict[str, str] | None = None,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        for field, expected in (filters or {}).items():
            rows = [row for row in rows if expected.casefold() in str(row.get(field, "")).casefold()]
        if keyword:
            rows = [row for row in rows if keyword.casefold() in str(row.get("指标编号", "")).casefold()]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = (page - 1) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in LIST_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"指标定义 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于指标定义可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"指标定义已{action}"

    def read_chart_snapshot(self, chart_id: int) -> dict[str, Any]:
        """V022 跨模块联动：读取图表数据快照，校验指标标识与横纵轴统计粒度。

        指标定义模块顺着调用链拿到可视化配置侧持久化的同一份快照，核对其中的
        指标标识是否在指标定义表内登记，并比对指标口径的统计粒度与轴字段粒度。
        """
        handoff = ChartConfigService().read_snapshot_for_metric(chart_id)
        metric_code = str(handoff.get("指标标识") or "")
        metric_row = next(
            (row for row in store.rows(MODULE) if str(row.get("指标编号") or "") == metric_code),
            None,
        )
        if metric_row is None:
            raise TransactionError(f"图表快照中的指标标识 {metric_code or '(空)'} 未在指标定义模块登记")
        defined_grain = str(metric_row.get("统计粒度") or "")
        axis_grains = {str(handoff.get("横轴统计粒度") or ""), str(handoff.get("纵轴统计粒度") or "")}
        grain_matched = defined_grain in axis_grains or any(
            defined_grain and defined_grain in grain for grain in axis_grains
        )
        return {
            "ok": bool(grain_matched),
            "图表id": chart_id,
            "指标标识": metric_code,
            "指标名称": metric_row.get("指标名称"),
            "指标定义统计粒度": defined_grain,
            "横轴字段": handoff.get("横轴字段"),
            "纵轴字段": handoff.get("纵轴字段"),
            "横轴统计粒度": handoff.get("横轴统计粒度"),
            "纵轴统计粒度": handoff.get("纵轴统计粒度"),
            "粒度校验通过": grain_matched,
            "快照版本": handoff.get("快照版本"),
            "留档版本": "V022",
            "message": "统计粒度核对通过" if grain_matched else (
                f"统计粒度不一致：指标定义为{defined_grain}，快照轴粒度为{'/'.join(sorted(g for g in axis_grains if g))}"
            ),
        }
