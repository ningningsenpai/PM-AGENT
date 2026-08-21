from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

import httpx

__all__ = ["FileDownloader"]


class FileDownloader:
    """将可信的 HTTP 临时地址下载到受控临时文件。"""

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        max_file_size_bytes: int = 50 * 1024 * 1024,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("下载超时时间必须大于 0")
        if max_file_size_bytes <= 0:
            raise ValueError("最大文件大小必须大于 0")

        self._timeout_seconds = timeout_seconds
        self._max_file_size_bytes = max_file_size_bytes

    async def download(self, temp_url: str) -> Path:
        """下载文件并返回临时路径；下载失败时不会遗留临时文件。"""
        self._validate_url(temp_url)
        temp_path = self._create_temp_path(temp_url)

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=self._timeout_seconds,
            ) as client:
                async with client.stream("GET", temp_url) as response:
                    response.raise_for_status()
                    self._validate_content_length(response)
                    await self._write_response(response, temp_path)
            return temp_path
        except httpx.HTTPStatusError as exception:
            temp_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"下载文件失败，HTTP 状态码为 {exception.response.status_code}"
            ) from exception
        except httpx.HTTPError as exception:
            temp_path.unlink(missing_ok=True)
            raise RuntimeError("下载文件失败，无法访问临时地址") from exception
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def _validate_url(self, temp_url: str) -> None:
        parsed_url = urlsplit(temp_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("临时下载地址必须是有效的 HTTP 或 HTTPS 地址")

    def _create_temp_path(self, temp_url: str) -> Path:
        suffix = Path(urlsplit(temp_url).path).suffix.lower()
        if len(suffix) > 16 or not suffix.replace(".", "").isalnum():
            suffix = ""

        temp_file = NamedTemporaryFile(
            prefix="pm-agent-file-",
            suffix=suffix,
            delete=False,
        )
        temp_file.close()
        return Path(temp_file.name)

    def _validate_content_length(self, response: httpx.Response) -> None:
        raw_content_length = response.headers.get("Content-Length")
        if raw_content_length and raw_content_length.isdigit():
            if int(raw_content_length) > self._max_file_size_bytes:
                raise ValueError("下载文件大小超过允许上限")

    async def _write_response(
        self,
        response: httpx.Response,
        temp_path: Path,
    ) -> None:
        downloaded_bytes = 0
        with temp_path.open("wb") as output:
            async for chunk in response.aiter_bytes():
                downloaded_bytes += len(chunk)
                if downloaded_bytes > self._max_file_size_bytes:
                    raise ValueError("下载文件大小超过允许上限")
                output.write(chunk)
