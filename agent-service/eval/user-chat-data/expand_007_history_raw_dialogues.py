"""扩展 007 历史对话 CSV 到 200 条。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TARGET_FILE = BASE_DIR / "007-merged_001_003_history_raw_dialogues.csv"
PROJECT_ID = "7147375873232998401"
PROJECT_NAME = "PM-Agent 智能项目管理 Agent 平台"

HEADERS = [
    "raw_id", "global_index", "project_id", "project_name", "turn_no", "module", "memory_type",
    "business_type", "status", "user_message", "assistant_message", "memory_text", "entities",
    "facts", "decisions", "risks", "supersedes_raw_id", "value_score", "expected_retrieval_weight",
]

MODULE_ORDER = [
    "Agent 编排", "Agent 工具调用", "Figma 设计稿", "Git 管理", "RAG 知识库", "Skill 规范",
    "中间件策略", "任务管理", "前端工程", "后端架构", "开发规划", "技术选型", "接口规范",
    "数据模型", "文档规范", "模型策略", "模块边界", "注释规范", "设计风格", "项目管理", "风险分析",
]
MODULE_INDEX = {name: index for index, name in enumerate(MODULE_ORDER)}
BUSINESS_TYPE_MAP = {
    "bug": "risk",
    "learning": "decision",
}


def js(items: list[str]) -> str:
    return json.dumps(items, ensure_ascii=False)


def infer_memory_type(business_type: str) -> str:
    if business_type in {"tool_usage"}:
        return "procedural"
    if business_type in {"task", "progress", "status_update"}:
        return "episodic"
    return "semantic"


def make_record(
    module: str,
    business_type: str,
    user_message: str,
    assistant_message: str,
    entities: list[str],
    facts: list[str],
    decisions: list[str] | None = None,
    risks: list[str] | None = None,
    value_score: str = "0.86",
    weight: str = "high",
    status: str = "active",
) -> dict[str, str]:
    memory_text = f"项目：{PROJECT_NAME}。模块：{module}。用户问题：{user_message}。LLM回答：{assistant_message}"
    return {
        "raw_id": "",
        "global_index": "",
        "project_id": PROJECT_ID,
        "project_name": PROJECT_NAME,
        "turn_no": "",
        "module": module,
        "memory_type": infer_memory_type(business_type),
        "business_type": business_type,
        "status": status,
        "user_message": user_message,
        "assistant_message": assistant_message,
        "memory_text": memory_text,
        "entities": js(entities),
        "facts": js(facts),
        "decisions": js(decisions or []),
        "risks": js(risks or []),
        "supersedes_raw_id": "",
        "value_score": value_score,
        "expected_retrieval_weight": weight,
    }


def build_generated_records() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []

    def add(module: str, business_type: str, user: str, answer: str, entities: list[str], facts: list[str], decisions: list[str] | None = None, risks: list[str] | None = None, score: str = "0.86", weight: str = "high") -> None:
        records.append(make_record(module, business_type, user, answer, entities, facts, decisions, risks, score, weight))

    # Skill 规范：多轮链
    skill_qas = [
        ("这个项目为什么要拆这么多 skill，不能一个总 skill 全部管了吗？", "不建议只用一个总 Skill。PM-Agent 的协作范围横跨产品、后端、前端、数据模型、流程、Agent、测试和文档，如果全部交给一个 Skill，会导致触发边界模糊、输出风格不稳定，也不利于后续维护。项目早期把 Skill 拆开，是为了让每个设计问题先进入正确边界，再由对应 Skill 产出可落地方案。", ["Skill", "模块边界", "产品设计"], ["项目 Skill 需要按职责拆分，避免一个总 Skill 覆盖所有设计问题"], ["正式协作采用多 Skill 分工"]),
        ("那正式 skill 和 BaseSkill-CN 到底怎么分？", "正式开发调用以 `.claude/skills/` 下的英文 Skill 为准，`BaseSkill-CN/` 只是中文参考副本，方便对照审阅和人工理解。这样做是因为 Claude Code 的 Skill 触发描述更适合用英文保持稳定，而中文副本可以帮助用户确认语义不偏。实际执行时不要把中文参考 Skill 当成触发来源。", [".claude/skills", "BaseSkill-CN", "Skill 触发"], ["正式 Skill 位于 .claude/skills，BaseSkill-CN 仅作中文参考"], ["开发调用优先使用英文正式 Skill"]),
        ("如果我要设计一个页面，应该走产品 skill 还是前端 skill？", "如果还没确定页面目标、角色、MVP 范围和验收标准，应该先走 `pm-agent-product-designer`；如果产品边界已经明确，只需要拆页面结构、组件、路由、Pinia 状态和 Naive UI 交互，则进入 `pm-agent-frontend-builder`。这能避免前端直接实现一个还没有被产品定义清楚的页面。", ["pm-agent-product-designer", "pm-agent-frontend-builder", "页面设计"], ["产品边界未定时先使用产品 Skill，页面实现阶段再使用前端 Skill"], ["页面设计先产品后前端"]),
        ("Agent 相关的设计是不是都归 llm orchestrator？", "大部分 Agent 编排、Prompt、模型路由、工具调用、Trace 和 Java-Python 协作确实归 `pm-agent-llm-orchestrator`。但如果涉及工具背后的业务表、权限、接口状态流转，仍要和 backend architect、data modeler、workflow designer 协作。Agent Skill 负责推理和编排边界，不应该替代 Java 后端的业务规则。", ["pm-agent-llm-orchestrator", "工具调用", "Trace", "Java 后端"], ["Agent 编排归 LLM Orchestrator，但业务规则仍由后端和数据模型约束"], ["Agent 不直接替代业务后端"]),
        ("文档类需求是不是都让 doc-writer 处理？", "大多数需求文档、技术方案、API 文档、模块设计和 README 都可以由 `pm-agent-doc-writer` 统一组织。但它不负责凭空决定产品范围，也不负责替代 backend/frontend/Agent 的技术判断。正确流程是先由对应设计 Skill 确认方案，再由 doc-writer 归档为中文 Markdown。", ["pm-agent-doc-writer", "Markdown", "模块设计文档"], ["doc-writer 负责组织文档，不替代产品和技术决策"], ["设计结论先确认再沉淀为文档"]),
        ("新增 skill 的时候需要注意什么？", "新增 Skill 要先明确触发场景、目标、边界和不能做的事情，不能只写一个泛泛的能力描述。项目模板要求 Skill 有清晰的 workflow、输出格式和需要用户确认的边界。尤其是 PM-Agent 这种多模块项目，新增 Skill 要避免和已有 Skill 重叠，否则后续触发会混乱。", ["Skill 模板", "触发场景", "边界"], ["新增 Skill 需要定义触发场景、目标、workflow 和边界"], ["新增 Skill 前应避免和已有 Skill 重叠"]),
        ("skill 会不会限制你发挥？", "会有一定限制，但这是有意设计的。Skill 的目的不是限制能力，而是把输出限定在项目已经确认的技术栈、文档风格、业务边界和阶段目标内。比如前端 Skill 会保护 Warm Linear 风格，后端 Skill 会保护 Spring Boot 分层和 Sa-Token 选择，LLM Skill 会保护 Agent 不直接操作数据库的原则。", ["Skill 限制", "技术栈", "业务边界"], ["Skill 用于约束输出不要偏离项目既定技术栈和阶段边界"], ["Skill 约束优先服务稳定性"]),
        ("那多个 skill 互相冲突时听谁的？", "优先级应按问题本身归属来判断。产品范围先由 product designer 定，数据字段由 data modeler 定，后端接口由 backend architect 定，前端页面由 frontend builder 定，Agent 编排由 llm orchestrator 定。如果冲突涉及项目根规范和 CLAUDE.md，则以项目根规范为上位约束。", ["Skill 冲突", "CLAUDE.md", "职责归属"], ["多个 Skill 冲突时应按问题归属和项目根规范确定优先级"], ["项目根规范优先于单个 Skill"]),
        ("skill 生成的内容能不能直接当最终实现？", "不能默认当最终实现。Skill 输出通常是设计、规范或实现计划，仍需要结合当前代码、数据表、接口和阶段目标校验。特别是后置能力、未来演进和可选方案，文档中必须标注为计划或待确认，不能写成已经完成。", ["Skill 输出", "待确认", "实现计划"], ["Skill 输出需要结合当前代码和阶段目标校验，不能直接视为已实现"], [], ["把未实现能力写成已完成会污染文档和测试数据"]),
        ("如果只是问一个小问题，也要触发 skill 吗？", "不一定。Skill 适合有明确领域边界的设计、文档、架构或实现规划。如果只是简单解释概念或查一个文件，直接回答即可；如果问题涉及 PM-Agent 的产品边界、后端分层、前端视觉、Agent 编排或文档规范，就应该使用对应项目 Skill 保持一致性。", ["Skill 触发", "简单问题", "项目规范"], ["简单解释不一定触发 Skill，领域设计问题应触发对应 Skill"], []),
        ("中文参考 skill 要不要继续维护？", "可以维护，但定位要清楚。中文参考 Skill 适合用户自己审阅、对照和教学，不作为 Claude Code 正式触发来源。如果英文正式 Skill 有调整，中文副本可以同步更新，但不能反过来让中文副本覆盖正式 Skill 的行为描述。", ["中文参考 Skill", "英文正式 Skill", "维护边界"], ["中文参考 Skill 只用于审阅和对照，不作为正式触发来源"], ["正式行为以英文 Skill 为准"]),
        ("Skill 文档里要不要写很多项目历史？", "不建议。Skill 文档应该写触发场景、目标、边界、workflow 和输出要求，不要写大量历史过程。项目历史和阶段记录应该放在 docs 或 Git 记录中，Skill 只保留能影响未来行为的稳定规则。", ["Skill 文档", "项目历史", "workflow"], ["Skill 文档应保留稳定规则，不应堆积历史过程"], []),
        ("哪些 skill 是现在最优先完善的？", "项目规范里最优先完善的是 `pm-agent-backend-architect`、`pm-agent-frontend-builder` 和 `pm-agent-llm-orchestrator`。原因是当前平台的核心闭环依赖 Java 业务主链路、Vue 前端界面和 Python Agent 服务，三者决定了项目可运行、可演示和可扩展的基础。", ["pm-agent-backend-architect", "pm-agent-frontend-builder", "pm-agent-llm-orchestrator"], ["当前最优先完善的三个 Skill 是后端、前端和 LLM 编排 Skill"], ["优先保障核心开发链路"]),
        ("skill 里面为什么一直强调人工确认？", "因为 PM-Agent 的 Agent 后续会涉及任务状态、风险创建、权限、通知等高影响操作。Skill 规范提前把删除、权限变更、外部通知、Agent 写业务数据等列为高风险场景，要求通过前端动作卡片和用户确认后再调用 Java 工具 API。这样能避免 Agent 自行修改业务状态。", ["人工确认", "高风险操作", "工具 API"], ["高风险 Agent 操作必须人工确认，不能由 Agent 直接执行"], ["删除、权限、通知和业务写操作都需要确认"], ["绕过人工确认会造成业务状态误改"]),
        ("如果以后项目变大，skill 怎么演进？", "可以按模块继续拆，但要避免过早细分。当前 9 个项目级 Skill 已覆盖产品、后端、前端、数据、流程、LLM、测试、文档和成本。后续只有当某类问题频繁出现且现有 Skill 边界不够清晰时，才新增或拆分 Skill。", ["Skill 演进", "模块拆分", "边界"], ["Skill 演进应基于频繁场景和边界不足，不应过早细分"], []),
        ("那本次生成数据要怎么记录 skill 相关内容？", "这类历史对话可以归到 `Skill 规范` 模块，`business_type` 多数用 `decision`、`architecture` 或 `prompt`。如果是操作方法，比如新增 Skill 模板怎么填，可以用 `procedural/tool_usage`；如果是边界结论，则用 `semantic/decision` 更合适。", ["Skill 规范", "business_type", "memory_type"], ["Skill 相关历史记录按主题分为决策、架构或操作方法"], ["边界结论使用 semantic，操作步骤使用 procedural"]),
    ]
    for user, answer, entities, facts, decisions, *rest in skill_qas:
        risks = rest[0] if rest else None
        add("Skill 规范", "decision", user, answer, entities, facts, decisions, risks, score="0.88")

    # 技术栈与框架多轮链
    tech_qas = [
        ("整体技术栈现在是不是就定 Java + Python + Vue？", "是的，总体架构已经定为 Vue 3 + TypeScript 前端、Java Spring Boot 3 业务主系统、Python FastAPI Agent 服务。这个拆分是为了让 Java 承担确定性业务逻辑、权限和持久化，Python 专注 Prompt、模型调用、工具编排和后续 RAG，前端负责工作台、看板和 Agent 结果展示。", ["Vue 3", "Spring Boot 3", "FastAPI"], ["PM-Agent 整体架构采用 Vue 前端、Java 后端和 Python Agent 服务"], ["整体技术栈采用 Java + Python + Vue"]),
        ("为什么前端不直接用 React + Ant Design？", "React + Ant Design 是备选，但当前项目是单人 + AI 协作，Vue 3 单文件组件更直观，Naive UI 的视觉更现代，TypeScript 支持也够好。Ant Design 更偏传统企业后台，和项目想要的 Warm Linear 工作台风格不完全一致，所以第一版不选。", ["React", "Ant Design", "Vue 3", "Naive UI"], ["Vue 3 + Naive UI 更符合单人开发和 Warm Linear 视觉方向"], ["第一版前端不采用 React + Ant Design"]),
        ("Element Plus 不也是 Vue 生态吗，为什么不用？", "Element Plus 确实成熟，但视觉比较传统，默认后台感强。PM-Agent 的页面希望更像现代项目工作台，而不是传统表格后台，所以文档中明确偏向 Naive UI。Naive UI 组件 API 清晰、样式更轻，后续和自定义视觉结合也更顺手。", ["Element Plus", "Naive UI", "Vue"], ["Element Plus 成熟但视觉偏传统后台，Naive UI 更贴合项目偏好"], ["第一版组件库采用 Naive UI"]),
        ("Pinia 和 Vuex 这里还有必要纠结吗？", "不需要再纠结。Vue 3 生态下 Pinia 已经是官方推荐的新状态管理方案，类型推导更友好，代码也更轻。Vuex 更适合旧项目迁移，本项目从零开始，没有必要引入 Vuex 的额外负担。", ["Pinia", "Vuex", "Vue 3"], ["Pinia 是 Vue 3 项目更合适的状态管理方案"], ["状态管理采用 Pinia"]),
        ("后端为什么不用 Spring Security？", "Spring Security 能力很强，但配置复杂，适合企业 OAuth2、SSO 和复杂安全体系。PM-Agent 第一版只需要基础登录、权限注解、会话和简单角色控制，Sa-Token 代码量少、上手快、权限表达直观，更符合单人开发效率。", ["Spring Security", "Sa-Token", "认证授权"], ["Sa-Token 比 Spring Security 更适合第一版轻量认证授权"], ["后端认证采用 Sa-Token"]),
        ("裸 JWT 会不会更简单？", "裸 JWT 看起来简单，但实际要自己处理登录、刷新、踢人、黑名单、会话失效和权限注解。Sa-Token 已经提供这些能力，且和 Spring Boot 集成成本低。为了减少自研安全逻辑，第一版不裸用 JWT。", ["JWT", "Sa-Token", "会话管理"], ["裸 JWT 需要自研大量会话和权限逻辑，第一版不采用"], ["不裸用 JWT"]),
        ("ORM 为什么选 MyBatis Plus，不选 JPA？", "MyBatis Plus 更适合需要控制 SQL 的业务系统，后续项目任务、风险扫描、统计查询和复杂筛选都可能需要手写或调优 SQL。JPA 抽象更高，但复杂查询可控性不如 MyBatis Plus。为了后续可维护和可调优，后端选 MyBatis Plus。", ["MyBatis Plus", "JPA", "SQL"], ["MyBatis Plus 在复杂查询和 SQL 调优上更可控"], ["ORM 采用 MyBatis Plus"]),
        ("Python Agent 为什么不用 LangChain 一把梭？", "LangChain 抽象很多，适合复杂 Agent 生态，但第一版 PM-Agent 只需要模型调用、Prompt 模板、流式输出和少量工具编排。直接上 LangChain 会增加学习成本和调试复杂度。文档里决定先自研轻量编排，必要时再引入 LangChain 或 LlamaIndex。", ["LangChain", "LlamaIndex", "FastAPI", "Agent 编排"], ["第一版 Agent 编排先自研轻量方案，LangChain 后置评估"], ["不在第一版直接引入 LangChain"]),
        ("FastAPI 是不是只是因为 Python 方便调模型？", "不只是方便调模型。FastAPI 异步友好，Pydantic 校验天然适合结构化输入输出，和 Agent 的 Prompt、模型响应、工具调用 schema 都很契合。它也能和 Java 后端通过 HTTP/JSON 清晰协作，不会污染 Java 业务主链路。", ["FastAPI", "Pydantic", "Agent 服务"], ["FastAPI 适合 Python Agent 服务的异步接口和结构化校验"], ["Python Agent 服务采用 FastAPI + Pydantic"]),
        ("Knife4j 和 Markdown API 文档是不是重复？", "不重复。Knife4j 更适合接口调试和浏览，Markdown API 文档更适合长期维护接口约定、请求头、幂等、错误码和 traceId 说明。项目规范要求不能只依赖 Knife4j，关键 API 仍要有 Markdown 文档，尤其是跨 Java、Python、前端协作的接口。", ["Knife4j", "Markdown API 文档", "接口规范"], ["Knife4j 用于调试，Markdown 文档用于长期接口约定"], ["API 文档不能只依赖 Knife4j"]),
        ("那技术栈后面还能换吗？", "核心技术栈不建议轻易换。项目规范明确不主动改动已确定的 Sa-Token、Naive UI 等选型。后续可以在边界内增强，比如引入 Redis、RabbitMQ、RAG、监控，但不应因为短期偏好重构前端框架或后端认证体系。", ["技术栈", "Sa-Token", "Naive UI"], ["已确定技术选型不应轻易替换，后续以增强为主"], ["技术栈演进以增强为目标，不重构核心"]),
        ("现在记录到 CSV 里，技术选型这类应该算什么类型？", "技术栈选择、框架取舍和不选方案原因都属于稳定结论，适合标记为 `semantic`。如果是“怎么启动前端”“怎么配置环境变量”这类操作步骤，再标记为 `procedural`。业务类型可以用 `architecture` 或 `decision`，方便后续按选型问题检索。", ["semantic", "procedural", "architecture", "decision"], ["技术选型类记录通常是 semantic，业务类型可用 architecture 或 decision"], []),
    ]
    for user, answer, entities, facts, decisions, *rest in tech_qas:
        risks = rest[0] if rest else None
        add("技术选型", "architecture", user, answer, entities, facts, decisions, risks, score="0.9")

    # 后端架构补充链
    backend_qas = [
        ("后端包结构是不是按模块拆就行？", "后端包结构不是简单按文件类型堆 controller、service、mapper，而是以 `com.ning.pm` 为根，在 `modules` 下按 auth、user、project、requirement、task、iteration、risk、report、agent 等业务模块拆分。common 放统一响应、异常和工具，infrastructure 放缓存、消息、外部服务和 Agent 客户端，避免业务层直接依赖外部细节。", ["com.ning.pm", "modules", "infrastructure"], ["后端按业务模块拆分，基础设施能力放 infrastructure"], ["后端采用模块化包结构"]),
        ("Java 后端和 Python Agent 的边界再说清楚一点？", "Java 后端是业务事实主源，负责权限、数据一致性、工具 API、幂等和状态日志。Python Agent 只负责模型编排、Prompt、工具选择、流式输出和 Trace 协作。Agent 不能直接操作数据库，所有业务变更都必须回到 Java 工具 API。", ["Java 后端", "Python Agent", "工具 API", "数据库"], ["Java 是业务事实主源，Python 负责 Agent 编排"], ["Agent 不直接操作数据库"]),
        ("后端接口路径和响应格式有什么固定要求？", "接口路径统一使用 `/api/v1/<module>/<resource>` 风格，响应结构统一包含 `code`、`message`、`data` 和 `traceId`。写接口还要考虑 `X-Idempotency-Key`，跨前端、Java、Python 的调用要保持 traceId 贯通，便于排查 Agent 和工具调用链路。", ["/api/v1", "traceId", "X-Idempotency-Key"], ["接口统一使用 /api/v1 路径和 code/message/data/traceId 响应结构"], ["后端接口必须保持统一响应和 traceId"]),
        ("后端第一阶段要不要把审计日志做完整？", "不建议。开发规划里审计日志属于第 7 阶段或更早增强，第 1 阶段只保留注解和 AOP 空实现的入口即可。第一阶段目标是登录、项目、任务和看板闭环，完整审计会拖慢主线。Agent Trace 不在这个延期范围内，按 Agent 阶段单独落地。", ["审计日志", "第 1 阶段", "Agent Trace"], ["完整审计日志不属于第 1 阶段，Agent Trace 按第 3 阶段落地"], ["第 1 阶段只保留审计入口，不做完整审计"]),
        ("后端测试接口的时候是不是直接调 Python 更快？", "如果只想验证模型是否能返回，可以直接调 Python；但如果目标是验证项目真实链路，就应该走 Java 的 `/api/v1/agent/chat`。因为 Java 负责鉴权、上下文组装、conversationId、历史消息和落库，绕过 Java 会漏掉权限和持久化链路。", ["/api/v1/agent/chat", "鉴权", "落库"], ["验证真实 Agent 对话链路应走 Java 后端入口"], ["测试落库不能绕过 Java"]),
        ("MapStruct 和 Hutool 是不是都必须用？", "它们是工具选型，不是每个地方都必须用。MapStruct 适合 DTO、VO、Entity 之间的结构映射，Hutool 适合常用工具能力。原则是减少样板代码，但不能为了使用工具而引入不必要抽象。简单映射可以直接写，复杂重复映射再考虑 MapStruct。", ["MapStruct", "Hutool", "DTO"], ["MapStruct 和 Hutool 是辅助工具，不应为了工具而过度抽象"], []),
        ("后端注释要写到什么程度？", "项目规范要求关键类和方法有中文注释，复杂业务逻辑解释为什么这么做，而不是复述代码做了什么。普通 getter、简单 CRUD 不需要堆注释；涉及权限边界、状态流转、幂等、防重复提交、Agent 高风险动作时，注释要说明约束和原因。", ["中文注释", "复杂业务逻辑", "幂等"], ["关键类和复杂业务逻辑需要中文注释并解释原因"], ["注释用于解释非显而易见的约束"]),
        ("如果接口报错，错误提示要用中文吗？", "是的，项目规范明确错误提示使用中文。统一异常处理应返回中文 message，并带 traceId 方便排查。内部日志可以保留技术细节，但给前端和用户的错误信息要可理解，不要直接暴露底层异常栈。", ["错误提示", "中文", "traceId"], ["接口错误提示使用中文并返回 traceId"], []),
        ("后端是不是所有列表都要分页？", "项目管理 MVP 阶段要求列表统一支持分页、排序和过滤。第一阶段可以先保证项目和任务列表可用，但在接口设计上要预留分页参数，避免后续需求、迭代、风险列表再重新改接口风格。", ["分页", "排序", "过滤", "列表接口"], ["项目管理列表应统一支持分页、排序和过滤"], ["接口设计预留分页能力"]),
        ("状态日志和审计日志怎么区分？", "状态日志服务于业务流程复盘，比如任务从待处理变为开发中、风险从打开到关闭。审计日志记录谁在什么时候对什么资源做了什么关键操作，更偏安全和合规。第 1 阶段任务状态变更必须写 `pm_task_status_log`，完整审计日志后置。", ["状态日志", "审计日志", "pm_task_status_log"], ["状态日志记录业务状态流转，审计日志记录关键操作行为"], []),
        ("后端架构这些记录放 CSV 时 module 用什么？", "如果讨论的是包结构、接口规范、认证、权限、异常处理、Java-Python 调用，都可以归到 `后端架构`。如果更偏状态流转或任务风险流程，可以归到 `模块边界` 或 `项目管理`。这样后续检索“后端怎么分层”时能集中召回。", ["后端架构", "模块边界", "项目管理"], ["后端相关历史记录应按架构、模块边界或项目管理区分"], []),
        ("后端第一阶段是不是只要用户和任务就够？", "不完全够。第 1 阶段的闭环是登录、看到项目、创建任务、看板查看任务状态，所以至少需要用户、项目、项目成员、任务和任务状态日志。只做用户和任务会缺少项目上下文，也无法体现 PM-Agent 的项目管理主线。", ["用户", "项目", "任务", "任务状态日志"], ["第 1 阶段最小闭环包括用户、项目、任务和任务状态日志"], ["第 1 阶段不只做用户和任务"]),
    ]
    for user, answer, entities, facts, decisions, *rest in backend_qas:
        risks = rest[0] if rest else None
        add("后端架构", "architecture", user, answer, entities, facts, decisions, risks, score="0.89")

    # Python Agent 与模型策略链
    agent_qas = [
        ("Agent 第一版到底是聊天还是能操作业务？", "第 3 阶段的第一版 Agent 主要是项目自然语言问答、流式输出和会话 Trace，不应该直接操作业务数据。到第 4 阶段才引入工具调用，比如查询项目概览、任务列表、延期任务、人员负载、拆分需求和生成周报。业务写操作还必须通过人工确认和 Java 工具 API。", ["Agent 对话", "工具调用", "第 3 阶段", "第 4 阶段"], ["第 3 阶段 Agent 以问答为主，第 4 阶段才引入工具调用"], ["第一版 Agent 不直接写业务数据"]),
        ("为什么 Agent 不直接连数据库查询？", "因为 Agent 输出不稳定，直接连数据库会绕过 Java 的权限、幂等、状态日志和审计边界。PM-Agent 的原则是 Agent 负责推理和编排，Java 后端负责确定性业务逻辑和数据主源。即使 Agent 要查询任务或风险，也应该通过受控工具 API。", ["Agent", "数据库", "Java 工具 API"], ["Agent 不直接操作数据库，业务查询和变更通过 Java 工具 API"], ["Agent 数据访问必须走工具 API"], ["Agent 直连数据库会绕过权限和审计"]),
        ("模型默认用 DeepSeek，会不会影响质量？", "默认 DeepSeek 是成本和效果的折中。普通意图识别、项目问答、草稿生成可以用 DeepSeek；复杂推理、关键风险判断、长文档终稿或重要决策再升级 Claude 或 GPT。这样符合月度运行成本 200-600 元的约束，也避免所有请求都走高成本模型。", ["DeepSeek", "Claude", "GPT", "模型路由"], ["运行时默认 DeepSeek，复杂任务再升级 Claude 或 GPT"], ["采用低成本默认模型加关键任务升级策略"]),
        ("Prompt 要不要都写在代码里？", "不建议散落在代码里。Agent Prompt 应该有模板管理、命名或编号，并在 Trace 中记录模板变量和最终上下文。这样后续调试回答质量、比较模型效果、做成本优化时，才能知道是哪一个 Prompt 版本影响了输出。", ["Prompt 模板", "Trace", "模型调试"], ["Prompt 模板需要可追踪，不应散落在代码里"], ["Prompt 模板需要编号或命名"]),
        ("Trace 到底记录什么？", "Trace 应记录用户输入、Prompt、模型信息、token 使用、工具调用入参出参、耗时、错误、最终输出、人工确认结果和 traceId。开发和调优阶段要足够完整，敏感字段需要脱敏，超大工具输出可以截断并记录 truncated 标记。", ["Trace", "tool_calls", "token usage", "traceId"], ["Agent Trace 需要记录输入、Prompt、模型、工具调用、输出和人工确认"], ["Trace 保留 3 个月并注意脱敏"]),
        ("流式输出第一版必须做吗？", "项目 Agent 设计里把流式输出列为第一版要求，因为用户和 Agent 对话时等待模型完整返回体验较差。流式输出可以先只做回答文本流，工具调用过程可在后续可视化。实现时 Python 侧支持 SSE，前端负责流式展示。", ["流式输出", "SSE", "Agent 助手页"], ["Agent 第一版需要流式输出以改善对话体验"], ["Python 侧支持 SSE，前端展示流式回答"]),
        ("Agent 工具失败了能不能让模型自己兜底？", "不能假装成功。工具失败时 Agent 应明确告诉用户失败原因，并包含 traceId，Trace 中记录工具名、入参、错误和耗时。模型可以解释失败和建议下一步，但不能编造查询结果或说业务修改已经完成。", ["工具失败", "traceId", "Trace"], ["工具失败时 Agent 不能假装成功，必须说明失败并记录 Trace"], [], ["模型编造工具结果会破坏业务可信度"]),
        ("高风险动作具体有哪些？", "删除、不可逆操作、权限和成员变更、外部通知发布、Agent 写业务数据都属于高风险动作。Agent 可以生成建议或待确认动作卡片，但必须由用户确认后，再由 Java 工具 API 执行并写入 Trace 和状态日志。", ["高风险动作", "人工确认", "动作卡片"], ["删除、权限变更、外部通知和业务写操作需要人工确认"], ["高风险动作走 Agent 建议 -> 用户确认 -> Java 工具 API"]),
        ("Agent 输出结构化是不是每次都要 JSON？", "不需要每次都 JSON。普通聊天回答可以自然语言，但关键业务结果，如需求拆解、风险分析、周报结构、工具调用参数和高风险动作建议，必须用 Pydantic 或 JSON Schema 校验。结构化的目的不是形式统一，而是防止关键字段凭空生成或格式漂移。", ["JSON Schema", "Pydantic", "结构化输出"], ["关键业务结果需要结构化校验，普通聊天不必强制 JSON"], []),
        ("RAG 是不是第 3 阶段就能一起做？", "不建议。开发规划明确 RAG 知识库在第 6 阶段，引入 MinIO、Qdrant 或 pgvector、文档解析、切片、向量化和重排序。第 3 阶段只做 Agent 对话和 Trace，最多预留接口和术语，不要提前把完整 RAG 链路压进第一版。", ["RAG", "第 6 阶段", "MinIO", "Qdrant"], ["完整 RAG 知识库属于第 6 阶段，第 3 阶段只预留接口和术语"], ["RAG 不提前完整实现"]),
    ]
    for user, answer, entities, facts, decisions, *rest in agent_qas:
        risks = rest[0] if rest else None
        add("Agent 编排", "architecture", user, answer, entities, facts, decisions, risks, score="0.91")

    # 中间件多轮链 18
    middleware_qas = [
        ("中间件是不是先都写进 docker-compose 比较省事？", "不建议默认全部启用。项目规范强调按阶段引入，第 1 阶段只需要 MySQL 支撑用户、项目、任务等业务表。Redis、RabbitMQ、MinIO、Qdrant 或 pgvector 都应在对应阶段再加入或启用，否则会让本地启动、排错和成本控制变复杂。", ["Docker Compose", "MySQL", "Redis", "RabbitMQ"], ["中间件按阶段引入，第一阶段默认只启用 MySQL"], ["不提前默认启动所有中间件"]),
        ("MySQL 为什么是第一个中间件？", "因为第 1 阶段目标是登录、项目、任务和看板最小闭环，这些都需要稳定业务数据存储。MySQL 工具链成熟，和 Spring Boot、MyBatis Plus、Flyway 组合稳定，适合单人项目快速落地。", ["MySQL", "第 1 阶段", "业务存储"], ["MySQL 支撑第 1 阶段用户、项目、任务等业务表"], ["第 1 阶段主数据库采用 MySQL 8"]),
        ("Redis 是不是登录一开始就必须上？", "不一定。第 1 阶段可以先用基础会话方案跑通登录和任务闭环，Redis 规划在第 2 阶段引入，用于 Sa-Token 会话、缓存、限流和项目概览缓存。这样能避免第一阶段同时处理数据库、缓存和权限联调的复杂度。", ["Redis", "Sa-Token", "缓存"], ["Redis 规划在第 2 阶段用于会话、缓存和限流"], ["Redis 不强制进入第 1 阶段"]),
        ("RabbitMQ 是不是风险分析前就可以先加？", "不建议提前加。RabbitMQ 主要服务第 5 阶段的异步任务、通知和风险扫描。第 1 到第 4 阶段的主线更关注业务闭环、Agent 对话和工具调用，提前引入消息队列会增加部署和问题定位成本。弱异步场景可以先用 Spring 内置异步或定时任务过渡。", ["RabbitMQ", "风险分析", "异步任务"], ["RabbitMQ 属于第 5 阶段，用于异步任务、通知和风险扫描"], ["RabbitMQ 不提前进入 MVP"]),
        ("MinIO 是不是附件功能一开始就需要？", "MinIO 规划在第 6 阶段引入，主要用于文档、附件和报告文件。第 1 阶段没有文档管理和知识库能力，不需要先上对象存储。早期如果只有少量演示文件，可以先不接文件系统，避免为了未来能力增加当前复杂度。", ["MinIO", "文档", "附件", "报告"], ["MinIO 在第 6 阶段用于文档、附件和报告文件"], ["第一阶段不引入 MinIO"]),
        ("Qdrant 和 pgvector 选哪个？", "文档里保留了 Qdrant 或 pgvector 两种方向。单人项目早期可优先评估 pgvector，因为一个数据库能同时承载业务和向量，运维简单；文档量增长、检索能力要求更高时再考虑 Qdrant。无论选哪个，都不在第 1 到第 5 阶段作为默认能力。", ["Qdrant", "pgvector", "向量检索"], ["向量库在第 6 阶段引入，Qdrant 和 pgvector 都保留评估空间"], ["向量库不进入前 5 阶段"]),
        ("那现在做 RAG 测试用了 Qdrant，会不会和规划冲突？", "不冲突，但要区分实验和产品化。当前 eval/rag 下的 Qdrant 是离线评测脚本，用来验证 embedding 和召回效果，不等于第 6 阶段的正式 RAG 知识库已经上线。正式产品能力仍要按文档管理、切片、权限、引用来源和 Trace 设计完整落地。", ["RAG 测试", "Qdrant", "第 6 阶段"], ["离线 RAG 评测使用 Qdrant 不代表正式 RAG 能力提前上线"], ["实验代码和产品化能力区分管理"]),
        ("Elasticsearch 要不要作为搜索默认方案？", "不建议作为默认。Elasticsearch 在文档里是可选后置能力，主要用于全文检索或更复杂搜索场景。早期可以依靠数据库查询和后续向量检索，只有当文本量、搜索体验和复杂查询都达到需要时，再评估 ES。", ["Elasticsearch", "全文检索", "后置能力"], ["Elasticsearch 是可选后置，不是第一版默认中间件"], []),
        ("Prometheus 和 Grafana 要不要现在一起配？", "不建议。Prometheus + Grafana 属于后期监控能力。第一版可以先用应用日志、traceId 和基础健康检查定位问题。等系统有稳定运行环境、接口流量和异步任务后，再引入指标采集和可视化看板更合适。", ["Prometheus", "Grafana", "监控"], ["Prometheus 和 Grafana 属于后期监控能力"], []),
        ("中间件边界是不是都由 backend 管？", "不完全。MySQL、Redis、RabbitMQ 等和业务一致性、会话、异步任务密切相关，主要由后端负责；MinIO 和向量库会同时影响 Agent、文档管理和 RAG；监控会横跨 Java、Python 和部署。设计时应明确谁是主责模块，而不是让所有模块都直接操作中间件。", ["中间件边界", "后端", "Agent", "部署"], ["中间件主责需按用途划分，不应被所有模块直接操作"], []),
        ("如果中间件后置，文档里还要不要提前写？", "要写阶段规划和边界，但不要写成已完成实现。比如 `docs/02-技术选型.md` 可以说明 RabbitMQ 第 5 阶段引入、MinIO 和向量库第 6 阶段引入，Docker Compose 可以预留结构，但未到阶段的中间件不得默认启动。", ["阶段规划", "Docker Compose", "中间件"], ["后置中间件可以写规划和边界，但不能写成已实现"], []),
        ("单人项目为什么这么强调中间件克制？", "因为单人 + AI 协作的瓶颈不是能不能堆技术，而是能否持续完成可演示闭环。每多一个中间件，就多一套启动、配置、数据、故障和学习成本。项目采用每阶段最多引入 1 到 2 个新技术点，就是为了避免节奏失控。", ["单人开发", "中间件克制", "阶段引入"], ["中间件克制是为了控制单人开发节奏和调试成本"], ["每阶段最多引入 1 到 2 个新技术点"]),
        ("Redis、RabbitMQ、MinIO 都后置，会不会影响架构扩展？", "不会，只要接口和模块边界提前留好。第一版先跑通业务主线，后续可以在 infrastructure 层接入缓存、消息和文件存储，不需要推翻核心业务表和接口。文档也强调后续阶段以增强为目标，不重构核心。", ["infrastructure", "缓存", "消息", "文件存储"], ["后置中间件通过 infrastructure 层增强，不应推翻核心业务"], ["后续阶段只增不改核心"]),
        ("本地开发是不是所有中间件都用 Docker？", "项目规划中 Docker 容器主要承载中间件，Spring Boot 后端和 Vue 前端本机运行，便于断点调试和热更新。第 1 阶段只默认启动 MySQL，后续 Redis、RabbitMQ、MinIO、向量库按阶段加入 Docker Compose。", ["Docker", "本地开发", "MySQL"], ["本地 Docker 用于中间件，后端和前端本机运行便于调试"], []),
        ("中间件选型记录放 CSV 里算 semantic 还是 procedural？", "如果记录的是为什么选、什么时候引入、边界是什么，属于 `semantic/decision` 或 `semantic/architecture`。如果记录的是怎么启动 Docker、怎么查看 Qdrant、怎么配置环境变量，则属于 `procedural/tool_usage`。", ["semantic", "procedural", "中间件策略"], ["中间件取舍是 semantic，启动配置是 procedural"], []),
        ("RabbitMQ 和 Spring 异步怎么取舍？", "弱场景可以先用 Spring 内置异步或定时任务，特别是在第 1 到第 4 阶段。RabbitMQ 更适合第 5 阶段的风险扫描、通知和异步任务，因为那时需要可靠投递、削峰和异步处理链路。不要为了单个后台任务提前引入消息队列。", ["RabbitMQ", "Spring 异步", "定时任务"], ["弱异步先用 Spring 异步，复杂异步任务再引入 RabbitMQ"], []),
        ("pgvector 如果用 PostgreSQL 会不会和 MySQL 冲突？", "会带来数据库体系切换或双库维护问题，所以文档只是保留 pgvector 评估空间。当前主数据库已经选 MySQL 8，若第 6 阶段想降低运维复杂度，需要重新评估是继续 MySQL + Qdrant，还是切到 PostgreSQL + pgvector。不能在早期同时承担两套数据库主线。", ["pgvector", "PostgreSQL", "MySQL", "Qdrant"], ["pgvector 会涉及 PostgreSQL 评估，不能早期同时承担两套数据库主线"], [], ["双数据库主线会增加运维复杂度"]),
        ("中间件最终应该怎么写进数据集？", "可以归到 `中间件策略` 模块，围绕每个中间件生成多轮问答：是否现在引入、为什么后置、负责哪个边界、替代方案是什么、后续怎么演进。这样比单条总结更容易测试 RAG 是否能区分 MySQL、Redis、RabbitMQ、MinIO 和向量库的阶段差异。", ["中间件策略", "RAG 数据集", "阶段差异"], ["中间件数据集应围绕阶段、边界、替代方案和演进生成多轮问答"], []),
    ]
    for user, answer, entities, facts, decisions, *rest in middleware_qas:
        risks = rest[0] if rest else None
        add("中间件策略", "decision", user, answer, entities, facts, decisions, risks, score="0.9")

    # 开发规划链 16
    planning_qas = [
        ("为什么开发规划要分 7 个阶段？", "7 个阶段是为了把传统项目管理能力、Agent 能力、RAG 能力和企业级能力拆开，避免单人开发节奏失控。第 1 阶段先做登录、项目、任务和看板闭环；第 2 阶段补需求、迭代、风险；第 3 到第 6 阶段逐步接入 Agent、工具调用、风险分析和 RAG；第 7 阶段再做企业级完善。", ["7 个阶段", "MVP", "Agent", "RAG"], ["开发规划分 7 阶段是为了控制单人开发节奏并逐步增强能力"], ["按阶段推进，不跨阶段堆功能"]),
        ("垂直切片优先是什么意思？", "垂直切片优先就是每个阶段都要形成可演示的前后端闭环，而不是先写一堆后端接口再补前端。比如第 1 阶段要让用户能登录、看到项目、创建任务、在看板查看状态，这样每阶段都有可验证成果。", ["垂直切片", "前后端闭环", "第 1 阶段"], ["垂直切片要求每个阶段都有可演示的前后端闭环"], []),
        ("MVP 边界是不是只做登录就行？", "不够。PM-Agent 的 MVP 第一阶段至少要覆盖登录、项目、任务和任务看板，否则无法体现项目管理平台的主线。登录只是入口，项目和任务才是业务骨架，任务状态流转和状态日志则保证后续风险分析与 Agent 查询有数据基础。", ["MVP", "登录", "项目", "任务看板"], ["第 1 阶段 MVP 包括登录、项目、任务和看板最小闭环"], []),
        ("第 2 阶段为什么才做需求和风险？", "因为第 1 阶段先把用户、项目、任务和看板跑通，避免数据模型一开始过重。第 2 阶段再补需求、迭代、任务依赖、风险和 RBAC，能在已有项目任务基础上扩展，不需要推翻第一阶段结构。", ["第 2 阶段", "需求", "风险", "RBAC"], ["需求、迭代、风险和 RBAC 属于第 2 阶段项目管理 MVP"], []),
        ("Agent 为什么不放第一阶段？", "第一阶段先做传统业务闭环，Agent 放第 3 阶段。原因是 Agent 需要项目、任务、用户和会话数据作为上下文，如果业务主链路还没稳定，Agent 只能空聊，不能真正服务项目管理。", ["Agent", "第 3 阶段", "业务闭环"], ["Agent 应在传统业务数据稳定后接入"], ["第 1 阶段不做 Agent 对话"]),
        ("工具调用为什么又要等第 4 阶段？", "第 3 阶段先验证 Agent 对话、Prompt、模型路由、流式输出和会话落库。工具调用会涉及权限、内部 API、Trace 和结构化输出，复杂度更高，所以放在第 4 阶段。这样可以先稳定聊天链路，再让 Agent 查询和推动业务。", ["工具调用", "第 4 阶段", "Trace"], ["工具调用属于第 4 阶段，先稳定 Agent 对话再接工具"], []),
        ("风险分析为什么要等 RabbitMQ？", "风险分析涉及每日扫描延期、阻塞、人员负载和通知，天然适合异步任务和定时处理。RabbitMQ 在第 5 阶段引入，用于支撑这些后台分析和通知，不应在业务主线还没稳定时提前增加消息队列复杂度。", ["风险分析", "RabbitMQ", "定时任务"], ["风险分析属于第 5 阶段，配合 RabbitMQ 和规则引擎实现"], []),
        ("RAG 为什么排到第 6 阶段？", "RAG 需要文档上传、MinIO、切片、向量化、检索、重排序、引用来源展示等一整套能力。它依赖项目文档和 Agent 链路成熟，所以放第 6 阶段。早期可以做离线评测，但产品化 RAG 不应提前挤进 MVP。", ["RAG", "第 6 阶段", "MinIO", "向量检索"], ["RAG 知识库依赖文档管理和 Agent 链路成熟，规划在第 6 阶段"], ["早期只做 RAG 评测，不做产品化 RAG"]),
        ("第 7 阶段是不是太远了？", "第 7 阶段主要是企业级完善，包括通知中心、审计日志、报告导出、数据看板、系统设置和监控指标。它们很重要，但不是 MVP。放后面能保证前面阶段先形成可用项目管理和 Agent 能力，再补企业展示和运维能力。", ["第 7 阶段", "审计日志", "报告导出", "监控"], ["企业级完善放在第 7 阶段，不进入 MVP 主线"], []),
        ("阶段之间是不是只能新增不能改？", "规划原则是以增强为目标，不重构核心。第 1 到第 2 阶段要集中评审核心表结构，后续尽量只增字段、增模块和增能力，不反复改主键和核心关系。这样才能避免单人项目后期陷入重构泥潭。", ["增强", "重构", "数据模型"], ["阶段演进以增强为目标，避免后续反复重构核心字段"], []),
        ("如果中途想做新功能怎么办？", "先判断它属于哪个阶段。如果是当前阶段主线必须能力，可以纳入；如果是后续阶段能力，比如 RAG、审计、通知、监控、拖拽看板，就记录为后置，不要打断当前闭环。这样能保持开发节奏。", ["阶段归属", "后置能力", "开发节奏"], ["新功能要先判断阶段归属，后置能力不打断当前闭环"], []),
        ("第 1 阶段验收到底看什么？", "第 1 阶段验收看用户能否登录并保持登录态、能否创建项目和查看项目列表、能否在项目下创建任务、任务能否按状态分组展示并通过下拉框切换状态、状态变更是否写入 pm_task_status_log、后端接口是否可通过 Knife4j 调试。", ["第 1 阶段验收", "pm_task_status_log", "Knife4j"], ["第 1 阶段验收聚焦登录、项目、任务、看板和状态日志"], []),
        ("任务看板第一版为什么不用拖拽？", "拖拽看板体验更好，但会引入状态流转校验、前端拖拽交互、失败回滚和权限判断。第 1 阶段先用下拉框切换状态，保证闭环和状态日志，拖拽能力后续按状态流转规则评估是否加入。", ["任务看板", "拖拽", "状态流转"], ["第 1 阶段任务看板用下拉框切换状态，拖拽后置"], []),
        ("开发规划写进 CSV 时算 progress 还是 decision？", "阶段总览、MVP 边界和后置能力判断属于稳定决策，用 `semantic/decision` 或 `semantic/architecture`。如果记录某一次当前进度，比如已完成哪些文件、下一步做什么，可以用 `episodic/progress`。", ["开发规划", "progress", "decision"], ["开发规划中的阶段边界属于 semantic decision，临时进度属于 episodic progress"], []),
        ("以后阶段规划改了，旧记忆怎么办？", "如果新规划明确替代旧规划，旧记录应标记为 `superseded`，新记录写入 `active` 并通过 `supersedes_raw_id` 指向旧记录。这样后续 RAG 检索时可以召回历史过程，但回答应以最新规划为准。", ["superseded", "active", "supersedes_raw_id"], ["规划变更时旧记录应标记 superseded，新记录作为 active 最新结论"], []),
        ("这类阶段讨论要不要保留到长期记忆？", "要保留高价值部分，尤其是阶段边界、为什么后置某能力、MVP 验收标准和技术引入节奏。单纯的临时 TODO 可以过滤，但阶段性决策会影响后续开发判断，适合进入 RAG 原始数据集。", ["长期记忆", "阶段边界", "MVP"], ["阶段边界和 MVP 验收标准适合保留到长期记忆"], []),
    ]
    for user, answer, entities, facts, decisions, *rest in planning_qas:
        risks = rest[0] if rest else None
        add("开发规划", "decision", user, answer, entities, facts, decisions, risks, score="0.89")

    # 前端 / Figma / 设计风格 14
    frontend_qas = [
        ("前端风格到底是普通后台还是更现代一点？", "项目已经确认偏 Warm Linear workspace style，不是传统表格后台。整体要有浅色背景、柔和卡片、清晰层级、蓝绿黄状态色和执行线索。Naive UI 提供基础组件，但页面不能只堆表格，要体现项目进度、任务状态、风险提醒和 Agent 建议。", ["Warm Linear", "Naive UI", "项目工作台"], ["前端视觉方向是 Warm Linear workspace style，而不是传统后台风"], ["前端风格采用 Warm Linear"]),
        ("Figma 画布里能不能写设计说明？", "用户可见的 Figma 画布不应该放设计 rationale、实现说明或思考过程。设计稿应只展示产品界面、交互状态和必要 UI 文案。设计原因、实现说明和验收标准放到 Markdown 文档里，避免画布变成杂乱说明书。", ["Figma", "设计说明", "Markdown 文档"], ["Figma 用户画布不放设计 rationale，说明放 Markdown 文档"], []),
        ("Figma 页面怎么排才统一？", "项目 Figma 规范要求业务页面纵向排列，同一业务的交互状态放在右侧横向展开。这样能让用户从上到下看完整业务流，又能横向查看弹窗、空状态、错误态和确认态。不要把不同业务随意散在画布上。", ["Figma 页面", "交互状态", "业务流"], ["Figma 页面按业务纵向排列，同业务交互态横向展开"], []),
        ("Naive UI 组件是不是直接默认样式就行？", "默认样式可以作为基础，但不能完全依赖。PM-Agent 需要在卡片、列表、看板、风险标签、Agent 建议卡片上体现统一视觉层级。Naive UI 负责表单、弹窗、表格、按钮等基础能力，项目视觉还需要通过布局、色彩、间距和状态标签统一。", ["Naive UI", "组件", "视觉层级"], ["Naive UI 提供基础组件，项目仍需要统一布局和视觉层级"], []),
        ("任务看板颜色怎么用？", "颜色要服务状态，而不是装饰。蓝色适合进行中和主操作，绿色适合完成和健康状态，黄色适合提醒、风险和需要注意的洞察。文档里也强调黄色不要均匀铺满 UI，而是用于值得注意的风险或提示。", ["任务看板", "蓝色", "绿色", "黄色"], ["颜色应服务状态表达，黄色主要用于风险和注意事项"], []),
        ("移动端要不要第一版适配？", "移动端不是第一版重点。PM-Agent 第一阶段是后台管理和项目工作台，优先保证桌面端信息密度、表格、看板和 Agent 对话体验。移动端可以后置，至少不要为了移动端牺牲桌面端主流程。", ["移动端", "桌面端", "第一版"], ["移动端适配不是第一版重点，桌面端项目工作台优先"], []),
        ("暗色模式要不要顺手做？", "不建议第一版做暗色模式。暗色模式会增加颜色系统、图表、状态标签、表格和弹窗的适配成本。当前重点是 Warm Linear 浅色工作台风格稳定，等主流程完成后再评估是否需要主题系统。", ["暗色模式", "主题系统", "Warm Linear"], ["暗色模式后置，第一版优先稳定浅色 Warm Linear 风格"], []),
        ("前端目录按页面放还是按业务模块放？", "建议按业务模块组织，通用组件再放 components。项目涉及 project、task、requirement、risk、agent 等业务域，按模块组织更利于后续页面、API、store 和类型文件协同维护，避免所有页面堆在一个 pages 目录里变乱。", ["前端目录", "业务模块", "Pinia"], ["前端目录按业务模块组织更利于维护"], []),
        ("Pinia store 怎么拆？", "按业务状态拆，不要一个全局 store 管所有。至少用户、项目、任务、Agent 会话可以分开。这样页面只依赖自己需要的状态，也方便后续联调真实接口、替换 mock 数据和控制缓存策略。", ["Pinia", "store", "业务状态"], ["Pinia store 应按用户、项目、任务、Agent 会话等业务状态拆分"], []),
        ("前端 Mock 层要不要保留？", "第 1 阶段接口未完全稳定时，前端可以保留简单本地 Mock 层，用于模拟登录、项目和任务数据。等后端接口可用后逐步切真实 API。Mock 只服务开发期，不应让页面逻辑依赖 mock 特有字段。", ["Mock", "前端联调", "真实 API"], ["前端开发期可保留 Mock 层，但不能依赖 mock 特有字段"], []),
        ("Agent 助手页应该怎么展示？", "Agent 助手页要展示用户问题、流式回答、会话历史和必要的工具调用过程。第一版可以先展示文本流和预置问题，工具调用可视化放第 4 阶段增强。回答中引用的项目数据和后续动作建议，要和普通聊天内容区分开。", ["Agent 助手页", "流式回答", "工具调用"], ["Agent 助手页第一版展示流式回答和会话历史，工具调用可视化后置"], []),
        ("设计稿和代码不一致怎么办？", "如果是视觉细节差异，可以以后端和前端实现成本为约束做微调；如果是业务流程、页面能力、字段含义不一致，则应回到产品和文档先确认，再改设计或代码。设计稿是实现参考，不应绕过文档边界直接扩展功能。", ["设计稿", "代码实现", "产品边界"], ["设计稿和代码不一致时，业务差异需回到文档和产品边界确认"], []),
        ("前端相关记录在 CSV 里怎么分 module？", "如果讨论工程结构、路由、状态管理和 API 封装，module 用 `前端工程`；如果讨论视觉风格、配色、组件观感，用 `设计风格`；如果讨论 Figma 画布和交互态，用 `Figma 设计稿`。这样后续按问题检索更集中。", ["前端工程", "设计风格", "Figma 设计稿"], ["前端历史记录按工程、视觉和设计稿三个模块区分更清晰"], []),
        ("为什么第一版看板用下拉框状态切换，而不是拖拽？", "拖拽涉及前端交互、后端状态机、失败回滚、权限校验和状态日志同步。第一版用下拉框可以先验证任务状态流转和日志写入，等状态规则稳定后再做拖拽。这个取舍更符合垂直切片优先原则。", ["任务看板", "拖拽", "下拉框", "状态日志"], ["第一版看板用下拉框优先验证状态流转，拖拽后置"], []),
    ]
    for user, answer, entities, facts, decisions, *rest in frontend_qas:
        risks = rest[0] if rest else None
        module = "Figma 设计稿" if "Figma" in user else "设计风格" if "风格" in user or "颜色" in user or "暗色" in user else "前端工程"
        add(module, "decision", user, answer, entities, facts, decisions, risks, score="0.86")

    # 文档规范 12
    doc_qas = [
        ("文档是不是都放 docs 目录？", "长期项目文档统一放在 `docs/`，并使用中文 Markdown。`docs/README.md` 是索引，说明长期规范文档、阶段与模块文档以及文档归属。临时调度清单不进入 docs，必要时用 GitHub Issue 或开发规划的下一步章节。", ["docs", "Markdown", "文档索引"], ["长期项目文档统一放在 docs 目录并使用中文 Markdown"], ["文档统一归入 docs"]),
        ("文档里能不能写历史代码细节？", "不建议。文档应写当前设计目标、方案、规则和验收标准，不写历史代码细节。历史变更应由 Git 记录或提交说明追踪。这样文档才能长期服务设计和实现，而不是变成开发日记。", ["文档规范", "历史代码", "Git"], ["项目文档不写历史代码细节，只写当前设计目标、方案和规则"], []),
        ("新增业务概念时先写代码还是先改术语表？", "先查 `docs/00-术语表.md`。如果没有对应术语，应先补充术语表，再进入数据建模、接口设计和代码实现。这样能避免同一个概念在页面、表名、Java 类和 Agent Prompt 里出现多个叫法。", ["术语表", "数据建模", "接口设计"], ["新增业务概念必须先更新术语表，再进入建模和实现"], []),
        ("API 文档是不是只靠 Knife4j 就行？", "不行。Knife4j 适合接口查看和调试，但 Markdown API 文档负责沉淀路径、请求头、权限、幂等、错误码、traceId 和示例。尤其跨前端、Java、Python 的接口，必须有长期可读的 Markdown 说明。", ["Knife4j", "API 文档", "traceId"], ["API 文档需要 Markdown 和 Knife4j 配合，不能只靠 Knife4j"], []),
        ("每个模块都要写设计文档吗？", "是的，doc-writer Skill 明确要求每个模块至少有模块设计文档，包含背景、职责、术语、业务流程、数据模型、接口清单、前端页面、Agent 介入点、权限与风险、开发步骤、验收标准和待确认问题。", ["模块设计文档", "验收标准", "待确认问题"], ["每个模块应有最小设计文档，代码前先明确职责和边界"], []),
        ("文档结构一定要固定模板吗？", "默认建议保留背景、目标、范围、详细设计、开发计划、风险取舍、验收标准和待确认问题，但不需要为了模板而模板。阶段总结模板已经取消，必要时按具体阶段临时生成，避免堆积低价值过程文档。", ["文档模板", "阶段总结", "待确认问题"], ["文档保留核心结构，但固定阶段总结模板已取消"], []),
        ("成本控制要不要单独写一个文档？", "目前成本控制规则已并入技术选型、数据模型、Agent 设计和根目录规范，不再单独维护成本控制文档。这样能减少重复文档，也避免成本策略和模型路由、Trace 保留策略分散。", ["成本控制", "技术选型", "Agent 设计"], ["成本控制规则已并入多个核心文档，不再单独维护"], []),
        ("文档里待确认问题是不是每篇都要有？", "长期文档最后应保留待确认问题章节，但只列真正影响实现的问题。不要把过程 TODO、临时想法、已解决事项都堆进去。待确认问题的价值是提醒后续决策点，而不是替代任务管理。", ["待确认问题", "长期文档", "TODO"], ["长期文档保留待确认问题，但只记录真正影响实现的事项"], []),
        ("README 和详细文档怎么分工？", "README 负责入口说明、启动方式、目录说明和快速理解；详细设计放在 docs 或模块设计文档里。不要把复杂设计全塞 README，也不要让 README 只剩一句跳转。", ["README", "详细设计", "docs"], ["README 负责入口和快速理解，详细方案放 docs"], []),
        ("文档生成时能不能写未实现能力？", "可以写规划，但必须标注为未实现、后置或待确认。比如 RAG、审计日志、企业级看板、监控指标都可以出现在规划里，但不能写成已经完成。项目展示文档尤其要避免夸大未完成能力。", ["未实现能力", "规划", "项目展示"], ["未实现能力可以写规划，但必须标注状态，不能写成已完成"], [], ["夸大未完成能力会误导评审和后续开发"]),
        ("这类文档规范记录进 CSV 有用吗？", "有用。后续当你问“API 文档怎么写”“新增模块前要补什么”“为什么不能只靠 Knife4j”时，RAG 可以召回这些规范。它们属于稳定的项目协作规则，适合标记为 `semantic/decision` 或 `procedural/tool_usage`。", ["文档规范", "RAG", "semantic"], ["文档规范是稳定协作规则，适合进入 RAG 原始数据集"], []),
        ("如果文档和代码不一致怎么办？", "如果是当前实现已经改变，应优先验证代码和最新需求，再更新文档；如果是文档中的后置规划尚未实现，不应因为代码没有对应实现就删除规划，而是明确标注阶段和状态。当前状态优先通过代码核验，长期边界通过文档维护。", ["文档一致性", "代码", "阶段规划"], ["文档和代码不一致时应核验当前实现并更新文档状态"], []),
    ]
    for user, answer, entities, facts, decisions, *rest in doc_qas:
        risks = rest[0] if rest else None
        add("文档规范", "decision", user, answer, entities, facts, decisions, risks, score="0.86")

    # 单点补充 68? Need enough pool.
    singles = [
        ("模块边界", "architecture", "项目、需求、任务、迭代、风险这些模块怎么分？", "项目是交付目标，需求描述要实现什么，任务是可执行最小工作单元，迭代承载时间周期，风险表示可能影响交付的不确定因素。模块边界要围绕业务语义拆，不要把所有字段塞进任务表。", ["项目", "需求", "任务", "迭代", "风险"], ["项目、需求、任务、迭代、风险分别承担不同业务语义"], ["业务模块按语义边界拆分"]),
        ("模块边界", "architecture", "报告模块现在要不要做？", "报告属于后续能力，第一版不需要完整报告中心。第 4 阶段会出现周报生成工具，第 7 阶段再做报告导出和报表中心。当前只需在文档里保留报告术语和未来接口边界。", ["报告", "周报", "第 4 阶段", "第 7 阶段"], ["报告生成和导出不是第 1 阶段能力"], []),
        ("模块边界", "architecture", "风险模块第一版是不是只手动登记？", "是的，MVP 前两阶段先支持风险手动登记和状态跟踪。自动风险识别、延期扫描、阻塞分析和人员负载属于第 5 阶段，需要 RabbitMQ、规则引擎和 Agent 风险建议，不应提前挤进第一版。", ["风险", "手动登记", "风险分析"], ["风险第一版以手动登记为主，自动分析后置到第 5 阶段"], []),
        ("Agent 工具调用", "architecture", "工具 API 应该由 Python 直接实现吗？", "不应该。工具背后的业务查询和变更应由 Java 后端提供内部 API，Python Agent 只选择和调用工具。这样权限、幂等、状态日志和业务规则都留在 Java 主系统内，避免 Agent 服务绕过业务边界。", ["工具 API", "Java 后端", "Python Agent"], ["Agent 工具背后的业务能力由 Java 后端提供"], ["工具 API 由 Java 负责业务实现"]),
        ("Agent 工具调用", "decision", "split_requirement_into_tasks 这种工具会不会直接写任务？", "第一版不应直接写入。需求拆任务属于 Agent 写业务数据，应该先生成建议和动作卡片，用户确认后再由 Java 工具 API 创建任务。这样既保留 Agent 效率，也避免模型误拆导致脏数据进入任务表。", ["split_requirement_into_tasks", "人工确认", "任务创建"], ["Agent 生成任务建议需人工确认后再写入业务表"], ["需求拆任务不直接自动入库"], ["模型误拆任务会污染任务数据"]),
        ("Agent 工具调用", "architecture", "Trace 页要展示哪些东西？", "Trace 页应展示用户输入、Prompt 版本、模型、token、工具调用名称、入参、出参、耗时、状态、错误信息和最终回答。前端可以先展示核心链路，完整调试信息保留在 Trace 表中。", ["Trace 页", "工具调用", "token"], ["Trace 应覆盖输入、Prompt、模型、工具调用和最终输出"], []),
        ("接口规范", "decision", "写接口都要传 X-Idempotency-Key 吗？", "所有写请求都应该传 `X-Idempotency-Key`，避免重复提交导致重复创建项目、任务或风险。读请求不需要幂等键，但仍应保持 traceId。Agent 工具调用业务写接口时也必须携带幂等键。", ["X-Idempotency-Key", "写请求", "Agent 工具"], ["写请求需要幂等键，Agent 工具写接口也一样"], []),
        ("接口规范", "architecture", "traceId 是前端生成还是后端生成？", "可以由前端传入，也可以由后端生成，但响应必须返回 traceId。关键是跨前端、Java、Python、LLM 的链路要保持同一个追踪标识，方便排查对话、工具调用和业务落库问题。", ["traceId", "前端", "Java", "Python"], ["traceId 需要贯通前端、Java、Python 和 LLM 链路"], []),
        ("数据模型", "architecture", "Agent Trace 和业务审计日志是一个东西吗？", "不是。Agent Trace 记录模型决策链路、Prompt、工具调用和最终输出；业务审计日志记录用户对资源的关键操作。Trace 用于调试和优化 Agent，审计日志用于安全、合规和操作追溯，两者可以通过 traceId 关联但职责不同。", ["Agent Trace", "审计日志", "traceId"], ["Agent Trace 与业务审计日志职责不同，可通过 traceId 关联"], []),
        ("数据模型", "decision", "逻辑删除字段是不是所有表都要预留？", "业务主表建议预留逻辑删除字段，尤其是项目、任务、需求、风险等需要历史追溯的数据。对于纯日志表和 Trace 表，通常不做普通逻辑删除，而是按保留策略和归档策略管理。", ["逻辑删除", "业务主表", "Trace"], ["业务主表适合逻辑删除，日志和 Trace 更适合保留策略管理"], []),
        ("模型策略", "decision", "Claude、GPT、DeepSeek 怎么分工？", "运行时默认 DeepSeek，复杂推理、关键决策、最终润色再升级 Claude 或 GPT。开发期架构设计和代码理解优先 Claude，文档初稿和批量生成可以用 DeepSeek。这样既保证效果，也控制月度运行成本。", ["Claude", "GPT", "DeepSeek", "模型路由"], ["运行时默认 DeepSeek，复杂任务升级 Claude 或 GPT"], ["模型分层路由以成本和质量平衡为目标"]),
        ("模型策略", "risk", "LLM 成本失控怎么办？", "成本控制靠默认低成本模型、关键任务升级、高价值 Trace 保留和批量摘要缓存。RAG 阶段文档切片和摘要也要缓存结果，不能每次重复调用模型。必要时可以引入本地模型作为后续扩展，但不属于当前阶段。", ["LLM 成本", "缓存", "本地模型"], ["LLM 成本通过模型分层、缓存和 Trace 保留策略控制"], [], ["重复摘要和无节制升级高成本模型会造成成本失控"]),
        ("Git 管理", "decision", "为什么不用长期 frontend/backend 分支？", "项目采用 Monorepo + main 主干 + feature/* 任务分支。目录用于区分模块，分支用于区分任务。如果长期维护 frontend/backend 分支，会造成集成延迟和主干漂移，不适合单人 + AI 协作节奏。", ["Monorepo", "main", "feature/*"], ["项目使用 main 主干和 feature/* 任务分支，不使用长期模块分支"], []),
        ("Git 管理", "tool_usage", "什么时候需要单独开 feature 分支？", "每个相对独立的任务都可以从 main 开 feature/* 分支，例如初始化前端、初始化后端、实现认证、补任务接口。分支代表任务边界，不代表长期模块归属。完成后合并回 main，保持主干是完整基线。", ["feature/*", "main", "任务边界"], ["feature 分支用于任务边界，完成后合并回 main"], []),
        ("注释规范", "decision", "注释到底要多写还是少写？", "项目规范要求关键类和方法有中文注释，复杂业务逻辑解释为什么这么做。但不要给显而易见的代码写废话注释。注释重点是隐藏约束、状态流转原因、权限边界、幂等逻辑和 Agent 高风险动作。", ["中文注释", "复杂业务逻辑", "权限边界"], ["注释应解释为什么和关键约束，而不是重复代码做了什么"], []),
        ("注释规范", "decision", "TODO 注释能不能随便写？", "不能。临时代码必须用 `TODO 中文说明` 标注，说明为什么临时、后续要处理什么。没有说明的 TODO 会变成技术债噪声。已经不需要的临时代码应删除，而不是靠注释保留。", ["TODO", "中文说明", "临时代码"], ["TODO 必须有中文说明，临时代码不应无说明保留"], []),
        ("项目管理", "architecture", "任务状态第一版有哪些？", "第 2 阶段规划了更完整状态机：待处理、开发中、待联调、待测试、已完成、已取消。第 1 阶段可以先满足看板按状态分组和下拉切换，但状态日志要先落地，为后续风险分析和过程复盘准备数据。", ["任务状态", "看板", "状态日志"], ["任务状态和状态日志是任务看板与风险分析的基础"], []),
        ("项目管理", "decision", "需求和任务是不是可以合成一个表？", "不建议。需求描述用户或业务视角的“要实现什么”，任务是可分配、可执行、可跟踪状态的最小工作单元。合成一个表会让需求评审、任务执行和进度跟踪混在一起，后续需求拆任务和 Agent 工具调用也不好做。", ["需求", "任务", "数据模型"], ["需求和任务语义不同，不应合并为一个表"], []),
        ("项目管理", "architecture", "迭代和阶段是不是一个概念？", "术语表里统一使用 `迭代 iteration`，它承载敏捷 Sprint 和瀑布阶段两类语义。代码、表名和 API 使用 iteration，不在代码里混用 Sprint 或阶段，避免术语分裂。", ["迭代", "iteration", "Sprint"], ["代码和 API 统一使用 iteration 表达迭代"], []),
        ("风险分析", "decision", "风险和问题怎么区分？", "风险是可能影响交付的不确定因素，问题是已经发生并影响进度、质量或交付的事项。风险可以演变为问题，但不能混用。这个区分会影响风险列表、问题处理和 Agent 风险分析的判断口径。", ["风险", "问题", "交付"], ["风险是可能发生的问题，问题是已经发生的影响事项"], []),
        ("风险分析", "architecture", "风险关闭后需要留记录吗？", "需要。风险关闭后应保留处理记录，包括原因、建议、处理人和状态变化。第 5 阶段自动风险分析也需要这些历史数据训练规则和评估 Agent 建议是否有效。", ["风险关闭", "处理记录", "状态变化"], ["风险关闭后需要保留处理记录和状态变化"], []),
        ("RAG 知识库", "architecture", "文档上传后是不是直接向量化就行？", "不够。正式 RAG 需要文档上传、存储、解析、切片、向量化、检索、重排序、引用来源和权限控制。直接把整篇文档向量化会导致召回粒度粗、引用不清晰，也不利于多轮追问。", ["文档上传", "切片", "向量化", "引用来源"], ["正式 RAG 需要解析、切片、向量化、检索、重排序和引用来源"], []),
        ("RAG 知识库", "decision", "RAG 回答里要不要显示来源？", "要显示。第 6 阶段验收标准明确 Agent 回答中包含引用来源。没有来源的 RAG 回答难以追溯，也无法判断模型是否真的基于项目文档回答。", ["RAG", "引用来源", "验收标准"], ["RAG 回答必须包含引用来源"], []),
        ("RAG 知识库", "risk", "向量召回会不会召回语义像但业务不相关的内容？", "会，这正是后续要引入混合召回、project_id 过滤、关键词召回、实体召回和 reranker 的原因。单纯 embedding 容易被相似词误导，比如两个宿舍项目都出现通知、状态、管理员。", ["向量召回", "project_id", "reranker"], ["单纯向量召回可能语义相似但业务无关，需要过滤和重排序"], [], ["语义相似不等于业务相关"]),
        ("前端工程", "tool_usage", "前端环境变量怎么管理？", "前端通过 Vite 环境变量管理 API 地址、mock 开关等配置。开发期可以用 `VITE_USE_MOCK=true` 切 mock，真实联调时改为后端 API。不要把环境地址写死在业务组件里。", ["Vite", "环境变量", "Mock"], ["前端配置通过 Vite 环境变量管理，业务组件不写死地址"], []),
        ("前端工程", "architecture", "Axios 封装要做哪些事？", "Axios 封装应处理基础 URL、Authorization 注入、traceId、统一错误码、登录失效跳转和响应结构解包。这样页面不用关心底层请求细节，也能统一处理后端返回的 code/message/data/traceId。", ["Axios", "Authorization", "traceId", "错误码"], ["Axios 封装负责认证、错误处理和统一响应解包"], []),
        ("后端架构", "decision", "Flyway 是不是有点重？", "不重。PM-Agent 后端需要稳定管理业务表、状态日志和后续 Agent Trace 表。Flyway 能让数据库结构随版本迁移，避免手动改库导致环境不一致。单人项目也需要可重复初始化和回放数据库结构。", ["Flyway", "数据库迁移", "版本管理"], ["Flyway 用于可重复管理数据库结构迁移"], []),
        ("后端架构", "risk", "MapStruct 会不会过度工程？", "如果只为一两个简单对象转换使用，确实可能过度。它更适合 DTO、VO、Entity 转换规则变多时减少样板代码。第一版可以按需要引入，不必强迫所有对象转换都用 MapStruct。", ["MapStruct", "DTO", "过度工程"], ["MapStruct 应按转换复杂度使用，不强制所有映射都走它"], [], ["过早抽象会增加维护成本"]),
        ("Skill 规范", "prompt", "如果用户只说写个文档，是不是一定触发 doc-writer？", "如果是项目文档、技术方案、模块设计、API 文档、README 或部署说明，就应该触发 doc-writer。如果只是临时回答或一段说明，不一定要生成长期文档。doc-writer 的边界是把稳定设计沉淀为可维护 Markdown，而不是把所有对话都变成文档。", ["doc-writer", "项目文档", "Markdown"], ["doc-writer 用于稳定项目文档，不处理所有临时回答"], []),
        ("Skill 规范", "prompt", "前端设计是不是可以直接用 frontend-design skill？", "通用前端美化可以用 frontend-design，但 PM-Agent 项目内页面优先使用 `pm-agent-frontend-builder`，因为它会保护已确认的 Warm Linear 方向、Vue 3 技术栈、Naive UI 组件和项目模块边界。", ["frontend-design", "pm-agent-frontend-builder", "Warm Linear"], ["PM-Agent 页面优先使用项目级 frontend builder Skill"], []),
        ("文档规范", "decision", "阶段复盘文档为什么被清理了？", "阶段复盘和开工前置确认属于过程性内容，长期价值不如术语、规划、技术选型、接口、数据模型和 Agent 设计。项目文档清理后不再保留固定模板，必要时按具体阶段临时生成，避免 docs 目录堆积低价值过程文档。", ["阶段复盘", "docs", "过程文档"], ["阶段复盘固定模板已取消，docs 保留长期设计文档"], []),
        ("文档规范", "architecture", "长期文档命名为什么有编号？", "编号便于阅读顺序和主题分组，比如术语表、开发规划、技术选型、业务流程、数据模型、接口规范、Agent 设计。文档清理后编号不强制连续，避免为了补号大规模重命名和修改引用。", ["文档编号", "docs", "引用"], ["长期文档使用编号方便阅读顺序，但编号不强制连续"], []),
        ("设计风格", "decision", "为什么黄色只用于风险和洞察？", "黄色视觉注意力强，如果大面积使用会让页面显得焦虑且没有层级。PM-Agent 中黄色更适合表示风险、提醒、值得注意的洞察和待处理状态，普通信息用中性色和蓝绿色表达即可。", ["黄色", "风险", "视觉层级"], ["黄色应控制使用，主要表达风险和注意事项"], []),
        ("设计风格", "architecture", "Warm Linear 和普通后台最大的区别是什么？", "普通后台往往以表格和表单为中心，Warm Linear 更强调工作台感、任务流、状态提示、卡片层级和轻量视觉反馈。PM-Agent 是项目管理 Agent 平台，需要让用户快速理解项目状态和 Agent 建议，而不是只看到数据表。", ["Warm Linear", "后台", "工作台"], ["Warm Linear 强调工作台感和状态线索，不只是表格后台"], []),
        ("模型策略", "risk", "如果 DeepSeek 回答质量不稳定怎么办？", "先通过 Prompt、结构化输出和工具结果约束提升稳定性。如果仍涉及关键决策、复杂推理或最终润色，再升级 Claude 或 GPT。不要一开始所有请求都升级，否则运行成本会失控。", ["DeepSeek", "Claude", "GPT", "成本"], ["DeepSeek 不稳定时优先优化 Prompt 和结构化约束，关键任务再升级模型"], [], ["全量高成本模型会导致运行成本失控"]),
        ("模型策略", "architecture", "模型路由是不是要一开始就做复杂？", "不需要。第一版可以先有轻量 ModelClient 适配层，统一请求、响应、流式事件、错误和 token 统计。复杂模型路由、自动升级和本地模型可以后续扩展，不要一开始做成重型网关。", ["ModelClient", "模型路由", "token"], ["第一版模型适配层要轻量，复杂路由后置"], []),
        ("数据模型", "architecture", "Agent Trace 保留多久？", "项目设计里 Agent Trace 开发与调优阶段保留必要 Prompt、模型输出和工具调用结果，运行期按 3 个月保留策略控制存储成本。超大输出可截断并记录标记，敏感字段必须脱敏。", ["Agent Trace", "3 个月", "脱敏"], ["Agent Trace 运行期按 3 个月保留，并处理截断和脱敏"], []),
        ("数据模型", "risk", "Trace 里能不能存完整 Prompt？", "开发和调优阶段需要足够完整的 Prompt 以便复盘，但要注意敏感信息脱敏。长期运行时可以保留模板编号、变量、摘要和必要上下文，超大内容放外部存储或截断，避免成本和隐私风险。", ["Prompt", "Trace", "脱敏"], ["Trace 记录 Prompt 需要兼顾调试价值、存储成本和敏感信息脱敏"], [], ["完整 Prompt 可能带来隐私和存储成本风险"]),
        ("接口规范", "decision", "错误码分段有什么意义？", "错误码分段能让前端、后端和 Agent 快速判断错误来源。通用错误、用户权限、项目任务、Agent/LLM、外部服务和系统错误使用不同区间，后续告警、日志分析和用户提示都更清晰。", ["错误码", "Agent", "外部服务"], ["错误码分段用于区分错误来源并提升排查效率"], []),
        ("接口规范", "architecture", "Python 服务内部接口也要 /api/v1 吗？", "对外或跨服务调用建议保持版本化路径，Python Agent 当前也有 `/api/v1/agent/chat`。内部健康检查可以使用 `/internal/health`。版本化路径有利于 Java 客户端和前端保持兼容。", ["/api/v1", "/internal/health", "Python Agent"], ["跨服务接口建议使用版本化路径，健康检查可用 internal 路径"], []),
        ("项目管理", "decision", "RBAC 第一版要做完整吗？", "完整 RBAC 放第 2 阶段。第 1 阶段可以保留用户、项目成员和基础角色字段，但不需要做复杂权限矩阵。等需求、任务、风险和成员管理稳定后，再按项目经理、研发、测试、管理员等角色扩展。", ["RBAC", "项目成员", "角色"], ["完整 RBAC 属于第 2 阶段，第 1 阶段只保留基础角色结构"], []),
        ("项目管理", "architecture", "项目成员和系统用户为什么要区分？", "系统用户表示能登录系统的人，项目成员表示某个用户在某个项目中的角色和权限。一个用户可以参与多个项目，并在不同项目承担不同角色，所以需要 project_member 关系表，而不是只在用户表上写一个全局角色。", ["用户", "项目成员", "角色"], ["系统用户和项目成员职责不同，需要通过项目成员关系表达项目内角色"], []),
        ("风险分析", "architecture", "人员负载分析需要哪些数据？", "至少需要任务负责人、任务状态、优先级、截止时间、迭代归属和历史完成情况。第 5 阶段再结合规则引擎和 Agent 解释生成负载风险。第 1 阶段不必完整实现，但任务表和状态日志要为后续预留基础。", ["人员负载", "任务状态", "状态日志"], ["人员负载分析依赖任务负责人、状态、截止时间和历史完成情况"], []),
        ("Git 管理", "risk", "如果 feature 分支拖太久会怎样？", "feature 分支拖太久会偏离 main，合并时冲突更多，也容易让文档、前端、后端状态不同步。项目采用小任务 feature 分支，完成后尽快合并回 main，保持 main 是完整项目基线。", ["feature 分支", "main", "冲突"], ["feature 分支应小而短，完成后尽快合并回 main"], [], ["长期 feature 分支会增加合并冲突和状态漂移"]),
        ("文档规范", "decision", "部署说明放哪里？", "部署和本地中间件说明统一放 `deploy/README.md`，不要散落在阶段复盘或临时 TODO 文档里。长期文档只保留稳定入口和规则，实际启动、验证、重置步骤集中在部署说明中维护。", ["deploy/README.md", "部署说明", "中间件"], ["本地中间件和部署说明集中在 deploy/README.md"], []),
        ("RAG 知识库", "risk", "RAG 记忆和业务数据库会不会冲突？", "业务数据库是事实主源，RAG 或记忆系统负责上下文、历史解释和证据。比如任务当前状态必须查业务表，历史上为什么创建这个任务可以查记忆。不能让旧记忆覆盖当前业务事实。", ["RAG", "业务数据库", "事实主源"], ["业务数据库是事实主源，记忆系统负责历史语境"], [], ["旧记忆覆盖当前事实会造成错误回答"]),
        ("Agent 编排", "decision", "Agent 什么时候应该追问用户？", "当项目、任务、日期、负责人、风险范围等关键字段不足时，Agent 应该追问，而不是凭空补全。尤其是高风险动作和业务写操作，必须先让用户确认具体对象和影响范围。", ["Agent", "追问", "信息不足"], ["Agent 信息不足时应追问，不应凭空补全关键业务字段"], []),
        ("Skill 规范", "decision", "测试策略相关问题归哪个 skill？", "测试策略、手工验收、API 测试、前端交互测试、Agent 场景测试和 LLM 输出样例都归 `pm-agent-test-planner`。它不负责写业务代码，而是定义质量门禁和验收路径。", ["pm-agent-test-planner", "验收", "测试策略"], ["测试策略相关问题由 pm-agent-test-planner 负责"], []),
        ("Skill 规范", "decision", "成本优化相关问题归哪个 skill？", "LLM 调用成本、模型路由、Prompt 缓存、Trace 存储成本、向量数据库成本和部署成本都归 `pm-agent-cost-optimizer`。它关注运行时预算，不替代 LLM Orchestrator 的编排设计。", ["pm-agent-cost-optimizer", "模型路由", "Trace 成本"], ["成本优化问题由 pm-agent-cost-optimizer 负责"], []),
        ("Skill 规范", "decision", "数据表设计用 database-schema-designer 还是项目 data-modeler？", "通用关系数据库设计可以用 database-schema-designer，但 PM-Agent 内部业务表、状态枚举、逻辑删除、多租户、Agent Trace 表等优先用 `pm-agent-data-modeler`，因为它理解项目术语和阶段边界。", ["database-schema-designer", "pm-agent-data-modeler", "数据表"], ["PM-Agent 业务数据建模优先使用项目级 data modeler Skill"], []),
        ("前端工程", "architecture", "ECharts 第一版要做哪些图？", "第 1 阶段不需要复杂图表。ECharts 主要在后续数据看板、风险趋势和项目统计中使用。第一版前端重点是登录、项目列表、项目详情和任务看板，图表能力可以等第 5 到第 7 阶段逐步增强。", ["ECharts", "数据看板", "风险趋势"], ["ECharts 图表能力主要用于后续看板和风险趋势，不是第 1 阶段重点"], []),
        ("设计风格", "decision", "项目介绍页要不要做得很营销？", "不需要过度营销。PM-Agent 是项目管理 Agent 平台，介绍页应清楚说明定位、核心能力、阶段状态和演示路径。视觉可以现代，但不要夸大未完成功能，也不要把规划能力写成已上线能力。", ["项目介绍页", "演示路径", "未完成功能"], ["项目介绍页应展示定位和演示路径，不夸大未完成功能"], []),
    ]
    for module, bt, user, answer, entities, facts, decisions, *rest in singles:
        risks = rest[0] if rest else None
        add(module, bt, user, answer, entities, facts, decisions, risks, score="0.84", weight="medium" if module in {"Git 管理", "设计风格"} else "high")

    return records


def normalize_existing(row: dict[str, str]) -> dict[str, str]:
    normalized = {header: row.get(header, "") for header in HEADERS}
    normalized["project_id"] = PROJECT_ID
    normalized["project_name"] = PROJECT_NAME
    normalized["business_type"] = BUSINESS_TYPE_MAP.get(normalized["business_type"], normalized["business_type"])
    if normalized["memory_type"] not in {"semantic", "episodic", "procedural"}:
        normalized["memory_type"] = infer_memory_type(normalized["business_type"])
    return normalized


def main() -> None:
    with TARGET_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        existing = [normalize_existing(row) for row in reader]

    generated = build_generated_records()
    needed = 200 - len(existing)
    if needed < 0:
        raise RuntimeError(f"现有数据已超过 200 条：{len(existing)}")
    if len(generated) < needed:
        raise RuntimeError(f"生成池不足，需要 {needed} 条，只有 {len(generated)} 条")

    all_rows = existing + generated[:needed]
    all_rows.sort(key=lambda row: (MODULE_INDEX.get(row["module"], 999), row["module"], row["user_message"]))

    for index, row in enumerate(all_rows, start=1):
        row["raw_id"] = f"{index:03d}"
        row["global_index"] = str(index)
        row["turn_no"] = str(index)
        row["project_id"] = PROJECT_ID
        row["project_name"] = PROJECT_NAME
        for array_field in ["entities", "facts", "decisions", "risks"]:
            value = row.get(array_field, "")
            try:
                parsed = json.loads(value) if value else []
            except json.JSONDecodeError:
                parsed = [value] if value else []
            if not isinstance(parsed, list):
                parsed = [str(parsed)]
            row[array_field] = json.dumps(parsed, ensure_ascii=False)
        row.setdefault("supersedes_raw_id", "")

    with TARGET_FILE.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(all_rows)

    modules = sorted({row["module"] for row in all_rows})
    print(f"扩展完成：{TARGET_FILE}")
    print(f"总行数：{len(all_rows)}")
    print(f"新增行数：{needed}")
    print(f"模块数量：{len(modules)}")
    print("模块列表：" + "、".join(modules))


if __name__ == "__main__":
    main()
