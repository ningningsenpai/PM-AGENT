"""项目规范模型输出的有限字段名纠正，不改变持久化模型的严格契约。"""

from __future__ import annotations

import json

from app.core.logger import get_logger

logger = get_logger(__name__)

_CONTENT_FIELDS = {
    "development_approach": "rule",
    "technical_constraints": "constraint",
    "coding_rules": "rule",
    "document_rules": "rule",
    "risk_rules": "rule",
}


def normalize_specification_json(content: str) -> str:
    """只转换规则正文的唯一字符串别名，其他错误交由原有 Pydantic 校验拒绝。"""
    try:
        document = json.loads(content)
    except ValueError:
        return content
    if not isinstance(document, dict):
        return content
    body = document.get("project_specification")
    if not isinstance(body, dict):
        return content

    corrected = []
    for field, expected in _CONTENT_FIELDS.items():
        rules = body.get(field)
        if not isinstance(rules, list):
            continue
        alias = "constraint" if expected == "rule" else "rule"
        for index, rule in enumerate(rules):
            # 两个字段同时存在时不选择、不丢弃内容，保留严格校验错误。
            if (
                isinstance(rule, dict)
                and expected not in rule
                and isinstance(rule.get(alias), str)
            ):
                rule[expected] = rule.pop(alias)
                corrected.append(
                    f"project_specification.{field}.{index}.{alias}->{expected}"
                )

    if not corrected:
        return content
    logger.warning(
        "项目规范模型输出字段名已纠正，继续严格校验 "
        "action=project.specification.normalize count=%s fields=%s",
        len(corrected),
        json.dumps(corrected[:20], ensure_ascii=False),
    )
    return json.dumps(document, ensure_ascii=False)
