#!/usr/bin/env python3
"""无第三方依赖的测试入口：优先使用真 pytest，缺失时回退到标准库垫片。

用法：python3 -I scripts/run_tests.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "tests"))

import conftest  # noqa: E402,F401  （引导垫片或确认 pytest 可用）


def main() -> int:
    import pytest

    if getattr(pytest, "__mini__", False):
        pytest.main([str(BACKEND / "tests")])
        return 0
    return pytest.main([str(BACKEND / "tests"), "-q"])


if __name__ == "__main__":
    raise SystemExit(main())
