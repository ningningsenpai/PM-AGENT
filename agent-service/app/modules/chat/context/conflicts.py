"""同主题和词条冲突检查；不同编号不能自动消除相同条件下的矛盾。"""

import unicodedata

from app.core.errors import AppException, ErrorCode


def normalized(value):
    return "".join(unicodedata.normalize("NFKC", value).lower().split())


def conflicts(left, right):
    if left["id"] == right["id"] or left["kind"] != right["kind"]:
        return False
    if left["status"] != "active" or right["status"] != "active":
        return False
    a, b = left["attributes"], right["attributes"]
    if left["kind"] == "term":
        shared = {normalized(x) for x in a.get("aliases", [])} & {
            normalized(x) for x in b.get("aliases", [])
        }
        return bool(shared) and normalized(a.get("canonical") or "") != normalized(
            b.get("canonical") or ""
        )
    return (
        bool(a.get("key"))
        and normalized(a["key"]) == normalized(b.get("key", ""))
        and normalized(left["content"]) != normalized(right["content"])
    )


def coexistence_confirmed(left, right):
    a = {normalized(x) for x in left.get("conditions", []) if x.strip()}
    b = {normalized(x) for x in right.get("conditions", []) if x.strip()}
    # 条件不同只是必要条件，仍须用户明确确认共存关系和理由。
    return bool(a and b and a != b) and (
        right["id"] in left.get("relatedEntryIds", [])
        and bool(left["attributes"].get("coexistReason"))
        or left["id"] in right.get("relatedEntryIds", [])
        and bool(right["attributes"].get("coexistReason"))
    )


def validate_conflicts(entries, changed_ids):
    for index, left in enumerate(entries):
        for right in entries[index + 1 :]:
            if not {left["id"], right["id"]} & changed_ids:
                continue
            if conflicts(left, right) and not coexistence_confirmed(left, right):
                raise AppException(
                    ErrorCode.RESOURCE_CONFLICT,
                    "存在同主题或别名冲突，请纠正、取消候选，或明确不同适用条件及共存理由",
                )
