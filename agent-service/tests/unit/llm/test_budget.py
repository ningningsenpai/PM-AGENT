"""费用预留和真实调用预算回归。"""
import sqlite3
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

import pytest

from app.llm.telemetry import ModelCall, capture_calls


@pytest.fixture
def tmp_path():
    """使用工作区临时目录，兼容 Windows 沙箱的用户临时目录权限。"""
    path = Path.cwd() / ".tmp" / f"budget-{uuid4().hex}"
    path.mkdir(parents=True)
    return path


def test_reservation_survives_unknown_usage(tmp_path):
    ledger = str(tmp_path / 'budget.sqlite3')
    with patch.dict('os.environ', {'PM_AGENT_TEST_BUDGET_PATH': ledger, 'PM_AGENT_TEST_BUDGET_CNY': '1'}):
        events = []
        with capture_calls(events):
            call = ModelCall({'model': 'deepseek-v4-flash', 'messages': [], 'max_tokens': 100}, 2000)
            call.finish(error=TimeoutError())
        with sqlite3.connect(ledger) as conn:
            reserved, charged = conn.execute('SELECT reserved,charged FROM calls').fetchone()
        assert reserved == charged > 0
        assert events[0]['usageKnown'] is False


def test_context_guard_runs_before_network():
    with pytest.raises(ValueError, match='上下文预算'):
        ModelCall({'model': 'deepseek-v4-flash', 'max_tokens': 1024}, 1024)


def test_budget_refuses_additional_calls(tmp_path):
    with patch.dict('os.environ', {'PM_AGENT_TEST_BUDGET_PATH': str(tmp_path / 'budget.sqlite3'), 'PM_AGENT_TEST_BUDGET_CNY': '0.001'}):
        with pytest.raises(ValueError, match='累计预算'):
            ModelCall({'model': 'deepseek-v4-flash', 'max_tokens': 1024}, 20000)
