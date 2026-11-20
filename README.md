# 多源数据采集与RPA自动化平台

面向网页抓取、API接入、增量采集、RPA流程编排、数据校验与采集监控的数据工程平台。

这是一个前后端分离的管理平台：前端 Vue 3 + Vite + TypeScript，后端 FastAPI（Python）。
两边各自独立启动，前端 dev server 已关掉自动打开页面，启动后按终端打印的地址手工打开。

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/            每个业务模块一个页面
│   ├── src/api/              统一请求封装
│   ├── src/stores/           会话与筛选状态
│   └── vite.config.ts        dev server 配置（open: false）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/          每个业务模块一组接口
│   ├── app/services/         业务规则与状态流转
│   └── app/store.py          内存数据仓库与示例数据
├── .gitignore
└── docker-compose.yml
```

## 启动

### 后端

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

健康检查：`curl http://127.0.0.1:8000/api/health`

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认监听 `http://127.0.0.1:5173/`，dev server 不会自动打开浏览器，
需要自己访问。`/api` 由 vite 代理到后端 `http://127.0.0.1:8000`。

## 业务模块

| 模块 | 目录 | 业务对象 | 主要字段 |
| --- | --- | --- | --- |
| 数据源配置 | `datasource` | 数据源 | 源端编号、连接类型、接入地址 |
| 网页采集规则 | `crawler` | 采集规则 | 规则编号、目标网址、页面选择器 |
| API接入管理 | `apiclient` | API客户端 | 客户端编号、接口名称、请求方法 |
| 增量采集 | `incremental` | 增量游标 | 游标编号、来源标识、增量字段 |
| RPA任务编排 | `robot_task` | RPA任务 | 任务编号、任务名称、页面定位器 |
| 数据接入通道 | `ingestion` | 接入通道 | 通道编号、通道名称、输入格式 |
| 格式解析器 | `parser` | 解析配置 | 解析编号、输入格式、输出格式 |
| 采集结果校验 | `validator` | 校验规则 | 规则编号、校验字段、校验类型 |
| 采集去重 | `dedup` | 去重策略 | 策略编号、输入来源、去重键 |
| 采集调度 | `schedule` | 调度计划 | 计划编号、关联任务、调度周期 |
| 采集监控 | `monitor` | 监控面板 | 面板编号、采集源总数、今日采集量 |
| 采集日志 | `log_viewer` | 日志条目 | 日志编号、关联任务、日志级别 |
| 凭证管理 | `auth` | 认证凭证 | 凭证编号、凭证类型、关联数据源 |
| 采集转换管道 | `transform` | 转换节点 | 节点编号、输入来源、输出目标 |
| 数据流转编排 | `flow` | 流转管道 | 管道编号、管道名称、起始节点 |
| 数据血缘追踪 | `lineage` | 血缘关系 | 关系编号、上游节点、下游节点 |
| 采集报告 | `report` | 采集报告 | 报告编号、采集源、统计周期 |

## 约定

- 每个模块的前端页面在 `frontend/src/views/<模块>/index.vue`，后端接口在
  `backend/app/routers/<模块>.py`，业务规则在 `backend/app/services/<模块>.py`。
- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。

## 历史抓取规则迁移（crawler_migration）

把网页采集规则的旧平铺清单迁移为带版本的结构化采集定义，并对随旧登记归档的
页面样本做可复核解析。核心代码在 `backend/app/migration/`，只依赖 Python 标准库：

| 文件 | 职责 |
| --- | --- |
| `migration/builder.py` | 旧清单 → 版本化定义与迁移对照明细，逐字段溯源并做跨规则拼装自检 |
| `migration/dom.py` | 零依赖 HTML/DOM 与 CSS 选择器（类型/类/ID、后代/子代），带字符位置追踪 |
| `migration/engine.py` | 按迁移对照为每份样本选择可复核定义，写出解析版本与未解析字段位置 |
| `migration/registry.py` | 新环境统一入口：装载归档、预跑解析、凭旧引用回查原出处、编目核查 |

夹具（旧清单、样本登记、GBK/UTF-8 归档原页）在 `backend/fixtures/migration/`。

迁移口径：

- 含义不足的旧字段（空选择器、未登记语义的键）只保留原文并标记「留原文待核」，
  绝不猜测或补默认选择器；
- 每个结构化字段带 `source_legacy_id`，同一条旧规则独立建版，
  禁止把 A 规则的抓取频率与 B 规则的正文选择器拼成一套（有运行时自检）；
- 同一规则编号的多份旧规格各自得到并存版本（如全页 `1.0.0` / 正文 `1.1.0`）；
- 样本的旧引用可无版本号，`/api/crawler-migration/resolve-ref` 可回查全部候选版本，
  `/api/crawler-migration/archive/{sample_id}` 从归档打开原页，不重新抓取网络；
- 两个版本都能逐字核实的公告标题可编目录；仅出现在全页、没有任何版本选择器登记的
  临时开放时间，保留页面取证与字符位置，但标记为「欠采集版本凭据」挂起待核。

### 主要接口（前缀 `/api/crawler-migration`）

- `GET /summary` 迁移总览
- `GET /migration-mapping` 历史抓取规则迁移对照明细
- `GET /definitions` 带版本的结构化采集定义
- `GET /parse-records`、`/parse-records/{sample_id}` 样本解析记录与未解析字段位置
- `GET /catalog-review` 可编目公告与等待核查项
- `GET /resolve-ref?legacy_ref=` 旧引用回查候选版本与归档样本
- `GET /archive/{sample_id}` 打开归档原页
- `POST /rerun` 重新装载归档并重跑迁移解析

### 测试

```bash
make test
# 或在 backend/ 下
python3 -I scripts/run_tests.py        # 单元/端到端用例（无第三方依赖也可运行）
python3 -I scripts/run_api_check.py    # 视图序列化、业务口径、路由声明核验
python3 -I scripts/run_router_smoke.py # 路由 -> 服务 -> 注册表全链路冒烟
```

装有 `pytest`/`httpx` 时 `scripts/run_tests.py` 自动改用真 pytest，
`tests/test_http_api.py` 会通过 TestClient 复核真实 HTTP 行为。
