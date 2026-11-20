"""业务模块路由汇总。

这里统一按别名导入再暴露 ROUTERS：模块名有可能和内置名撞车（某个业务模块就叫 dict、list
这种名字时），按名字直接 import 会把内置类型覆盖掉，函数注解在运行时求值就会报
'module' object is not subscriptable。
"""
from __future__ import annotations

from app.routers import datasource as router_datasource
from app.routers import crawler as router_crawler
from app.routers import crawler_migration as router_crawler_migration
from app.routers import apiclient as router_apiclient
from app.routers import incremental as router_incremental
from app.routers import robot_task as router_robot_task
from app.routers import ingestion as router_ingestion
from app.routers import parser as router_parser
from app.routers import validator as router_validator
from app.routers import dedup as router_dedup
from app.routers import schedule as router_schedule
from app.routers import monitor as router_monitor
from app.routers import log_viewer as router_log_viewer
from app.routers import auth as router_auth
from app.routers import transform as router_transform
from app.routers import flow as router_flow
from app.routers import lineage as router_lineage
from app.routers import report as router_report

ROUTERS = [router_datasource, router_crawler, router_crawler_migration, router_apiclient, router_incremental, router_robot_task, router_ingestion, router_parser, router_validator, router_dedup, router_schedule, router_monitor, router_log_viewer, router_auth, router_transform, router_flow, router_lineage, router_report]
