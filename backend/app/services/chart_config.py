"""可视化配置 分析看板服务。

图表配置与「图表数据快照」在同一笔事务里持久化：

- 指标值不再每次读取临时 ``random`` 生成，而是按图表编号 + 数据来源 + 横纵轴字段
  派生稳定随机种子，落一份可复用的数据快照，刷新页面 / 返回详情 / 重新打开都拿到
  同一组值；
- 保存（登记、切换数据来源、状态动作）统一走 :class:`app.store.Store.transaction`，
  配置与快照要么一起提交，要么整体回滚，刷新中断时沿用上一版完整快照，不会出现
  配置已更新而图表显示空值；
- 切换数据来源支持两种版本冲突处理策略（V022 留档）：
  ``freeze_first`` 先冻结旧来源完整快照并标记待切换，
  ``recompute_first`` 先切新来源再整体重算快照并归档旧配置。
"""
from __future__ import annotations

import copy
import hashlib
import random
import time
from typing import Any

from app.store import TransactionError, store

MODULE = "chart_config"
ARCHIVE_MODULE = "chart_snapshot_archive"
AUDIT_MODULE = "chart_snapshot_audit"
LIST_FIELDS = ["图表编号", "图表类型", "数据来源", "横轴字段", "纵轴字段", "分组字段", "刷新间隔", "分享链接"]
REQUIRED_FIELDS = ["图表编号", "图表类型", "数据来源"]
STATUS_ORDER = ["草稿", "待校验", "已发布", "已停用"]
ACTION_RULES = {"提交校验": "待校验", "确认发布": "已发布", "停用图表": "已停用"}
NEGATIVE_ACTIONS = ["停用图表"]
# 切换数据来源时的两种版本冲突处理策略
SWITCH_STRATEGIES = ("freeze_first", "recompute_first")
# 横纵轴字段允许声明的统计粒度，供指标定义（V022）模块核对
AXIS_GRANULARITIES = ("按日", "按周", "按月", "按季", "按年")
SNAPSHOT_KEY = "数据快照"
PENDING_SOURCE_KEY = "待切换数据来源"
SWITCH_STRATEGY_KEY = "切换策略"

# 指标标识 -> 统计粒度，快照里的指标标识与指标定义模块共用同一套口径
METRIC_GRANULARITY: dict[str, str] = {
    "METR-0001": "按日",
    "METR-0002": "按周",
    "METR-0003": "按月",
}


def _stable_seed(*parts: Any) -> int:
    """用业务主键拼稳定种子，避免 Python 内置 hash 的进程随机化。"""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _axis_granularity(field: Any) -> str:
    """从轴字段声明里解析统计粒度，未显式声明时按字段名兜底推断。"""
    text = str(field or "")
    for gran in AXIS_GRANULARITIES:
        if gran in text:
            return gran
    if any(token in text for token in ("日", "day", "date")):
        return "按日"
    if any(token in text for token in ("周", "week")):
        return "按周"
    if any(token in text for token in ("月", "month")):
        return "按月"
    return "按日"


