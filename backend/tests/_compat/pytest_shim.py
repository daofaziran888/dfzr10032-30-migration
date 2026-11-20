"""极轻量 pytest 垫片：仅支持本仓库测试用到的 fixture、raises 与 mark。

运行环境没有 pip/venv，无法安装真正的 pytest。该垫片只在 ``tests/_compat`` 下，
通过 ``tests/conftest.py`` 注入 sys.path，业务代码完全不依赖它；换到有 pytest 的
环境时直接用 pytest 运行即可，测试文件无需修改。
"""
from __future__ import annotations

import contextlib
import inspect
import sys
import types
from pathlib import Path


class _RaisesAssertion(AssertionError):
    pass


@contextlib.contextmanager
def raises(exc_type, match: str | None = None):
    import re

    try:
        yield
    except exc_type as exc:  # type: ignore[misc]
        if match is not None and not re.search(match, str(exc)):
            raise _RaisesAssertion(f"异常信息 {exc!s} 不匹配 {match!r}") from exc
        return
    raise _RaisesAssertion(f"期望抛出 {exc_type!r}，但没有异常")


class _Fixture:
    def __init__(self, func):
        self.func = func
        self.__name__ = func.__name__


def fixture(func=None):
    if func is None:
        def wrapper(f):
            return _Fixture(f)
        return wrapper
    return _Fixture(func)


class _NoSkip:
    __mini_skip__ = None

    def __init__(self, reason: str = "") -> None:
        self.reason = reason


class _Mark:
    def __getattr__(self, name):
        def decorator(obj):
            return obj
        return decorator

    def skipif(self, condition: bool, reason: str = ""):
        if condition:
            class _SkipMark:
                __mini_skip__ = reason or "条件跳过"

            return _SkipMark()
        return _NoSkip(reason)


mark = _Mark()


class _MiniPytest(types.ModuleType):
    __mini__ = True
    raises = staticmethod(raises)
    fixture = staticmethod(fixture)
    mark = mark

    @staticmethod
    def main(args=None):
        base = Path(__file__).resolve().parent.parent
        if args is None:
            args = [str(base)]
        files: list[Path] = []
        for arg in args:
            p = Path(arg)
            if p.is_dir():
                files.extend(sorted(p.glob("test_*.py")))
            elif p.is_file():
                files.append(p)
        # 先加载 conftest 风格的公共夹具（本项目夹具写在各自文件里，这里只做收集）
        total = passed = 0
        failures: list[str] = []
        for file in files:
            module_name = f"_mini_test_{file.stem}"
            module = types.ModuleType(module_name)
            module.__file__ = str(file)
            sys.modules[module_name] = module
            try:
                code = compile(file.read_text(encoding="utf-8"), str(file), "exec")
                exec(code, module.__dict__)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{file.name}: 模块加载失败 {exc!r}")
                total += 1
                continue
            module_skip = getattr(module, "pytestmark", None)
            skip_reason = None
            if module_skip is not None:
                skip_reason = getattr(module_skip, "__mini_skip__", None)
                if skip_reason is None and isinstance(module_skip, list):
                    for mark_obj in module_skip:
                        skip_reason = getattr(mark_obj, "__mini_skip__", None)
                        if skip_reason:
                            break
            if skip_reason is not None:
                print(f"{file.name}: 跳过（{skip_reason}）")
                continue
            fixtures = {
                name: obj for name, obj in vars(module).items() if isinstance(obj, _Fixture)
            }
            tests = [
                (name, obj) for name, obj in sorted(vars(module).items())
                if name.startswith("test_") and callable(obj)
            ]
            for name, test in tests:
                total += 1
                kwargs = {}
                for param in inspect.signature(test).parameters:
                    if param in fixtures:
                        kwargs[param] = fixtures[param].func()
                try:
                    test(**kwargs)
                    passed += 1
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{file.name}::{name}: {exc!r}")
        print(f"\n{passed}/{total} 用例通过")
        if failures:
            print("失败用例：")
            for item in failures:
                print(" -", item)
            raise SystemExit(1)


sys.modules["pytest"] = _MiniPytest("pytest")
