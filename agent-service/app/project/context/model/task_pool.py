"""Qwen 调用线程池。"""
from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Generic, TypeVar

__all__ = ["QwenTaskPool", "QwenTaskResult"]

T = TypeVar("T")


@dataclass(frozen=True)
class QwenTaskResult(Generic[T]):
    """Qwen 任务执行结果。"""

    success: bool
    result: T | None = None
    error: str = ""


class QwenTaskPool:
    """固定 6 线程的 Qwen 调用线程池。"""

    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(max_workers=6)

    def run_many(self, tasks: list[Callable[[], T]]) -> list[QwenTaskResult[T]]:
        """批量执行 Qwen 调用任务，并按提交顺序返回结果。"""
        futures = [self.executor.submit(task) for task in tasks]
        results: list[QwenTaskResult[T]] = []

        for future in futures:
            try:
                results.append(QwenTaskResult(success=True, result=future.result()))
            except Exception as error:
                results.append(QwenTaskResult(success=False, error=str(error)))

        return results

    def shutdown(self) -> None:
        """关闭线程池。"""
        self.executor.shutdown(wait=True)

    def __enter__(self) -> "QwenTaskPool":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.shutdown()
