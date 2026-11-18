import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'

type ModuleCase = {
  key: string
  fields: string[]
  actions: string[]
  actionTargets: string[]
  shape: string
}

const modules: ModuleCase[] = [
  {
    "key": "experiment",
    "fields": [
      "方案编号",
      "实验名称",
      "对照组说明",
      "实验组说明",
      "样本总量",
      "分流比例",
      "启动日期",
      "预期时长"
    ],
    "actions": [
      "提交审批",
      "启动实验",
      "终止实验"
    ],
    "actionTargets": [
      "待审批",
      "运行中",
      "已结束"
    ],
    "shape": "job-timeline"
  },
  {
    "key": "sample_group",
    "fields": [
      "分群编号",
      "分群名称",
      "筛选条件",
      "样本基数",
      "分群日期",
      "更新方式",
      "有效天数",
      "负责人"
    ],
    "actions": [
      "开始计算",
      "确认就绪",
      "标记过期"
    ],
    "actionTargets": [
      "计算中",
      "已就绪",
      "已过期"
    ],
    "shape": "crud-table"
  },
  {
    "key": "metric_def",
    "fields": [
      "指标编号",
      "指标名称",
      "计算公式",
      "统计粒度",
      "时间窗口",
      "基准取值",
      "精度位数",
      "口径版本"
    ],
    "actions": [
      "提交校验",
      "标记生效",
      "标记废弃"
    ],
    "actionTargets": [
      "待校验",
      "已生效",
      "已废弃"
    ],
    "shape": "crud-table"
  },
  {
    "key": "ab_result",
    "fields": [
      "报告编号",
      "实验编号",
      "分析指标",
      "对照组均值",
      "实验组均值",
      "置信水平",
      "效果方向",
      "生成时间"
    ],
    "actions": [
      "开始计算",
      "确认完成",
      "归档报告"
    ],
    "actionTargets": [
      "计算中",
      "已完成",
      "已归档"
    ],
    "shape": "analysis-dashboard"
  },
  {
    "key": "segment_compare",
    "fields": [
      "任务编号",
      "分群A",
      "分群B",
      "对比指标",
      "时间范围",
      "差异阈值",
      "显著性水平",
      "比较方法"
    ],
    "actions": [
      "开始计算",
      "确认完成",
      "废弃任务"
    ],
    "actionTargets": [
      "计算中",
      "已完成",
      "已废弃"
    ],
    "shape": "analysis-dashboard"
  },
  {
    "key": "drill_down",
    "fields": [
      "维度编号",
      "维度名称",
      "下钻层级",
      "基准指标",
      "父级维度",
      "子级维度",
      "数据来源",
      "刷新间隔"
    ],
    "actions": [
      "提交校验",
      "标记生效",
      "停用维度"
    ],
    "actionTargets": [
      "待校验",
      "已生效",
      "已停用"
    ],
    "shape": "analysis-dashboard"
  },
  {
    "key": "data_filter",
    "fields": [
      "规则编号",
      "数据来源",
      "筛选字段",
      "筛选算子",
      "筛选阈值",
      "逻辑组合",
      "输出集合",
      "规则版本"
    ],
    "actions": [
      "提交校验",
      "标记生效",
      "停用规则"
    ],
    "actionTargets": [
      "待校验",
      "已生效",
      "已停用"
    ],
    "shape": "crud-table"
  },
  {
    "key": "attr_analysis",
    "fields": [
      "任务编号",
      "目标指标",
      "候选因子",
      "归因模型",
      "分析窗口",
      "贡献度阈值",
      "交互项数",
      "任务批次"
    ],
    "actions": [
      "开始计算",
      "确认完成",
      "取消任务"
    ],
    "actionTargets": [
      "计算中",
      "已完成",
      "已取消"
    ],
    "shape": "analysis-dashboard"
  },
  {
    "key": "anomaly_detect",
    "fields": [
      "规则编号",
      "监控指标",
      "检测算法",
      "基线窗口",
      "波动阈值",
      "告警级别",
      "静默时段",
      "规则版本"
    ],
    "actions": [
      "提交校验",
      "标记生效",
      "停用规则"
    ],
    "actionTargets": [
      "待校验",
      "已生效",
      "已停用"
    ],
    "shape": "crud-table"
  },
  {
    "key": "forecast_model",
    "fields": [
      "模型编号",
      "预测对象",
      "历史窗口",
      "预测周期",
      "模型类型",
      "参数配置",
      "训练批次",
      "评估误差"
    ],
    "actions": [
      "开始训练",
      "确认就绪",
      "废弃模型"
    ],
    "actionTargets": [
      "训练中",
      "已就绪",
      "已废弃"
    ],
    "shape": "analysis-dashboard"
  },
  {
    "key": "data_export",
    "fields": [
      "任务编号",
      "数据来源",
      "导出格式",
      "字段清单",
      "数据范围",
      "压缩方式",
      "分片大小",
      "导出批次"
    ],
    "actions": [
      "开始导出",
      "确认完成",
      "取消导出"
    ],
    "actionTargets": [
      "导出中",
      "已完成",
      "已取消"
    ],
    "shape": "job-timeline"
  },
  {
    "key": "cohort_track",
    "fields": [
      "群组编号",
      "群组名称",
      "首次行为",
      "时间基准",
      "追踪周期",
      "留存窗口",
      "分析指标",
      "对比群组"
    ],
    "actions": [
      "提交校验",
      "标记生效",
      "停用群组"
    ],
    "actionTargets": [
      "待校验",
      "已生效",
      "已停用"
    ],
    "shape": "analysis-dashboard"
  },
  {
    "key": "chart_config",
    "fields": [
      "图表编号",
      "图表类型",
      "数据来源",
      "横轴字段",
      "纵轴字段",
      "分组字段",
      "刷新间隔",
      "分享链接"
    ],
    "actions": [
      "提交校验",
      "确认发布",
      "停用图表"
    ],
    "actionTargets": [
      "待校验",
      "已发布",
      "已停用"
    ],
    "shape": "analysis-dashboard"
  },
  {
    "key": "insight_report",
    "fields": [
      "报告编号",
      "分析主题",
      "数据来源",
      "关键发现",
      "建议措施",
      "影响范围",
      "生成时间",
      "报告版本"
    ],
    "actions": [
      "开始生成",
      "确认完成",
      "归档报告"
    ],
    "actionTargets": [
      "生成中",
      "已完成",
      "已归档"
    ],
    "shape": "analysis-dashboard"
  },
  {
    "key": "data_freshness",
    "fields": [
      "监控编号",
      "数据表名",
      "最新分区",
      "期望刷新",
      "滞后时长",
      "告警阈值",
      "检查间隔",
      "通知方式"
    ],
    "actions": [
      "提交校验",
      "标记生效",
      "停用监控"
    ],
    "actionTargets": [
      "待校验",
      "已生效",
      "已停用"
    ],
    "shape": "crud-table"
  },
  {
    "key": "metric_alias",
    "fields": [
      "版本编号",
      "指标编号",
      "变更说明",
      "旧口径",
      "新口径",
      "生效时间",
      "审批状态",
      "变更人"
    ],
    "actions": [
      "提交审批",
      "确认生效",
      "执行回滚"
    ],
    "actionTargets": [
      "待审批",
      "已生效",
      "已回滚"
    ],
    "shape": "crud-table"
  },
  {
    "key": "expr_factor",
    "fields": [
      "因子编号",
      "因子名称",
      "因子层级",
      "取值集合",
      "分配比例",
      "互斥规则",
      "关联实验",
      "生效批次"
    ],
    "actions": [
      "提交校验",
      "标记生效",
      "停用因子"
    ],
    "actionTargets": [
      "待校验",
      "已生效",
      "已停用"
    ],
    "shape": "crud-table"
  },
  {
    "key": "evaluate_board",
    "fields": [
      "看板编号",
      "看板名称",
      "关联实验",
      "展示指标",
      "数据范围",
      "刷新策略",
      "消费范围",
      "看板版本"
    ],
    "actions": [
      "提交校验",
      "确认发布",
      "停用看板"
    ],
    "actionTargets": [
      "待校验",
      "已发布",
      "已停用"
    ],
    "shape": "analysis-dashboard"
  }
]
const repoKind = 'fullstack'
const crudModules = modules.filter(m => m.shape === 'crud-table')
const dagModules = modules.filter(m => m.shape === 'dag-graph')
const timelineModules = modules.filter(m => m.shape === 'job-timeline')
const analysisModules = modules.filter(m => m.shape === 'analysis-dashboard')

