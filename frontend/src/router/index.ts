import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '@/views/Dashboard.vue'
const Datasource = () => import('@/views/datasource/index.vue')
const Crawler = () => import('@/views/crawler/index.vue')
const CrawlerMigration = () => import('@/views/crawler_migration/index.vue')
const Apiclient = () => import('@/views/apiclient/index.vue')
const Incremental = () => import('@/views/incremental/index.vue')
const RobotTask = () => import('@/views/robot_task/index.vue')
const Ingestion = () => import('@/views/ingestion/index.vue')
const Parser = () => import('@/views/parser/index.vue')
const Validator = () => import('@/views/validator/index.vue')
const Dedup = () => import('@/views/dedup/index.vue')
const Schedule = () => import('@/views/schedule/index.vue')
const Monitor = () => import('@/views/monitor/index.vue')
const LogViewer = () => import('@/views/log_viewer/index.vue')
const Auth = () => import('@/views/auth/index.vue')
const Transform = () => import('@/views/transform/index.vue')
const Flow = () => import('@/views/flow/index.vue')
const Lineage = () => import('@/views/lineage/index.vue')
const Report = () => import('@/views/report/index.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard },
    { path: '/datasource', name: 'datasource', component: Datasource },
    { path: '/crawler', name: 'crawler', component: Crawler },
    { path: '/crawler_migration', name: 'crawler_migration', component: CrawlerMigration },
    { path: '/apiclient', name: 'apiclient', component: Apiclient },
    { path: '/incremental', name: 'incremental', component: Incremental },
    { path: '/robot_task', name: 'robot_task', component: RobotTask },
    { path: '/ingestion', name: 'ingestion', component: Ingestion },
    { path: '/parser', name: 'parser', component: Parser },
    { path: '/validator', name: 'validator', component: Validator },
    { path: '/dedup', name: 'dedup', component: Dedup },
    { path: '/schedule', name: 'schedule', component: Schedule },
    { path: '/monitor', name: 'monitor', component: Monitor },
    { path: '/log_viewer', name: 'log_viewer', component: LogViewer },
    { path: '/auth', name: 'auth', component: Auth },
    { path: '/transform', name: 'transform', component: Transform },
    { path: '/flow', name: 'flow', component: Flow },
    { path: '/lineage', name: 'lineage', component: Lineage },
    { path: '/report', name: 'report', component: Report },
  ],
})

export default router
