"""大小写、Unicode 和空白等基础文本处理。"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

__all__ = ["TextNormalizationResult", "TextNormalizer"]


@dataclass(frozen=True)
class TextNormalizationResult:
    """文本清洗结果及清洗字符到原文字符的位置映射。"""

    cleaned_text: str
    original_index_map: tuple[int, ...]


class TextNormalizer:
    """以相同规则处理用户文本和术语库别名。"""

    def normalize(self, text: str) -> TextNormalizationResult:
        """执行逐字符 NFKC、大小写统一和连续空白折叠。"""
        if not isinstance(text, str):
            raise TypeError("待归一化内容必须是字符串")

        cleaned_characters: list[str] = []
        original_index_map: list[int] = []

        for original_index, character in enumerate(text):
            normalized_character = unicodedata.normalize("NFKC", character).casefold()
            for expanded_character in normalized_character:
                if expanded_character.isspace():
                    if not cleaned_characters or cleaned_characters[-1] == " ":
                        continue
                    cleaned_characters.append(" ")
                    original_index_map.append(original_index)
                    continue

                cleaned_characters.append(expanded_character)
                original_index_map.append(original_index)

        if cleaned_characters and cleaned_characters[-1] == " ":
            cleaned_characters.pop()
            original_index_map.pop()

        return TextNormalizationResult(
            cleaned_text="".join(cleaned_characters),
            original_index_map=tuple(original_index_map),
        )

    def normalize_for_matching(self, text: str) -> str:
        """返回适合作为自动机键的清洗文本。"""
        return self.normalize(text).cleaned_text