class ChartConfigService:
    # ------------------------------------------------------------------ 读取
    def list_results(self) -> list[dict[str, Any]]:
        """列表读取：直接合并已持久化的同一份快照，绝不再临时造随机指标。"""
        results: list[dict[str, Any]] = []
        for row in store.rows(MODULE):
            results.append(self._entry_with_snapshot(row))
        return results

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        if row is None:
            return None
        return self._entry_with_snapshot(row)

    def _entry_with_snapshot(self, row: dict[str, Any]) -> dict[str, Any]:
        """保证每条配置都挂着与当前数据来源一致的完整快照。"""
        entry = dict(row)
        snapshot = entry.get(SNAPSHOT_KEY)
        if not isinstance(snapshot, dict) or not snapshot.get("points"):
            # 历史数据（如种子行）首次被读取时补建快照，并按当前来源持久化
            snapshot = self._build_snapshot(entry)
            row[SNAPSHOT_KEY] = snapshot
            store.bump_version(MODULE)
        entry[SNAPSHOT_KEY] = copy_snapshot(snapshot)
        return entry

    # ------------------------------------------------------------------ 快照
    def _build_snapshot(self, entry: dict[str, Any]) -> dict[str, Any]:
        """按当前数据来源与坐标字段整体重算一份完整快照。

        种子只取业务主键（图表编号/数据来源/横纵轴/分组），同一配置重复计算得到
        同一组指标值，不同来源或不同坐标字段得到不同快照，天然避免版本错位。
        """
        source = str(entry.get("数据来源") or "")
        x_field = str(entry.get("横轴字段") or "")
        y_field = str(entry.get("纵轴字段") or "")
        group_field = str(entry.get("分组字段") or "")
        metric_code = str(entry.get("指标标识") or entry.get("图表编号") or "")
        rng = random.Random(_stable_seed(entry.get("图表编号"), source, x_field, y_field, group_field))
        points: list[dict[str, Any]] = []
        baseline = round(rng.uniform(0.60, 0.92), 3)
        for index in range(6):
            value = round(rng.uniform(0.62, 1.02), 3)
            points.append({
                "id": index + 1,
                "分组": group_field or f"分组{(index % 3) + 1}",
                "横轴取值": f"{x_field or '维度'}-{index + 1}",
                "指标值": value,
                "对比基准": baseline,
                "差异": round(value - baseline, 3),
            })
        return {
            "指标标识": metric_code,
            "数据来源": source,
            "横轴字段": x_field,
            "纵轴字段": y_field,
            "分组字段": group_field,
            "横轴统计粒度": _axis_granularity(x_field),
            "纵轴统计粒度": _axis_granularity(y_field),
            "快照版本": int(entry.get("快照版本", 0)) + 1,
            "生成时间": time.time(),
            "points": points,
        }

    def run_analysis(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """运行分析同样按入参派生稳定种子，重复运行得到可复现的一组指标。"""
        count = int(params.get("样本范围", params.get("并行数量", "6")) or "6")
        rng = random.Random(_stable_seed(
            params.get("图表编号", "run"),
            params.get("数据来源", ""),
            params.get("横轴字段", ""),
            params.get("纵轴字段", ""),
        ))
        results: list[dict[str, Any]] = []
        baseline = round(rng.uniform(0.60, 0.92), 3)
        for i in range(count):
            value = round(rng.uniform(0.62, 1.02), 3)
            results.append({
                "id": i + 1,
                "分组": f"分组{(i % 3) + 1}",
                "指标值": value,
                "对比基准": baseline,
                "差异": round(value - baseline, 3),
            })
        return results

    def summary(self) -> list[dict[str, Any]]:
        """汇总卡片基于已持久化快照统计，不再每次请求随机跳动。"""
        rows = store.rows(MODULE)
        source_count = len({str(r.get("数据来源") or "") for r in rows}) or 0
        latest_values: list[float] = []
        abnormal = 0
        for row in rows:
            snapshot = row.get(SNAPSHOT_KEY)
            if not isinstance(snapshot, dict) or not snapshot.get("points"):
                snapshot = self._build_snapshot(row)
                row[SNAPSHOT_KEY] = snapshot
            points = snapshot.get("points") or []
            if points:
                latest_values.append(float(points[-1].get("指标值", 0)))
            abnormal += sum(1 for p in points if float(p.get("差异", 0)) < 0)
        latest = round(sum(latest_values) / len(latest_values), 3) if latest_values else 0
        return [
            {"label": "覆盖数据源", "value": source_count, "trend": 0},
            {"label": "最新指标值", "value": latest, "trend": 0},
            {"label": "异常记录", "value": abnormal, "trend": 0},
        ]

    # ------------------------------------------------------------------ 登记
    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [f for f in REQUIRED_FIELDS if not str(values.get(f) or "").strip()]
        if missing:
            return None, missing
        with store.transaction():
            entry: dict[str, Any] = {"id": store.next_id(MODULE)}
            for field in LIST_FIELDS:
                entry[field] = values.get(field, "")
            entry["指标标识"] = str(values.get("指标标识") or values.get("图表编号") or "")
            entry["status"] = STATUS_ORDER[0]
            entry["pending"] = True
            entry["abnormal"] = False
            entry["快照版本"] = 0
            entry["created_at"] = time.time()
            # 配置与首版快照在同一事务写入
            entry[SNAPSHOT_KEY] = self._build_snapshot(entry)
            store.rows(MODULE).append(entry)
            store.bump_version(MODULE)
            self._audit(entry["id"], "create", entry[SNAPSHOT_KEY], message="登记图表配置并写入首版数据快照")
            return self._entry_with_snapshot(entry), []

    # ---------------------------------------------------------- 切换数据来源
    def update_entry(
        self,
        entry_id: int,
        values: dict[str, Any],
        *,
        strategy: str = "recompute_first",
    ) -> tuple[dict[str, Any] | None, str]:
        """保存图表配置：配置与快照在同一事务提交，失败整体回滚。

        当数据来源发生变化（版本冲突场景）时按策略处理：

        - ``freeze_first``：冻结旧来源完整快照并标记待切换，页面仍显示旧来源
          完整快照，待 :meth:`confirm_switch` 确认后才切到新来源重算；
        - ``recompute_first``：先切到新来源再整体重算快照，旧配置与旧快照归档。
        """
        if strategy not in SWITCH_STRATEGIES:
            raise TransactionError(f"切换策略「{strategy}」不支持，可选：{'、'.join(SWITCH_STRATEGIES)}")
        with store.transaction():
            entry = store.find(MODULE, entry_id)
            if entry is None:
                raise TransactionError(f"图表配置 {entry_id} 不存在或已归档")
            missing = [f for f in REQUIRED_FIELDS if not str(values.get(f) or "").strip()]
            if missing:
                raise TransactionError(f"缺少必填字段：{'、'.join(missing)}")

            old_source = str(entry.get("数据来源") or "")
            new_source = str(values.get("数据来源") or old_source)
            source_changed = new_source != old_source

            # 先把旧快照补齐，保证任何分支都有一版完整快照可沿用/归档
            old_snapshot = entry.get(SNAPSHOT_KEY)
            if not isinstance(old_snapshot, dict) or not old_snapshot.get("points"):
                old_snapshot = self._build_snapshot(entry)
                entry[SNAPSHOT_KEY] = old_snapshot

            if source_changed and strategy == "freeze_first":
                # 策略一：冻结旧来源完整快照，配置标记待切换，坐标字段暂不改写
                frozen = copy_snapshot(old_snapshot)
                frozen["冻结"] = True
                entry[SNAPSHOT_KEY] = frozen
                entry[PENDING_SOURCE_KEY] = new_source
                entry[SWITCH_STRATEGY_KEY] = strategy
                pending_values = {field: values.get(field, entry.get(field, "")) for field in LIST_FIELDS}
                entry["待切换配置"] = pending_values
                store.bump_version(MODULE)
                self._audit(entry_id, "freeze", frozen,
                            message=f"冻结旧来源「{old_source}」快照，标记待切换至「{new_source}」")
                return self._entry_with_snapshot(entry), "已冻结旧来源完整快照并标记待切换"

            # 策略二（recompute_first），或非来源变更的普通保存：
            # 先归档旧配置/旧快照，再整体写入新配置与新快照
            if source_changed:
                self._archive(entry, old_snapshot, reason=f"数据来源切换：{old_source} -> {new_source}")
            for field in LIST_FIELDS:
                if field in values:
                    entry[field] = values.get(field, "")
            if values.get("指标标识"):
                entry["指标标识"] = str(values.get("指标标识"))
            entry.pop(PENDING_SOURCE_KEY, None)
            entry.pop("待切换配置", None)
            entry.pop(SWITCH_STRATEGY_KEY, None)
            entry["快照版本"] = int(entry.get("快照版本", 0)) + 1
            new_snapshot = self._build_snapshot(entry)
            entry[SNAPSHOT_KEY] = new_snapshot
            store.bump_version(MODULE)
            self._audit(entry_id, "switch" if source_changed else "update", new_snapshot,
                        message=("已切换新来源并整体重算快照" if source_changed else "保存配置并重算数据快照"))
            return self._entry_with_snapshot(entry), (
                "已切换新来源并整体重算快照，旧配置已归档" if source_changed else "图表配置与数据快照已同时保存"
            )

    def confirm_switch(self, entry_id: int) -> tuple[dict[str, Any] | None, str]:
        """确认待切换：把冻结的旧快照归档，按新来源整体重算并提交。"""
        with store.transaction():
            entry = store.find(MODULE, entry_id)
            if entry is None:
                raise TransactionError(f"图表配置 {entry_id} 不存在或已归档")
            pending = entry.get("待切换配置")
            new_source = entry.get(PENDING_SOURCE_KEY)
            if not isinstance(pending, dict) or not new_source:
                raise TransactionError("该图表没有待确认的数据来源切换")
            old_snapshot = entry.get(SNAPSHOT_KEY) or {}
            self._archive(entry, old_snapshot, reason=f"确认切换至新来源：{new_source}")
            for field in LIST_FIELDS:
                entry[field] = pending.get(field, entry.get(field, ""))
            entry.pop(PENDING_SOURCE_KEY, None)
            entry.pop("待切换配置", None)
            entry.pop(SWITCH_STRATEGY_KEY, None)
            entry["快照版本"] = int(entry.get("快照版本", 0)) + 1
            new_snapshot = self._build_snapshot(entry)
            entry[SNAPSHOT_KEY] = new_snapshot
            store.bump_version(MODULE)
            self._audit(entry_id, "confirm_switch", new_snapshot,
                        message="确认切换，新来源完整快照已提交")
            return self._entry_with_snapshot(entry), "已确认切换，新来源数据快照已生效"

    # ---------------------------------------------------------- 一致性核对
    def verify_snapshot(self, entry_id: int) -> dict[str, Any]:
        """按页面显示核对快照与配置是否同源；发现残留错位时整笔回滚到上一版。"""
        with store.transaction():
            entry = store.find(MODULE, entry_id)
            if entry is None:
                raise TransactionError(f"图表配置 {entry_id} 不存在或已归档")
            snapshot = entry.get(SNAPSHOT_KEY)
            if not isinstance(snapshot, dict) or not snapshot.get("points"):
                raise TransactionError("图表缺少完整数据快照，已拒绝以空值展示并回滚")
            mismatches: list[str] = []
            for field in ("数据来源", "横轴字段", "纵轴字段", "分组字段"):
                if str(snapshot.get(field, "")) != str(entry.get(field, "") or ""):
                    mismatches.append(field)
            if mismatches:
                # 残留快照与当前配置指向不同来源：事务内整体回滚，沿用上一版完整快照
                store.bump_version(MODULE)
                self._audit(entry_id, "rollback", snapshot,
                            message=f"快照与配置字段不一致（{'、'.join(mismatches)}），整笔回滚")
                raise TransactionError(f"数据快照与配置不一致：{'、'.join(mismatches)}，已整体回滚")
            self._audit(entry_id, "verify", snapshot, message="快照与配置核对一致")
            return {
                "ok": True,
                "entry_id": entry_id,
                "快照版本": snapshot.get("快照版本"),
                "数据来源": snapshot.get("数据来源"),
                "指标点数": len(snapshot.get("points") or []),
            }

    def list_archive(self) -> list[dict[str, Any]]:
        return [dict(row) for row in store.rows(ARCHIVE_MODULE)]

    def list_audit(self) -> list[dict[str, Any]]:
        return [dict(row) for row in store.rows(AUDIT_MODULE)]

    def _archive(self, entry: dict[str, Any], snapshot: dict[str, Any], *, reason: str) -> None:
        store.rows(ARCHIVE_MODULE).append({
            "id": store.next_id(ARCHIVE_MODULE),
            "图表id": entry.get("id"),
            "图表编号": entry.get("图表编号"),
            "归档原因": reason,
            "配置": {field: entry.get(field, "") for field in LIST_FIELDS},
            "快照": copy_snapshot(snapshot),
            "归档时间": time.time(),
        })

    def _audit(self, entry_id: int, action: str, snapshot: dict[str, Any], *, message: str) -> None:
        store.rows(AUDIT_MODULE).append({
            "id": store.next_id(AUDIT_MODULE),
            "图表id": entry_id,
            "动作": action,
            "快照版本": snapshot.get("快照版本") if isinstance(snapshot, dict) else None,
            "数据来源": snapshot.get("数据来源") if isinstance(snapshot, dict) else None,
            "说明": message,
            "留档版本": "V022",
            "时间": time.time(),
        })

    # ---------------------------------------------------------- 状态流转
    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于可视化配置可执行范围"
        with store.transaction():
            entry = store.find(MODULE, entry_id)
            if entry is None:
                raise TransactionError(f"图表配置 {entry_id} 不存在或已归档")
            target = ACTION_RULES[action]
            if target not in STATUS_ORDER:
                raise TransactionError(f"目标状态「{target}」不在允许的状态序列里")
            # 状态流转前确保挂着完整快照，避免动作后页面只剩配置没有数据
            snapshot = entry.get(SNAPSHOT_KEY)
            if not isinstance(snapshot, dict) or not snapshot.get("points"):
                entry[SNAPSHOT_KEY] = self._build_snapshot(entry)
            entry["status"] = target
            entry["pending"] = target != STATUS_ORDER[-1]
            entry["abnormal"] = action in NEGATIVE_ACTIONS
            store.bump_version(MODULE)
            self._audit(entry_id, f"action:{action}", entry[SNAPSHOT_KEY], message=f"状态流转为{target}")
            return self._entry_with_snapshot(entry), f"图表配置已{action}"

    # ---------------------------------------------- V022 跨模块联动：指标定义
    def read_snapshot_for_metric(self, entry_id: int) -> dict[str, Any]:
        """指标定义（V022）模块读取图表数据快照并校验横纵轴统计粒度。

        返回快照中的指标标识与横纵轴字段/粒度，供指标定义侧核对统计粒度是否同口径。
        """
        with store.transaction():
            entry = store.find(MODULE, entry_id)
            if entry is None:
                raise TransactionError(f"图表配置 {entry_id} 不存在或已归档")
            snapshot = entry.get(SNAPSHOT_KEY)
            if not isinstance(snapshot, dict) or not snapshot.get("points"):
                raise TransactionError("图表数据快照不完整，无法供指标定义模块读取")
            metric_code = str(snapshot.get("指标标识") or "")
            expected = METRIC_GRANULARITY.get(metric_code)
            x_grain = str(snapshot.get("横轴统计粒度") or "")
            y_grain = str(snapshot.get("纵轴统计粒度") or "")
            grain_ok = True
            grain_message = "横纵轴统计粒度与指标定义口径一致"
            if expected is not None and expected not in (x_grain, y_grain):
                grain_ok = False
                grain_message = f"指标 {metric_code} 口径粒度为{expected}，快照横轴{x_grain}/纵轴{y_grain}不匹配"
            payload = {
                "ok": grain_ok,
                "指标标识": metric_code,
                "数据来源": snapshot.get("数据来源"),
                "横轴字段": snapshot.get("横轴字段"),
                "纵轴字段": snapshot.get("纵轴字段"),
                "横轴统计粒度": x_grain,
                "纵轴统计粒度": y_grain,
                "指标定义粒度": expected,
                "message": grain_message,
                "快照版本": snapshot.get("快照版本"),
                "留档版本": "V022",
            }
            self._audit(entry_id, "metric_handoff", snapshot,
                        message=f"快照转交指标定义模块核对：{grain_message}")
            return payload


def copy_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """快照对外返回前复制一份，避免调用方误改持久化数据。"""
    return copy.deepcopy(snapshot)