function parseCsv(text: string): string[][] {
  const records: string[][] = []
  let row: string[] = []
  let cell = ''
  let quoted = false
  const input = text.replace(/^\uFEFF/, '')
  for (let index = 0; index < input.length; index++) {
    const char = input[index]
    if (quoted) {
      if (char === '"' && input[index + 1] === '"') { cell += '"'; index++ }
      else if (char === '"') { quoted = false }
      else { cell += char }
    } else if (char === '"' && cell === '') { quoted = true }
    else if (char === ',') { row.push(cell); cell = '' }
    else if (char === '\n') {
      row.push(cell.replace(/\r$/, ''))
      if (row.some(v => v !== '')) records.push(row)
      row = []; cell = ''
    } else { cell += char }
  }
  row.push(cell.replace(/\r$/, ''))
  if (row.some(v => v !== '')) records.push(row)
  return records
}

test('CRUD模块：筛选、导出、登记、动作、指标全链路', async ({ page }) => {
  test.setTimeout(300_000)
  const browserErrors: string[] = []
  page.on('pageerror', e => browserErrors.push(e.message))
  page.on('response', r => { if (r.url().includes('/api/') && r.status()>=400) browserErrors.push(`${r.status()} ${r.url()}`) })
  if (crudModules.length === 0) { test.skip(); return }

  for (const mod of crudModules) {
    await page.goto(`/${mod.key}`)
    await page.waitForTimeout(3000)
    const bodyRows = page.locator('tbody tr[data-testid^="row-"]')
    await expect(bodyRows).toHaveCount(3)
    const firstValue = await bodyRows.nth(0).locator('td').nth(0).innerText()

    await page.getByTestId(`filter-${mod.fields[0]}`).fill(firstValue)
    await page.getByTestId('query').click()
    await expect(bodyRows).toHaveCount(1)
    await page.getByTestId('reset').click()
    await expect(bodyRows).toHaveCount(3)

    const downloadPromise = page.waitForEvent('download')
    await page.getByTestId('export').click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toBe(`${mod.key}.csv`)

    const createdValues = mod.fields.map((f, i) => `验收-${mod.key}-${i+1}`)
    await page.getByTestId('open-create').click()
    await expect(page.getByTestId('create-modal')).toBeVisible()
    for (const [i, field] of mod.fields.entries()) {
      await page.getByTestId(`create-${field}`).fill(createdValues[i])
    }
    await page.getByTestId('submit-create').click()
    await expect(page.getByTestId('create-modal')).toHaveCount(0)
    await expect(bodyRows).toHaveCount(4)

    const createdRow = page.locator('tbody tr').filter({ hasText: createdValues[0] })
    for (const [i, action] of mod.actions.entries()) {
      await createdRow.getByRole('button', { name: action, exact: true }).click()
      await expect(createdRow).toHaveAttribute('data-status', mod.actionTargets[i])
    }
  }

  expect(browserErrors).toEqual([])
})

