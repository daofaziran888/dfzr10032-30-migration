<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">多源数据采集与RPA自动化平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向网页抓取、API接入、增量采集、RPA流程编排、数据校验与采集监控的数据工程平台。</span>
        <span class="head-user">当前值班：{{ store.operator }} · {{ store.shiftLabel }}</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

const navItems = [{ label: "运营概览", path: "/" }, { label: "数据源配置", path: "/datasource" }, { label: "网页采集规则", path: "/crawler" }, { label: "历史抓取规则迁移", path: "/crawler_migration" }, { label: "API接入管理", path: "/apiclient" }, { label: "增量采集", path: "/incremental" }, { label: "RPA任务编排", path: "/robot_task" }, { label: "数据接入通道", path: "/ingestion" }, { label: "格式解析器", path: "/parser" }, { label: "采集结果校验", path: "/validator" }, { label: "采集去重", path: "/dedup" }, { label: "采集调度", path: "/schedule" }, { label: "采集监控", path: "/monitor" }, { label: "采集日志", path: "/log_viewer" }, { label: "凭证管理", path: "/auth" }, { label: "采集转换管道", path: "/transform" }, { label: "数据流转编排", path: "/flow" }, { label: "数据血缘追踪", path: "/lineage" }, { label: "采集报告", path: "/report" }]
</script>
