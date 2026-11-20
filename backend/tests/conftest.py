"""测试引导：有真 pytest 时不做任何事；无 pytest 的离线环境注入标准库垫片。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

if importlib.util.find_spec("pytest") is None:
    compat_dir = Path(__file__).resolve().parent / "_compat"
    sys.path.insert(0, str(compat_dir))
    import pytest_shim  # noqa: F401
