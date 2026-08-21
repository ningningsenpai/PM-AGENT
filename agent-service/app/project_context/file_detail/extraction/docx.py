from __future__ import annotations

import asyncio
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from .base import ExtractedFileContent

__all__ = ["DocxFileExtractor"]

_DOCUMENT_PATH = "word/document.xml"
_MAX_DOCUMENT_XML_BYTES = 20 * 1024 * 1024
_WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class DocxFileExtractor:
    """从 DOCX 主文档中提取段落和表格文本。"""

    async def extract(self, file_path: Path) -> ExtractedFileContent:
        extracted_text = await asyncio.to_thread(self._extract_text, file_path)
        return {
            "type": "doc",
            "text": extracted_text,
        }

    def _extract_text(self, file_path: Path) -> str:
        try:
            with ZipFile(file_path) as archive:
                document_info = archive.getinfo(_DOCUMENT_PATH)
                if document_info.file_size > _MAX_DOCUMENT_XML_BYTES:
                    raise ValueError("DOCX 文档内容超过允许上限")
                document_xml = archive.read(document_info)
        except (BadZipFile, KeyError) as exception:
            raise ValueError(
                "无法提取 Word 文档，仅支持有效的 DOCX 文件"
            ) from exception

        try:
            document = ElementTree.fromstring(document_xml)
        except ElementTree.ParseError as exception:
            raise ValueError("DOCX 文档结构损坏") from exception

        paragraph_tag = f"{{{_WORD_NAMESPACE}}}p"
        text_tag = f"{{{_WORD_NAMESPACE}}}t"
        tab_tag = f"{{{_WORD_NAMESPACE}}}tab"
        break_tags = {
            f"{{{_WORD_NAMESPACE}}}br",
            f"{{{_WORD_NAMESPACE}}}cr",
        }
        paragraphs: list[str] = []

        for paragraph in document.iter(paragraph_tag):
            parts: list[str] = []
            for element in paragraph.iter():
                if element.tag == text_tag and element.text:
                    parts.append(element.text)
                elif element.tag == tab_tag:
                    parts.append("\t")
                elif element.tag in break_tags:
                    parts.append("\n")
            paragraph_text = "".join(parts).strip()
            if paragraph_text:
                paragraphs.append(paragraph_text)

        return "\n".join(paragraphs)
