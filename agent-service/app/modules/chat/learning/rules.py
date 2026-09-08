"""校验学习证据必须来自本次可见的用户原文或反馈。"""

from app.core.errors import AppException, ErrorCode


def validate_source(candidate, sources):
    source = sources.get(candidate.source_message_id)
    if not source or candidate.source_quote not in source:
        raise AppException(ErrorCode.PARAM_INVALID, "学习条目缺少可验证的用户消息原文")
    return source
