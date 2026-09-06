"""文件解析输出额度与聊天上下文预算隔离测试。"""

from types import SimpleNamespace

import pytest

from app.core.config.llm_config import Settings
from app.modules.project_file.analysis import dependencies


def test_file_detail_output_budget_defaults_to_16384(monkeypatch):
    monkeypatch.delenv("PM_AGENT_FILE_DETAIL_MAX_OUTPUT_TOKENS", raising=False)
    monkeypatch.setenv("DEEPSEEK_RESERVED_OUTPUT_TOKENS", "4096")

    settings = Settings()

    assert settings.file_detail.max_output_tokens == 16384
    assert settings.get_llm_config("deepseek").reserved_output_tokens == 4096


@pytest.mark.parametrize("value", ["0", "-1"])
def test_file_detail_output_budget_must_be_positive(monkeypatch, value):
    monkeypatch.setenv("PM_AGENT_FILE_DETAIL_MAX_OUTPUT_TOKENS", value)

    with pytest.raises(ValueError, match="输出 token 上限必须大于 0"):
        Settings()


def test_analysis_and_specification_use_dedicated_output_budget(monkeypatch):
    monkeypatch.setenv("PM_AGENT_FILE_DETAIL_LLM_ENABLED", "true")
    monkeypatch.setenv("PM_AGENT_FILE_DETAIL_MAX_OUTPUT_TOKENS", "24576")
    monkeypatch.setenv("DEEPSEEK_RESERVED_OUTPUT_TOKENS", "4096")
    settings = SimpleNamespace(llm=Settings(), storage=SimpleNamespace(bucket="test"))
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)

    service = dependencies.get_project_file_analysis_service(
        session=SimpleNamespace(), projects=SimpleNamespace(), storage=SimpleNamespace()
    )

    generator = service._semantic_analyzer.generator
    assert generator._max_tokens == 24576
    assert service._specification._generator is generator
