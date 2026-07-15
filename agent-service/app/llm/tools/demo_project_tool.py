"""项目概览 Demo 工具。"""
from __future__ import annotations

from app.streaming.payloads import ToolCallRecord

__all__ = ["DemoProjectTool"]


class DemoProjectTool:
    """DemoProjectTool 仅用于演示工具调用链路，不访问数据库。"""

    tool_name = "demo_query_project_overview"

    def run(self, project_id: int | None) -> ToolCallRecord:
        """返回固定项目概览，后续真实数据应通过 Java 工具 API 获取。"""
        input_data = {"project_id": project_id}
        output_data = {
            "project_id": project_id or 1,
            "project_name": "PM-Agent 演示项目",
            "status": "running",
            "task_summary": {
                "pending": 2,
                "developing": 3,
                "testing": 1,
                "done": 5,
            },
            "risk_summary": "当前 Demo 数据显示存在 2 个待处理任务，建议优先确认负责人和截止日期。",
            "data_source": "python_demo_tool",
        }
        return ToolCallRecord(tool_name=self.tool_name, input=input_data, output=output_data)