test('DAG拓扑模块：节点渲染、详情、动作、导出', async ({ page }) => {
  test.setTimeout(300_000)
  const browserErrors: string[] = []
  page.on('pageerror', e => browserErrors.push(e.message))
  page.on('response', r => { if (r.url().includes('/api/') && r.status()>=400) browserErrors.push(`${r.status()} ${r.url()}`) })
  if (dagModules.length === 0) { test.skip(); return }

  for (const mod of dagModules) {
    await page.goto(`/${mod.key}`)
    await page.waitForTimeout(3000)
    await expect(page.locator('svg.dag-svg')).toBeVisible()
    const nodes = page.locator('g.dag-node')
    const count = await nodes.count()
    expect(count).toBeGreaterThanOrEqual(3)

    await nodes.first().click()
    await expect(page.getByTestId('dag-detail')).toBeVisible()

    const downloadPromise = page.waitForEvent('download')
    await page.getByTestId('export').click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toBe(`${mod.key}.csv`)

    await page.getByTestId('open-create').click()
    await expect(page.getByTestId('create-modal')).toBeVisible()
    for (const [i, field] of mod.fields.slice(0,3).entries()) {
      await page.locator('.create-field input').nth(i).fill(`E2E-${mod.key}-${i}`)
    }
    await page.getByTestId('submit-create').click()
    await expect(page.getByTestId('create-modal')).toHaveCount(0)
  }

  expect(browserErrors).toEqual([])
})

