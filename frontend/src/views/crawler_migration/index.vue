<template>
  <section class="page" data-module="crawler-migration">
    <header class="page-head">
      <div>
        <h2>历史抓取规则迁移</h2>
        <p class="page-desc">
          把旧平铺清单（目标网址、内容选择器、字符编码）迁移为带版本的结构化采集定义；
          含义不足字段留原文待核、不猜默认选择器，并对归档样本做可复核解析与编目核查。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="rerun">重新装载并重跑解析</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <nav class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </nav>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <!-- 迁移对照明细 -->
    <div v-if="activeTab === 'mapping'">
      <table class="data-table">
        <thead>
          <tr>
            <th>旧规则 ID</th>
            <th>规则编号</th>
            <th>新版本</th>
            <th>已迁移字段</th>
            <th>留原文待核字段</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in migrationRows" :key="row.legacy_id">
            <td>{{ row.legacy_id }}</td>
            <td>{{ row.rule_no }}</td>
            <td>
              <strong>{{ row.definition_id }}@{{ row.version }}</strong>
            </td>
            <td>
              <ul class="cell-list">
                <li v-for="m in row.field_mappings" :key="m.field_name + m.source_legacy_field">
                  {{ m.field_name }} ← {{ m.source_legacy_field }} = {{ m.value }}
                  <em class="src-tag">{{ m.source_legacy_id }}</em>
                </li>
              </ul>
            </td>
            <td>
              <ul class="cell-list">
                <li v-for="rv in row.review_fields" :key="rv.field_name + (rv.source_legacy_field ?? '')" class="review-item">
                  {{ rv.field_name }}（{{ rv.status }}）
                  <div class="review-note">{{ rv.note }}</div>
                </li>
              </ul>
            </td>
            <td class="muted-cell">{{ row.note || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 版本化定义 -->
    <div v-else-if="activeTab === 'definitions'">
      <table class="data-table">
        <thead>
          <tr>
            <th>定义</th>
            <th>版本</th>
            <th>范围</th>
            <th>来源旧规则</th>
            <th>目标网址</th>
            <th>抓取频率</th>
            <th>标题选择器</th>
            <th>正文选择器</th>
            <th>字符编码</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in definitions" :key="d.definition_id + d.version">
            <td>{{ d.definition_id }}</td>
            <td><strong>{{ d.version }}</strong></td>
            <td>
              <span class="scope-tag" :class="d.scope">{{ scopeText(d.scope) }}</span>
            </td>
            <td>{{ d.derived_from_legacy_id }}</td>
            <td class="prov-cell" :class="{ held: d.target_url.status !== '已迁移' }">
              {{ d.target_url.value ?? '—' }}
            </td>
            <td class="prov-cell" :class="{ held: d.crawl_frequency.status !== '已迁移' }">
              {{ d.crawl_frequency.value ?? '待核' }}
            </td>
            <td class="prov-cell" :class="{ held: d.title_selector.status !== '已迁移' }">
              <code>{{ d.title_selector.value ?? '留原文待核' }}</code>
            </td>
            <td class="prov-cell" :class="{ held: d.content_selector.status !== '已迁移' }">
              <code>{{ d.content_selector.value ?? '留原文待核' }}</code>
            </td>
            <td>{{ d.encoding.value ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
      <p class="page-foot">每个字段都带 source_legacy_id 溯源；已迁移字段只可能来自同一条旧规则，跨规则拼装有自检拦截。</p>
    </div>

    <!-- 样本解析记录 -->
    <div v-else-if="activeTab === 'parse'">
      <div v-for="rec in parseRecords" :key="rec.sample_id" class="record-card">
        <header class="record-head">
          <div>
            <strong>{{ rec.sample_id }}</strong>
            <span class="muted-cell">旧引用 {{ rec.legacy_ref }}</span>
            <span v-if="rec.legacy_version === null || rec.legacy_version === ''" class="review-tag">无版本号</span>
            <span v-else class="muted-cell">旧版本 {{ rec.legacy_version }}</span>
          </div>
          <span class="status-tag" :class="rec.overall_status">{{ statusText(rec.overall_status) }}</span>
        </header>
        <p class="muted-cell">
          归档原页：{{ rec.archive_path }} · 候选定义：{{ rec.candidate_definitions.join('，') || '无' }}
          · 用于复核：{{ rec.selected_for_review.join('，') || '无' }}
        </p>
        <table class="data-table sub-table">
          <thead>
            <tr>
              <th>定义版本</th>
              <th>字段</th>
              <th>选择器</th>
              <th>状态</th>
              <th>解析值 / 未解析位置</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="vr in rec.version_results" :key="vr.definition_id + vr.version">
              <tr v-for="f in vr.fields" :key="vr.version + f.field_name">
                <td>{{ vr.definition_id }}@{{ vr.version }}（{{ scopeText(vr.scope) }}）</td>
                <td>{{ fieldText(f.field_name) }}</td>
                <td><code>{{ f.selector ?? '—' }}</code></td>
                <td>
                  <span class="status-tag" :class="f.status">{{ statusText(f.status) }}</span>
                </td>
                <td>
                  <template v-if="f.status === '已解析'">
                    {{ f.value }}
                    <div class="muted-cell">位置 第 {{ f.line_number }} 行 / 字符 {{ f.char_position }}</div>
                  </template>
                  <template v-else>
                    <span class="review-item">未能解析</span>
                    <div class="review-note">
                      字符位置 {{ f.char_position ?? '未知' }} · 行号 {{ f.line_number ?? '未知' }} — {{ f.note }}
                    </div>
                  </template>
                </td>
              </tr>
            </template>
            <tr v-if="!rec.version_results.length">
              <td colspan="5" class="empty-state">旧引用回查不到任何采集定义，待人工核查</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 编目核查 -->
    <div v-else-if="activeTab === 'catalog'">
      <div class="catalog-columns">
        <article class="catalog-col">
          <h3>可编目公告（{{ catalogRows.filter((c) => c.title_catalogable).length }}）</h3>
          <div v-for="c in catalogRows.filter((c) => c.title_catalogable)" :key="c.sample_id" class="catalog-card ok">
            <strong>{{ c.announcement_title }}</strong>
            <p class="muted-cell">样本 {{ c.sample_id }} · {{ c.decision }}</p>
            <ul class="cell-list">
              <li v-for="ev in c.title_evidence" :key="ev.definition">
                {{ ev.definition }}（旧规则 {{ ev.legacy_id }}）逐字核实：{{ ev.value }}
              </li>
            </ul>
            <div v-for="h in c.held_fields" :key="h.field + h.definition" class="hold-box">
              挂起：{{ fieldText(h.field) }}
              <template v-if="h.value"> = {{ h.value }}</template>
              <div class="review-note">{{ h.reason }}</div>
            </div>
          </div>
        </article>
        <article class="catalog-col">
          <h3>等待核查（{{ catalogRows.filter((c) => !c.title_catalogable).length }}）</h3>
          <div v-for="c in catalogRows.filter((c) => !c.title_catalogable)" :key="c.sample_id" class="catalog-card hold">
            <strong>{{ c.announcement_title ?? '标题未能核实' }}</strong>
            <p class="muted-cell">样本 {{ c.sample_id }} — {{ c.reason }}</p>
          </div>
          <p v-if="!catalogRows.some((c) => !c.title_catalogable)" class="muted-cell">本轮没有标题待核样本。</p>
        </article>
      </div>
      <div class="legend-box">
        口径：两个版本都能逐字核实的标题可直接编公告目录；临时开放时间只在全页版本页面取证、
        没有任何采集版本选择器登记，属“欠采集版本凭据”，保留字符位置但不编入目录。
      </div>
    </div>

    <!-- 旧引用回查 -->
    <div v-else-if="activeTab === 'resolve'">
      <form class="filter-bar" @submit.prevent="resolveRef">
        <label class="filter-item">
          <span>样本上的旧规则引用（可无版本号）</span>
          <input v-model="refInput" placeholder="例如 LIB-12 或 LEGACY-LIB40-01" />
        </label>
        <button class="btn primary" type="submit">回查原出处</button>
      </form>
      <div v-if="resolveResult" class="record-card">
        <p>旧引用 <strong>{{ resolveResult.legacy_ref }}</strong> 回查到 {{ resolveResult.candidate_definitions.length }} 个候选版本：</p>
        <ul class="cell-list">
          <li v-for="d in resolveResult.candidate_definitions" :key="d.definition_id + d.version">
            {{ d.definition_id }}@{{ d.version }} · {{ scopeText(d.scope) }} · 溯源 {{ d.derived_from_legacy_id }}
          </li>
        </ul>
        <p class="muted-cell">关联旧登记：{{ resolveResult.related_legacy_ids.join('、') }}</p>
        <p class="muted-cell">归档样本：</p>
        <ul class="cell-list">
          <li v-for="s in resolveResult.archived_samples" :key="s.sample_id">
            {{ s.sample_id }} — {{ s.archive_path }}（来源 {{ s.source_url }}）
            <button class="link" type="button" @click="openArchive(s.sample_id)">打开归档原页</button>
          </li>
        </ul>
      </div>

      <div v-if="archivePage" class="record-card">
        <header class="record-head">
          <strong>归档原页 {{ archivePage.sample_id }}</strong>
          <span class="muted-cell">{{ archivePage.declared_encoding }} · {{ archivePage.char_length }} 字符</span>
        </header>
        <p class="muted-cell">来源网址 {{ archivePage.source_url }}，从旧引用打开仍是原页（离线归档，不重新抓取）。</p>
        <pre class="archive-pre">{{ archivePage.markup }}</pre>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

interface Provenance {
  field_name: string
  value: string | null
  status: string
  source_legacy_id: string | null
  source_legacy_field: string | null
  raw_value: unknown
  note: string
}
interface MigrationEntry {
  legacy_id: string
  rule_no: string
  definition_id: string
  version: string
  field_mappings: Provenance[]
  review_fields: Provenance[]
  note: string
}
interface Definition {
  definition_id: string
  version: string
  scope: string
  target_url: Provenance
  encoding: Provenance
  crawl_frequency: Provenance
  title_selector: Provenance
  content_selector: Provenance
  page_selector: Provenance | null
  derived_from_legacy_id: string
  status: string
}
interface ParsedField {
  field_name: string
  selector: string | null
  status: string
  value: string | null
  char_position: number | null
  line_number: number | null
  snippet: string
  note: string
}
interface VersionResult {
  definition_id: string
  version: string
  derived_from_legacy_id: string
  scope: string
  fields: ParsedField[]
  page_char_length: number
}
interface ParseRecord {
  sample_id: string
  legacy_ref: string
  legacy_version: string | null
  source_url: string
  archive_path: string
  candidate_definitions: string[]
  selected_for_review: string[]
  version_results: VersionResult[]
  unresolved_locations: ParsedField[]
  overall_status: string
}
interface TitleEvidence {
  definition: string
  legacy_id: string
  selector: string | null
  value: string
  char_position: number | null
  line_number: number | null
}
interface HeldField {
  definition: string
  field: string
  value?: string
  char_position?: number | null
  line_number?: number | null
  reason: string
}
interface CatalogDecision {
  sample_id: string
  announcement_title: string | null
  title_evidence: TitleEvidence[]
  title_catalogable: boolean
  held_fields: HeldField[]
  decision: string
  reason: string
}
interface Summary {
  legacy_rule_count: number
  definition_count: number
  sample_count: number
  pending_review_field_count: number
  catalogable_samples: string[]
  held_samples: string[]
}
interface CandidateDefinition {
  definition_id: string
  version: string
  scope: string
  derived_from_legacy_id: string
}
interface ArchivedSampleRef {
  sample_id: string
  archive_path: string
  source_url: string
  legacy_version: string | null
}
interface ResolveResult {
  legacy_ref: string
  resolved: boolean
  related_legacy_ids: string[]
  candidate_definitions: CandidateDefinition[]
  archived_samples: ArchivedSampleRef[]
}
interface ArchivePage {
  sample_id: string
  legacy_ref: string
  legacy_version: string | null
  source_url: string
  archive_path: string
  declared_encoding: string
  byte_length: number
  char_length: number
  markup: string
}

const ENDPOINT = '/api/crawler-migration'
const tabs = [
  { key: 'mapping', label: '迁移对照明细' },
  { key: 'definitions', label: '版本化定义' },
  { key: 'parse', label: '样本解析记录' },
  { key: 'catalog', label: '编目核查' },
  { key: 'resolve', label: '旧引用回查' },
] as const

const activeTab = ref<(typeof tabs)[number]['key']>('mapping')
const errorMessage = ref('')
const summary = ref<Summary | null>(null)
const migrationRows = ref<MigrationEntry[]>([])
const definitions = ref<Definition[]>([])
const parseRecords = ref<ParseRecord[]>([])
const catalogRows = ref<CatalogDecision[]>([])
const refInput = ref('LIB-12')
const resolveResult = ref<ResolveResult | null>(null)
const archivePage = ref<ArchivePage | null>(null)

const statCards = computed(() => [
  { label: '旧规则登记', value: summary.value?.legacy_rule_count ?? 0 },
  { label: '版本化定义', value: summary.value?.definition_count ?? 0 },
  { label: '归档样本', value: summary.value?.sample_count ?? 0 },
  { label: '留原文待核字段', value: summary.value?.pending_review_field_count ?? 0 },
  { label: '可编目 / 待核查', value: `${summary.value?.catalogable_samples.length ?? 0} / ${summary.value?.held_samples.length ?? 0}` },
])

function scopeText(scope: string): string {
  return { full_page: '全页', body_only: '仅正文', unknown: '范围待核' }[scope] ?? scope
}
function statusText(status: string): string {
  return { 已解析: '已解析', 未能解析: '未能解析', 多版本待核: '多版本待核' }[status] ?? status
}
function fieldText(field: string): string {
  return {
    announcement_title: '公告标题',
    announcement_body: '公告正文',
    temporary_opening_hours: '临时开放时间',
  }[field] ?? field
}

async function getJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    const detail = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(detail.detail ?? `接口返回 ${response.status}`)
  }
  return response.json() as Promise<T>
}

async function loadAll() {
  errorMessage.value = ''
  try {
    const [sum, mapping, defs, parse, catalog] = await Promise.all([
      getJson<Summary>(`${ENDPOINT}/summary`),
      getJson<{ items: MigrationEntry[] }>(`${ENDPOINT}/migration-mapping`),
      getJson<{ items: Definition[] }>(`${ENDPOINT}/definitions`),
      getJson<{ items: ParseRecord[] }>(`${ENDPOINT}/parse-records`),
      getJson<{ items: CatalogDecision[] }>(`${ENDPOINT}/catalog-review`),
    ])
    summary.value = sum
    migrationRows.value = mapping.items
    definitions.value = defs.items
    parseRecords.value = parse.items
    catalogRows.value = catalog.items
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '迁移数据读取失败'
  }
}

async function resolveRef() {
  errorMessage.value = ''
  archivePage.value = null
  try {
    resolveResult.value = await getJson<ResolveResult>(
      `${ENDPOINT}/resolve-ref?legacy_ref=${encodeURIComponent(refInput.value)}`,
    )
  } catch (error) {
    resolveResult.value = null
    errorMessage.value = error instanceof Error ? error.message : '旧引用回查失败'
  }
}

async function openArchive(sampleId: string) {
  errorMessage.value = ''
  try {
    archivePage.value = await getJson<ArchivePage>(`${ENDPOINT}/archive/${encodeURIComponent(sampleId)}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '归档原页打开失败'
  }
}

async function rerun() {
  errorMessage.value = ''
  try {
    await request(`${ENDPOINT}/rerun`, { method: 'POST' })
    await loadAll()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '重跑失败'
  }
}

onMounted(loadAll)
</script>

<style scoped>
.tab-bar { display: flex; gap: 6px; margin-bottom: 14px; flex-wrap: wrap; }
.tab-btn { border: 1px solid var(--border); background: #fff; border-radius: 6px; padding: 6px 14px; cursor: pointer; font-size: 13px; }
.tab-btn.active { background: var(--brand); border-color: var(--brand); color: #fff; }
.cell-list { margin: 0; padding-left: 16px; display: flex; flex-direction: column; gap: 4px; font-size: 12px; }
.src-tag { color: var(--muted); font-style: normal; margin-left: 4px; }
.review-item { color: #b54708; }
.review-note { color: var(--muted); font-size: 12px; }
.muted-cell { color: var(--muted); font-size: 12px; }
.scope-tag { padding: 2px 8px; border-radius: 10px; font-size: 12px; }
.scope-tag.full_page { background: #e0f2fe; color: #075985; }
.scope-tag.body_only { background: #dcfce7; color: #166534; }
.scope-tag.unknown { background: #fef3c7; color: #92400e; }
.prov-cell.held { color: #b54708; }
.status-tag { padding: 2px 8px; border-radius: 10px; font-size: 12px; white-space: nowrap; }
.status-tag.已解析 { background: #dcfce7; color: #166534; }
.status-tag.未能解析 { background: #fee2e2; color: #b42318; }
.status-tag.多版本待核 { background: #fef3c7; color: #92400e; }
.review-tag { background: #fef3c7; color: #92400e; border-radius: 10px; padding: 2px 8px; font-size: 12px; margin-left: 6px; }
.record-card { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; margin-bottom: 14px; }
.record-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.sub-table { margin-top: 8px; }
.catalog-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.catalog-col h3 { font-size: 15px; margin: 4px 0 10px; }
.catalog-card { border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; background: #fff; }
.catalog-card.ok { border-left: 4px solid #16a34a; }
.catalog-card.hold { border-left: 4px solid #d97706; }
.hold-box { margin-top: 8px; padding: 8px 10px; background: #fffbeb; border-radius: 6px; font-size: 13px; color: #92400e; }
.legend-box { margin-top: 12px; padding: 10px 14px; background: #f8fafc; border: 1px dashed var(--border); border-radius: 8px; font-size: 13px; color: var(--muted); }
.archive-pre { background: #0f172a; color: #e2e8f0; padding: 12px; border-radius: 8px; max-height: 420px; overflow: auto; font-size: 12px; }
</style>
