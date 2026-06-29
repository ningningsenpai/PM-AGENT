"""项目文件树构建与更新服务。"""
from __future__ import annotations

import mimetypes
from pathlib import Path
from tempfile import SpooledTemporaryFile

from fastapi import UploadFile
from starlette.datastructures import Headers

from app.api.internal.minio_files import delete_project_file, update_project_file, upload_project_file
from app.project.context.indexer.tree_index import TreeIndexWriter
from app.project.context.scanner.walker import walk
from app.project.context.schemas import FileNode, ScanResult
from app.project.files.schemas import FileBusiness, FileTreeCommand, FileTreeResult, FileUploadResult
from app.project.files.service import ProjectFileService

__all__ = ["ProjectFileTreeService"]


class ProjectFileTreeService:
    """编排文件树扫描、MinIO 同步和索引写入。"""

    def __init__(self, file_service: ProjectFileService) -> None:
        self.file_service = file_service
        self.writer = TreeIndexWriter()

    async def build_tree(self, command: FileTreeCommand) -> list[FileTreeResult]:
        """首次构建文件树并上传符合规则的文件。"""
        root = Path(command.root_path).resolve()
        result = walk(root)
        response_items: list[FileTreeResult] = []

        for node in self._active_file_nodes(result):
            local_path = root / node.path
            file_info = await self._upload_local_file(local_path, command)
            node.file_info = file_info.model_dump()
            response_items.append(self._build_result(node, command.business, file_info, is_delete=False))

        self.writer.write(result, command.output_dir)
        return response_items

    async def update_tree(self, command: FileTreeCommand) -> list[FileTreeResult]:
        """更新文件树，按差异同步 MinIO 并返回变更项。"""
        root = Path(command.root_path).resolve()
        current = walk(root)
        previous = self.writer.read(command.output_dir)
        if previous is None:
            return await self.build_tree(command)

        previous_map = self._node_map(previous)
        current_map = self._node_map(current)
        response_items: list[FileTreeResult] = []

        for path, node in current_map.items():
            previous_node = previous_map.get(path)
            if previous_node is None:
                file_info = await self._upload_local_file(root / node.path, command)
                node.file_info = file_info.model_dump()
                response_items.append(self._build_result(node, command.business, file_info, is_delete=False))
                continue

            if self._node_fingerprint(previous_node) != self._node_fingerprint(node):
                old_file_info = self._load_file_info(previous_node)
                upload_file = self._upload_file_from_path(root / node.path)
                file_info = await update_project_file(
                    url_path=old_file_info.url_path,
                    file=upload_file,
                    current_user_id=command.user_id,
                    service=self.file_service,
                )
                node.file_info = file_info.model_dump()
                response_items.append(self._build_result(node, command.business, file_info, is_delete=False))
                continue

            node.file_info = previous_node.file_info

        for path, previous_node in previous_map.items():
            if path in current_map:
                continue
            old_file_info = self._load_file_info(previous_node)
            delete_project_file(
                url_path=old_file_info.url_path,
                current_user_id=command.user_id,
                service=self.file_service,
            )
            response_items.append(self._build_result(previous_node, command.business, old_file_info, is_delete=True))

        self.writer.write(current, command.output_dir)
        return response_items

    async def _upload_local_file(self, local_path: Path, command: FileTreeCommand) -> FileUploadResult:
        upload_file = self._upload_file_from_path(local_path)
        return await upload_project_file(
            project_id=command.project_id,
            business=command.business,
            file=upload_file,
            user_id=command.user_id,
            service=self.file_service,
        )

    def _upload_file_from_path(self, local_path: Path) -> UploadFile:
        content_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
        file_obj = SpooledTemporaryFile(max_size=1024 * 1024)
        with local_path.open("rb") as source:
            file_obj.write(source.read())
        file_obj.seek(0)
        return UploadFile(
            file=file_obj,
            filename=local_path.name,
            headers=Headers({"content-type": content_type}),
        )

    def _active_file_nodes(self, result: ScanResult) -> list[FileNode]:
        return [node for node in result.nodes if not node.is_dir and node.scan_status == "active"]

    def _node_map(self, result: ScanResult) -> dict[str, FileNode]:
        return {node.path: node for node in self._active_file_nodes(result)}

    def _node_fingerprint(self, node: FileNode) -> tuple:
        return (
            node.size_bytes,
            node.quick_fingerprint,
            node.content_hash,
        )

    def _load_file_info(self, node: FileNode) -> FileUploadResult:
        if not node.file_info:
            raise ValueError(f"文件缺少 MinIO 映射信息：{node.path}")
        return FileUploadResult(**node.file_info)

    def _build_result(
        self,
        node: FileNode,
        business: FileBusiness,
        file_info: FileUploadResult,
        *,
        is_delete: bool,
    ) -> FileTreeResult:
        return FileTreeResult(
            original_file_name=node.name,
            original_path=node.path,
            _is_delete=is_delete,
            business=business,
            file_info=file_info,
        )
