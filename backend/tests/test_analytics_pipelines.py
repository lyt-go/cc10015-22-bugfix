"""多维分析实验平台核心链路测试。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.store import store, TransactionError
from app.services.experiment import ExperimentService
from app.services.sample_group import SampleGroupService
from app.services.ab_result import AbResultService
from app.services.metric_def import MetricDefService
from app.services.chart_config import ChartConfigService
from app.services.expr_factor import ExprFactorService
from app.services.segment_compare import SegmentCompareService
from app.services.attr_analysis import AttrAnalysisService
from app.services.anomaly_detect import AnomalyDetectService
from app.services.forecast_model import ForecastModelService
from app.services.insight_report import InsightReportService
from app.services.metric_alias import MetricAliasService
from app.services.evaluate_board import EvaluateBoardService
from app.services.data_freshness import DataFreshnessService
from app.services.cohort_track import CohortTrackService
from app.services.data_export import DataExportService
from app.services.drill_down import DrillDownService

def _clear_all():
    for k in list(store._tables.keys()):
        store._tables[k] = []

def test_pipeline_experiment_to_sample_groups():
    """实验创建后自动生成对照和实验组分群。"""
    _clear_all()
    es = ExperimentService()
    entry, ms = es.create_entry({
        "方案编号": "EXPE-001",
        "实验名称": "新首页布局",
        "对照组说明": "旧版首页",
        "实验组说明": "新版首页",
        "样本总量": "10000",
        "分流比例": "5:5",
        "启动日期": "2026-11-01",
        "预期时长": "14",
    })
    assert entry is not None, ms
    sg_rows = store.rows("sample_group")
    assert len(sg_rows) >= 2, f"应创建对照组和实验组，实际{len(sg_rows)}"
    control = [r for r in sg_rows if r.get("group_type") == "control"]
    exp = [r for r in sg_rows if r.get("group_type") == "experiment"]
    assert len(control) >= 1
    assert len(exp) >= 1
    assert int(control[0].get("样本基数", 0)) > 0
    assert int(exp[0].get("样本基数", 0)) > 0

def test_sample_group_members():
    """分群能生成带差异的用户列表。"""
    _clear_all()
    # 先创建实验再用自动分群
    es = ExperimentService()
    es.create_entry({"方案编号":"EXPE-002","实验名称":"测试","对照组说明":"控","实验组说明":"试","样本总量":"200","分流比例":"5:5"})
    sg = SampleGroupService()
    members = sg.get_group_members(1)
    assert len(members) > 0, "应有分群用户"
    assert "user_id" in members[0]
    assert "metric_value" in members[0]

def test_metric_def_creation():
    """指标定义创建和口径版本。"""
    _clear_all()
    md = MetricDefService()
    entry, ms = md.create_entry({
        "指标编号": "M-001",
        "指标名称": "点击率",
        "计算公式": "clicks / impressions",
        "统计粒度": "日",
        "时间窗口": "7",
        "基准取值": "0.10",
        "精度位数": "4",
        "口径版本": "v1",
    })
    assert entry is not None, ms

def test_ab_result_analysis():
    """AB分析生成对照和实验组对比。"""
    _clear_all()
    ab = AbResultService()
    results = ab.run_analysis({"样本范围": "4"})
    assert len(results) == 4
    for r in results:
        assert "指标值" in r
        assert "对比基准" in r
        assert "差异" in r

def test_expr_factor_creation():
    """实验因子互斥规则。"""
    _clear_all()
    ef = ExprFactorService()
    entry, ms = ef.create_entry({
        "因子编号": "F-001",
        "因子名称": "按钮颜色",
        "因子层级": "UI层",
        "取值集合": "红色,蓝色",
        "分配比例": "5:5",
        "互斥规则": "颜色因子互斥",
        "关联实验": "EXPE-001",
        "生效批次": "B001",
    })
    assert entry is not None, ms

def test_anomaly_detect():
    """异常检测计算移动平均。"""
    _clear_all()
    ad = AnomalyDetectService()
    ad.create_entry({
        "规则编号": "AD-001",
        "监控指标": "点击率",
        "检测算法": "moving_average",
        "基线窗口": "7",
        "波动阈值": "0.3",
        "告警级别": "高",
        "静默时段": "0",
        "规则版本": "v1",
    })
    result = ad.run_detection(1, [0.10, 0.12, 0.11, 0.13, 0.15, 0.14, 0.55])
    assert result.get("ok") or "anomaly" in str(result).lower()

def test_forecast_model():
    """预测模型简单移动平均。"""
    _clear_all()
    fc = ForecastModelService()
    fc.create_entry({
        "模型编号": "FC-001",
        "预测对象": "点击率",
        "历史窗口": "7",
        "预测周期": "3",
        "模型类型": "moving_average",
        "参数配置": "window=3",
        "训练批次": "T001",
        "评估误差": "",
    })
    result = fc.train_and_predict(1, [0.10, 0.12, 0.11, 0.13, 0.15, 0.14, 0.16])
    assert result.get("ok"), result

def test_metric_alias_version():
    """口径版本注册。"""
    _clear_all()
    ma = MetricAliasService()
    entry, ms = ma.create_entry({
        "版本编号": "ALIAS-001",
        "指标编号": "M-001",
        "变更说明": "修改去重逻辑",
        "旧口径": "clicks/impressions",
        "新口径": "clicks/valid_impressions",
        "生效时间": "2026-11-16",
        "审批状态": "草稿",
        "变更人": "admin",
    })
    assert entry is not None, ms


def _chart_values(source: str, code: str = "CHAR-T1") -> dict:
    return {
        "图表编号": code,
        "图表类型": "折线图",
        "数据来源": source,
        "横轴字段": "统计日期(按日)",
        "纵轴字段": "成交金额(按日)",
        "分组字段": "渠道",
    }


def test_chart_snapshot_persistent_across_reads():
    """图表数据快照持久化：刷新、重新读取拿到同一组指标值。"""
    _clear_all()
    svc = ChartConfigService()
    created, missing = svc.create_entry(_chart_values("src_a"))
    assert created is not None and not missing
    cid = created["id"]
    assert created["数据快照"]["points"]
    first_values = [p["指标值"] for p in created["数据快照"]["points"]]
    # 列表与详情重复读取必须完全一致（刷新、返回详情页场景）
    assert [p["指标值"] for p in svc.list_results()[0]["数据快照"]["points"]] == first_values
    detail = svc.get_entry(cid)
    assert [p["指标值"] for p in detail["数据快照"]["points"]] == first_values
    # 运行分析按业务主键派生稳定种子，同样参数可复现
    run_a = svc.run_analysis({"图表编号": "CHAR-T1", "数据来源": "src_a"})
    run_b = svc.run_analysis({"图表编号": "CHAR-T1", "数据来源": "src_a"})
    assert run_a == run_b
    # 不同来源得到不同快照，避免版本错位
    run_c = svc.run_analysis({"图表编号": "CHAR-T1", "数据来源": "src_b"})
    assert run_c != run_a


def test_chart_config_and_snapshot_commit_together():
    """配置与快照同时提交：保存失败时事务整体回滚，沿用上一版完整快照。"""
    _clear_all()
    svc = ChartConfigService()
    entry, missing = svc.create_entry(_chart_values("src_a"))
    assert entry is not None and not missing
    cid = entry["id"]
    assert entry["数据快照"]["数据来源"] == "src_a"
    before = svc.get_entry(cid)

    # 缺必填字段 -> 抛 TransactionError，仓库整体回滚，旧快照完整保留
    try:
        svc.update_entry(cid, {"图表编号": ""}, strategy="recompute_first")
        raise AssertionError("缺字段应当触发事务回滚")
    except TransactionError:
        pass
    after = svc.get_entry(cid)
    assert after["数据来源"] == before["数据来源"] == "src_a"
    assert after["数据快照"]["points"] == before["数据快照"]["points"]


def test_chart_source_switch_strategies_and_archive():
    """两种切换策略：冻结旧来源待切换；切新来源整体重算并归档旧配置。"""
    _clear_all()
    svc = ChartConfigService()

    # recompute_first：页面显示新来源完整快照，旧配置归档
    entry, _ = svc.create_entry(_chart_values("src_old"))
    cid = entry["id"]
    switched, msg = svc.update_entry(cid, _chart_values("src_new"), strategy="recompute_first")
    assert switched["数据来源"] == "src_new"
    assert switched["数据快照"]["数据来源"] == "src_new"
    assert switched["横轴字段"] == switched["数据快照"]["横轴字段"]
    archive = svc.list_archive()
    assert len(archive) == 1 and archive[0]["图表id"] == cid
    assert "src_old" in archive[0]["归档原因"]
    # 刷新后新来源快照值不变
    assert svc.get_entry(cid)["数据快照"] == switched["数据快照"]

    # freeze_first：页面仍显示旧来源完整快照并标记待切换
    entry2, _ = svc.create_entry(_chart_values("src_old", code="CHAR-T2"))
    cid2 = entry2["id"]
    frozen, fmsg = svc.update_entry(cid2, _chart_values("src_new", code="CHAR-T2"), strategy="freeze_first")
    assert frozen["数据来源"] == "src_old"
    assert frozen["数据快照"]["数据来源"] == "src_old"
    assert frozen["数据快照"].get("冻结") is True
    assert frozen["待切换数据来源"] == "src_new"
    # 确认切换后才整体重算新来源快照
    confirmed, _ = svc.confirm_switch(cid2)
    assert confirmed["数据来源"] == "src_new"
    assert confirmed["数据快照"]["数据来源"] == "src_new"
    assert "待切换数据来源" not in confirmed


def test_chart_snapshot_verify_and_v022_metric_handoff():
    """快照核对在事务内回滚；V022 指标定义读取快照指标标识并校验统计粒度。"""
    _clear_all()
    chart_svc = ChartConfigService()
    entry, _ = chart_svc.create_entry(_chart_values("src_a"))
    cid = entry["id"]
    report = chart_svc.verify_snapshot(cid)
    assert report["ok"] and report["数据来源"] == "src_a"

    # 刷新中断：配置已改而快照未更新的半截写入，在外层事务里整体回滚，
    # 沿用上一版完整快照，恢复后核对仍通过
    row = store.find("chart_config", cid)
    interrupted = False
    try:
        with store.transaction():
            row["数据来源"] = "half_written_source"
            try:
                chart_svc.verify_snapshot(cid)
            except TransactionError:
                interrupted = True
                raise
    except TransactionError:
        pass
    assert interrupted
    restored = store.find("chart_config", cid)
    assert restored["数据来源"] == "src_a"
    assert chart_svc.verify_snapshot(cid)["ok"]

    # 已落库的残留错位快照：核对报错，且不会让图表改显空值；
    # 重新保存（整体重算）后恢复一致
    row = store.find("chart_config", cid)
    row["数据快照"]["数据来源"] = "stale_source"
    try:
        chart_svc.verify_snapshot(cid)
        raise AssertionError("残留快照核对应当失败")
    except TransactionError as exc:
        assert "整体回滚" in str(exc)
    fixed, _ = chart_svc.update_entry(cid, _chart_values("src_a"))
    assert fixed["数据快照"]["数据来源"] == "src_a"
    assert chart_svc.verify_snapshot(cid)["ok"]

    # V022：指标定义模块沿调用链读取同一份快照并核对横纵轴统计粒度
    mds = MetricDefService()
    mds.create_entry({
        "指标编号": "CHAR-T1", "指标名称": "成交额",
        "计算公式": "sum(amount)", "统计粒度": "按日",
    })
    handoff = mds.read_chart_snapshot(cid)
    assert handoff["指标标识"] == "CHAR-T1"
    assert handoff["粒度校验通过"] is True
    assert handoff["横轴统计粒度"] == "按日" and handoff["纵轴统计粒度"] == "按日"
    assert handoff["留档版本"] == "V022"
    # 留痕均按 V022 归档
    assert all(a["留档版本"] == "V022" for a in chart_svc.list_audit())