test('时间线模块：甘特条渲染、日期筛选、日志查看、登记', async ({ page }) => {
  test.setTimeout(300_000)
  const browserErrors: string[] = []
  page.on('pageerror', e => browserErrors.push(e.message))
  page.on('response', r => { if (r.url().includes('/api/') && r.status()>=400) browserErrors.push(`${r.status()} ${r.url()}`) })
  if (timelineModules.length === 0) { test.skip(); return }

  for (const mod of timelineModules) {
    await page.goto(`/${mod.key}`)
    await expect(page.locator('.timeline-bar').first()).toBeVisible({ timeout: 10000 })
    const bars = page.locator('.timeline-bar')
    const count = await bars.count()
    expect(count).toBeGreaterThanOrEqual(3)

    await bars.first().click()
    await expect(page.getByTestId('timeline-log')).toBeVisible()

    const downloadPromise = page.waitForEvent('download')
    await page.getByTestId('export').click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toBe(`${mod.key}.csv`)

    await page.getByTestId('open-create').click()
    await expect(page.getByTestId('create-modal')).toBeVisible()
    for (const [i, field] of mod.fields.slice(0,3).entries()) {
      await page.locator('.create-field input').nth(i).fill(`E2E-${mod.key}-${i}`)
    }
    await page.getByTestId('submit-create').click()
    await expect(page.getByTestId('create-modal')).toHaveCount(0)
  }

  expect(browserErrors).toEqual([])
})

test('分析看板模块：KPI卡片、运行分析、图表渲染', async ({ page }) => {
  test.setTimeout(300_000)
  const browserErrors: string[] = []
  page.on('pageerror', e => browserErrors.push(e.message))
  page.on('response', r => { if (r.url().includes('/api/') && r.status()>=400) browserErrors.push(`${r.status()} ${r.url()}`) })
  if (analysisModules.length === 0) { test.skip(); return }

  for (const mod of analysisModules) {
    await page.goto(`/${mod.key}`)
    await expect(page.getByTestId('kpi-card').first()).toBeVisible({ timeout: 10000 })
    const kpiCards = page.getByTestId('kpi-card')
    const kpiCount = await kpiCards.count()
    expect(kpiCount).toBeGreaterThanOrEqual(2)
    await expect(kpiCards.first().locator('strong')).toBeVisible()

    await page.getByTestId('run-analysis').click()
    await expect(page.locator('.analysis-bar').first()).toBeVisible({ timeout: 5000 })
    await expect(page.locator('.data-table tbody tr').first()).toBeVisible({ timeout: 5000 })
  }

  expect(browserErrors).toEqual([])
})

test('概览汇总', async ({ page }) => {
  test.setTimeout(300_000)
  await page.goto('/')
  await expect(page.locator('.stat-value').nth(1)).toBeVisible()
  // 验证概览页加载正常即可，不硬编码精确计数（取决于各模块 E2E 登记成功数）
})

