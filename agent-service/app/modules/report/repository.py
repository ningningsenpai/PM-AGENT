"""报告模块的数据访问，不调用其他模块仓储。"""

from sqlalchemy import select

from .models import ProjectReport


class ReportRepository:
    def __init__(self, session):
        self.session = session

    async def add(self, report):
        self.session.add(report)
        await self.session.flush()
        await self.session.refresh(report)
        return report

    async def reports(self, user_id, project_id, kind=None, report_id=None):
        query = select(ProjectReport).where(
            ProjectReport.user_id == user_id, ProjectReport.project_id == project_id
        )
        if kind:
            query = query.where(ProjectReport.kind == kind)
        if report_id:
            query = query.where(ProjectReport.id == report_id)
        return list(
            (
                await self.session.scalars(
                    query.order_by(ProjectReport.id.desc()).limit(20)
                )
            ).all()
        )
