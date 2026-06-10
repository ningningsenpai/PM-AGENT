from app.schemas.chat import ToolCallRecord


class DemoProjectTool:
    """项目概览工具 Demo。

    当前工具不调用 Java，也不访问数据库，只返回固定演示数据，帮助理解工具调用链路。
    后续正式版本应改为调用 Java 工具 API。
    """

    tool_name = "demo_query_project_overview"

    def run(self, project_id: int | None) -> ToolCallRecord:
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
