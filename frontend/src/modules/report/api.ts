import { request } from '@/api/http'
import { useMock } from '@/mock'
export type ReportKind='development'|'risk'
export interface Report {id:string;projectId:string;runId:string;kind:ReportKind;markdown:string;sourceVersions:Record<string,unknown>;evidence:Record<string,unknown>[];createdAt:string}
export function listReports(projectId:string,kind?:ReportKind) {
  if(useMock)throw new Error('报告中心需要连接真实服务，请关闭演示模式')
  return request<Report[]>({url:`/api/v1/projects/${projectId}/reports`,params:kind?{kind}:undefined})
}
export async function getReport(projectId:string,id:string) {
  if(useMock)throw new Error('报告中心需要连接真实服务，请关闭演示模式')
  const result=await request<Report[]>({url:`/api/v1/projects/${projectId}/reports/${id}`})
  if(!result.length)throw new Error('报告不存在或不属于当前项目')
  return result[0]
}