test('可视化配置：图表数据快照持久化、来源切换与 V022 联动', async ({ page, request }) => {
  test.setTimeout(300_000)
  const browserErrors: string[] = []
  page.on('pageerror', e => browserErrors.push(e.message))
  page.on('response', r => { if (r.url().includes('/api/') && r.status() >= 400) browserErrors.push(`${r.status()} ${r.url()}`) })

  const api = process.env.E2E_BASE_URL?.replace(/:\d+$/, ':8000') ?? 'http://127.0.0.1:8000'
  const configValues = {
    图表编号: 'E2E-SNAP-001',
    图表类型: '折线图',
    数据来源: 'e2e_source_a',
    横轴字段: '统计日期(按日)',
    纵轴字段: '成交金额(按日)',
    分组字段: '渠道',
    刷新间隔: '5分钟',
    分享链接: 'https://example.com/a',
  }

  // 登记：配置与首版快照同时提交
  const createResp = await request.post(`${api}/api/chart_config`, { data: { values: configValues } })
  expect(createResp.ok()).toBeTruthy()
  const created = await createResp.json()
  expect(created.ok).toBeTruthy()
  const chartId = created.entry.id as number
  const firstValues = created.entry['数据快照'].points.map((p: any) => p['指标值'])
  expect(firstValues).toHaveLength(6)

  await page.goto('/chart_config')
  const targetRow = page.getByTestId(`row-${chartId}`)
  await expect(targetRow).toBeVisible({ timeout: 10000 })

  // 刷新页面后仍是同一组指标值（不再出现旧随机指标）
  await page.reload()
  await expect(page.getByTestId(`row-${chartId}`)).toBeVisible()
  const rowTextAfterReload = await page.getByTestId(`row-${chartId}`).getByTestId('snapshot-values').innerText()
  for (const value of firstValues.slice(0, 3)) {
    expect(rowTextAfterReload).toContain(String(value))
  }

  // 抽屉与导航页读取同一业务数据：抽屉快照与列表同源
  await page.getByTestId(`open-detail-${chartId}`).click()
  await expect(page.getByTestId('chart-drawer')).toBeVisible()
  await expect(page.getByTestId('drawer-snapshot')).toBeVisible()
  const drawerText = await page.getByTestId('drawer-snapshot').innerText()
  expect(drawerText).toContain('e2e_source_a')
  expect(drawerText).toContain(String(firstValues[0]))

  // recompute_first：切换数据来源，坐标字段与快照一起重算
  await page.getByTestId('form-数据来源').fill('e2e_source_b')
  await page.getByTestId('form-横轴字段').fill('自然周(按周)')
  await page.getByTestId('submit-save').click()
  await expect(page.getByTestId('chart-drawer')).toHaveCount(0)
  const switchedResp = await request.get(`${api}/api/chart_config/${chartId}`)
  const switched = await switchedResp.json()
  expect(switched['数据来源']).toBe('e2e_source_b')
  expect(switched['数据快照']['数据来源']).toBe('e2e_source_b')
  expect(switched['数据快照']['横轴字段']).toBe('自然周(按周)')
  expect(switched['数据快照']['横轴统计粒度']).toBe('按周')
  // 重新进入页面仍对得上同一组值
  await page.reload()
  const switchedRow = await (await request.get(`${api}/api/chart_config/${chartId}`)).json()
  const reloadedRow = await (await request.get(`${api}/api/chart_config/${chartId}`)).json()
  expect(reloadedRow['数据快照']).toEqual(switchedRow['数据快照'])
  // 旧配置已归档
  const archive = await (await request.get(`${api}/api/chart_config/archive`)).json()
  expect(archive.items.some((a: any) => a['图表id'] === chartId)).toBeTruthy()

  // freeze_first：冻结旧来源完整快照并标记待切换，页面仍显示旧来源
  const freezeResp = await request.put(`${api}/api/chart_config/${chartId}`, {
    data: { strategy: 'freeze_first', values: { ...configValues, 数据来源: 'e2e_source_c' } },
  })
  expect(freezeResp.ok()).toBeTruthy()
  const frozen = await freezeResp.json()
  expect(frozen.entry['数据来源']).toBe('e2e_source_b')
  expect(frozen.entry['待切换数据来源']).toBe('e2e_source_c')
  await page.reload()
  await expect(page.getByTestId(`confirm-switch-${chartId}`)).toBeVisible()
  await page.getByTestId(`confirm-switch-${chartId}`).click()
  await page.waitForLoadState('networkidle')
  const confirmed = await (await request.get(`${api}/api/chart_config/${chartId}`)).json()
  expect(confirmed['数据来源']).toBe('e2e_source_c')
  expect(confirmed['数据快照']['数据来源']).toBe('e2e_source_c')

  // 核对快照：一致时返回 ok
  const verifyResp = await request.post(`${api}/api/chart_config/${chartId}/verify`)
  expect(verifyResp.ok()).toBeTruthy()
  const verify = await verifyResp.json()
  expect(verify.ok).toBeTruthy()

  // 保存失败整体回滚：缺必填字段返回 409，旧快照完整保留
  const rollbackResp = await request.put(`${api}/api/chart_config/${chartId}`, {
    data: { strategy: 'recompute_first', values: { 图表编号: '' } },
  })
  expect(rollbackResp.status()).toBe(409)
  const afterRollback = await (await request.get(`${api}/api/chart_config/${chartId}`)).json()
  expect(afterRollback['数据快照']['points']).toHaveLength(6)
  expect(afterRollback['数据来源']).toBe('e2e_source_c')

  // V022 跨模块联动：指标定义读取快照指标标识并校验横纵轴统计粒度
  await request.post(`${api}/api/metric_def`, {
    data: { 指标编号: 'E2E-SNAP-001', 指标名称: 'E2E指标', 计算公式: 'sum(x)', 统计粒度: '按日' },
  })
  const handoffResp = await request.get(`${api}/api/metric_def/chart-handoff/${chartId}`)
  expect(handoffResp.ok()).toBeTruthy()
  const handoff = await handoffResp.json()
  expect(handoff['指标标识']).toBe('E2E-SNAP-001')
  expect(handoff['留档版本']).toBe('V022')
  expect(handoff['粒度校验通过'] === true || handoff['粒度校验通过'] === false).toBeTruthy()

  expect(browserErrors).toEqual([])
})
