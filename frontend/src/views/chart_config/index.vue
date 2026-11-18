<template>
  <section class="page" data-module="chart_config">
    <header class="page-head">
      <div>
        <h2>可视化配置</h2>
        <p class="page-desc">图表配置与数据快照同事务持久化：切换数据来源后刷新、返回详情页，指标值与坐标字段始终对得上同一份快照。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" data-testid="open-create" type="button" @click="openCreate">登记图表配置</button>
      </div>
    </header>

    <div class="analysis-summary">
      <article v-for="m in summaryMetrics" :key="m.label" class="analysis-card" data-testid="kpi-card">
        <span style="font-size:12px;color:var(--muted)">{{ m.label }}</span>
        <strong style="font-size:22px;display:block">{{ m.value }}</strong>
        <span class="trend-up" style="font-size:12px">快照口径</span>
      </article>
    </div>

    <form class="analysis-form" @submit.prevent="runAnalysis">
      <label v-for="field in runFields" :key="field"><span>{{ field }}</span>
        <input v-model="params[field]" :placeholder="`请输入${field}`" />
      </label>
      <button class="btn primary" type="submit" data-testid="run-analysis">运行分析</button>
    </form>

    <div v-if="chartData.length" class="analysis-chart" data-testid="analysis-chart">
      <div v-for="(bar, i) in chartData" :key="i" class="analysis-bar" :style="{ height: barHeight(bar.value) + 'px' }"><span>{{ bar.label }}</span></div>
    </div>

    <p v-if="message" class="error-text" data-testid="page-message">{{ message }}</p>

    <table class="data-table" v-if="results.length">
      <thead>
        <tr>
          <th v-for="c in resultColumns" :key="c">{{ c }}</th>
          <th>快照指标值</th>
          <th>快照版本</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in results" :key="String(row.id)" :data-testid="`row-${row.id}`" :data-status="String(row.status)">
          <td v-for="c in resultColumns" :key="c">{{ row[c] ?? '—' }}</td>
          <td data-testid="snapshot-values">{{ snapshotPreview(row) }}</td>
          <td>{{ row['数据快照']?.['快照版本'] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" :data-testid="`open-detail-${row.id}`" @click="openDrawer(row)">配置/快照</button>
            <button class="link" type="button" :data-testid="`verify-${row.id}`" @click="verifyRow(row)">核对快照</button>
            <button
              v-if="row['待切换数据来源']"
              class="link"
              type="button"
              :data-testid="`confirm-switch-${row.id}`"
              @click="confirmSwitch(row)"
            >确认切换至{{ row['待切换数据来源'] }}</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :data-testid="`action-${row.id}-${action}`"
              @click="runAction(action, row)"
            >{{ action }}</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="!results.length && !loading" style="text-align:center;color:var(--muted)">暂无图表配置，可先登记并生成首版数据快照</p>

    <!-- 抽屉：与导航页读取同一后端业务数据（同一份持久化快照） -->
    <div v-if="drawerVisible" class="drawer-backdrop" data-testid="chart-drawer" @click.self="closeDrawer">
      <aside class="drawer">
        <header class="drawer-head">
          <h3>{{ drawerMode === 'create' ? '登记图表配置' : `图表配置 #${formId}` }}</h3>
          <button class="btn ghost" type="button" @click="closeDrawer">关闭</button>
        </header>

        <form class="drawer-body" @submit.prevent="submitForm">
          <label v-for="field in configFields" :key="field" class="create-field">
            <span>{{ field }}</span>
            <input v-model="formValues[field]" :data-testid="`form-${field}`" required />
          </label>
          <label class="create-field">
            <span>来源切换策略（V022）</span>
            <select v-model="strategy" data-testid="form-strategy">
              <option value="recompute_first">先切新来源再整体重算快照（旧配置归档）</option>
              <option value="freeze_first">先冻结旧来源完整快照并标记待切换</option>
            </select>
          </label>
          <p v-if="drawerEntry?.['待切换数据来源']" class="error-text" data-testid="pending-source">
            当前冻结旧来源「{{ drawerEntry['数据来源'] }}」完整快照，待切换至「{{ drawerEntry['待切换数据来源'] }}」
          </p>
          <div class="page-actions">
            <button class="btn" type="button" @click="closeDrawer">取消</button>
            <button class="btn primary" type="submit" data-testid="submit-save">保存配置与快照</button>
          </div>
        </form>

        <section v-if="drawerSnapshot" class="drawer-snapshot" data-testid="drawer-snapshot">
          <h4>数据快照（与页面显示同源）</h4>
          <p class="page-desc">
            指标标识 {{ drawerSnapshot['指标标识'] || '—' }} · 来源 {{ drawerSnapshot['数据来源'] }} ·
            横轴 {{ drawerSnapshot['横轴字段'] }}（{{ drawerSnapshot['横轴统计粒度'] }}）·
            纵轴 {{ drawerSnapshot['纵轴字段'] }}（{{ drawerSnapshot['纵轴统计粒度'] }}）·
            版本 v{{ drawerSnapshot['快照版本'] }}
          </p>
          <table class="data-table">
            <thead><tr><th>分组</th><th>横轴取值</th><th>指标值</th><th>对比基准</th><th>差异</th></tr></thead>
            <tbody>
              <tr v-for="p in drawerSnapshot.points" :key="p.id">
                <td>{{ p['分组'] }}</td><td>{{ p['横轴取值'] }}</td><td>{{ p['指标值'] }}</td><td>{{ p['对比基准'] }}</td><td>{{ p['差异'] }}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { request } from '@/api/client'

const ENDPOINT = '/api/chart_config'
type SnapshotPoint = Record<string, string | number>
type Snapshot = Record<string, any> & { points: SnapshotPoint[] }
type ChartRow = Record<string, any> & { id: number; '数据快照'?: Snapshot }

const configFields = ['图表编号', '图表类型', '数据来源', '横轴字段', '纵轴字段', '分组字段', '刷新间隔', '分享链接']
const resultColumns = configFields.slice(0, 5)
const runFields = ['图表编号', '数据来源', '横轴字段', '纵轴字段'].slice(0, 4)
const actions = ['提交校验', '确认发布', '停用图表']

const summaryMetrics = ref<{ label: string; value: number; trend: number }[]>([])
const results = ref<ChartRow[]>([])
const chartData = ref<{ label: string; value: number }[]>([])
const loading = ref(false)
const message = ref('')
const params = ref<Record<string, string>>({})

const drawerVisible = ref(false)
const drawerMode = ref<'create' | 'edit'>('create')
const formId = ref<number | null>(null)
const formValues = ref<Record<string, string>>({})
const strategy = ref<'recompute_first' | 'freeze_first'>('recompute_first')
const drawerEntry = ref<ChartRow | null>(null)

const drawerSnapshot = computed<Snapshot | null>(() => drawerEntry.value?.['数据快照'] ?? null)

function snapshotPreview(row: ChartRow): string {
  const points = row['数据快照']?.points ?? []
  return points.slice(0, 3).map((p: SnapshotPoint) => p['指标值']).join(' / ') || '—'
}

function barHeight(v: number): number {
  const max = Math.max(...chartData.value.map(d => d.value), 1)
  return Math.max(10, (v / max) * 140)
}

async function fetchSummary(): Promise<void> {
  try {
    const res = await request(`${ENDPOINT}/summary`)
    summaryMetrics.value = (await res.json()).metrics || []
  } catch {
    summaryMetrics.value = []
  }
}

async function reload(): Promise<void> {
  loading.value = true
  message.value = ''
  try {
    const res = await request(ENDPOINT)
    if (!res.ok) throw new Error('图表配置列表读取失败')
    const payload = await res.json()
    results.value = payload.items ?? []
    // 抽屉若开着，同步成同一业务数据的最新快照
    if (drawerVisible.value && formId.value !== null) {
      const latest = results.value.find(r => r.id === formId.value)
      if (latest) drawerEntry.value = latest
    }
  } catch (error) {
    message.value = error instanceof Error ? error.message : '图表配置列表读取失败'
  } finally {
    loading.value = false
  }
}

async function runAnalysis(): Promise<void> {
  loading.value = true
  try {
    const res = await request(`${ENDPOINT}/run`, { method: 'POST', body: JSON.stringify({ values: params.value }) })
    const data = await res.json()
    const items: SnapshotPoint[] = data.items || []
    chartData.value = items
      .map((r: SnapshotPoint) => ({
        label: String(r['分组'] ?? Object.values(r)[0]),
        value: Number(r['指标值'] ?? 0),
      }))
      .slice(0, 6)
  } catch {
    chartData.value = []
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  drawerMode.value = 'create'
  formId.value = null
  formValues.value = Object.fromEntries(configFields.map(f => [f, '']))
  strategy.value = 'recompute_first'
  drawerEntry.value = null
  drawerVisible.value = true
}

async function openDrawer(row: ChartRow): Promise<void> {
  drawerMode.value = 'edit'
  formId.value = row.id
  message.value = ''
  try {
    // 抽屉与导航页读取同一接口的同一份持久化快照
    const res = await request(`${ENDPOINT}/${row.id}`)
    if (!res.ok) throw new Error('图表详情读取失败')
    const detail: ChartRow = await res.json()
    drawerEntry.value = detail
    formValues.value = Object.fromEntries(configFields.map(f => [f, String(detail[f] ?? '')]))
    strategy.value = (detail['切换策略'] as 'recompute_first' | 'freeze_first') || 'recompute_first'
    drawerVisible.value = true
  } catch (error) {
    message.value = error instanceof Error ? error.message : '图表详情读取失败'
  }
}

function closeDrawer(): void {
  drawerVisible.value = false
  drawerEntry.value = null
}

async function submitForm(): Promise<void> {
  message.value = ''
  try {
    const url = drawerMode.value === 'create' ? ENDPOINT : `${ENDPOINT}/${formId.value}`
    const method = drawerMode.value === 'create' ? 'POST' : 'PUT'
    const body = drawerMode.value === 'create'
      ? JSON.stringify({ values: formValues.value })
      : JSON.stringify({ values: formValues.value, strategy: strategy.value })
    const res = await request(url, { method, body })
    const payload = await res.json()
    if (!res.ok || !payload.ok) throw new Error(payload.detail || payload.message || '保存失败，事务已回滚')
    message.value = payload.message
    closeDrawer()
    await reload()
  } catch (error) {
    message.value = error instanceof Error ? error.message : '保存失败，已沿用上一版完整快照'
  }
}

async function confirmSwitch(row: ChartRow): Promise<void> {
  message.value = ''
  try {
    const res = await request(`${ENDPOINT}/${row.id}/confirm-switch`, { method: 'POST' })
    const payload = await res.json()
    if (!res.ok || !payload.ok) throw new Error(payload.detail || payload.message || '确认切换失败')
    message.value = payload.message
    await reload()
  } catch (error) {
    message.value = error instanceof Error ? error.message : '确认切换失败'
  }
}

async function verifyRow(row: ChartRow): Promise<void> {
  message.value = ''
  try {
    const res = await request(`${ENDPOINT}/${row.id}/verify`, { method: 'POST' })
    const payload = await res.json()
    if (!res.ok || payload.ok === false) throw new Error(payload.detail || payload.message || '快照核对未通过')
    message.value = `图表 #${row.id} 快照核对一致：来源 ${payload['数据来源']}，指标点 ${payload['指标点数']} 个（V022 留档）`
  } catch (error) {
    message.value = error instanceof Error ? error.message : '快照核对失败，已整体回滚'
  }
}

async function runAction(action: string, row: ChartRow): Promise<void> {
  message.value = ''
  try {
    const res = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = await res.json()
    if (!res.ok || !payload.ok) throw new Error(payload.detail || payload.message || '动作未生效')
    message.value = payload.message
    await reload()
  } catch (error) {
    message.value = error instanceof Error ? error.message : '图表动作执行失败'
  }
}

onMounted(() => {
  void fetchSummary()
  void reload()
})
</script>
