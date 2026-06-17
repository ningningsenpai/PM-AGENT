import csv
import json
from pathlib import Path
from collections import Counter

base = Path(__file__).parent

projects = [
    {
        "project_id": "P-DORM-STAFF",
        "project_name": "宿舍人员管理项目",
        "code": "DORM-STAFF",
        "modules": ["学生档案", "入住登记", "退宿管理", "换宿管理", "床位管理", "访客登记", "晚归记录", "宿管权限", "数据统计", "通知提醒"],
        "focus": "宿舍人员、床位、入住退宿、访客晚归和宿管权限",
        "points": {
            "学生档案": ["学生档案需要保存学号、姓名、学院、联系方式和当前宿舍绑定关系。", "导入学生档案时必须校验学号唯一，重复记录进入人工处理列表。"],
            "入住登记": ["入住登记必须校验床位为空闲，并同步更新床位状态为已占用。", "入住登记第一版只支持单人登记，批量导入后置。"],
            "退宿管理": ["退宿确认后必须释放床位，并保留历史住宿记录。", "退宿申请必须由宿管确认，避免床位提前释放。"],
            "换宿管理": ["换宿需要同时校验原床位和目标床位，跨学院换宿需要额外复核。", "换宿完成后必须生成两条床位变更记录。"],
            "床位管理": ["床位状态包括空闲、已占用、维修中和冻结。", "冻结床位用于迎新预留，不允许普通入住占用。"],
            "访客登记": ["访客登记使用二维码核验，记录来访人、被访学生、进入时间和离开时间。", "访客二维码过期时间最终定为 2 小时。"],
            "晚归记录": ["晚归记录由宿管录入，后续按学院和楼栋统计。", "晚归超过三次才触发辅导员提醒。"],
            "宿管权限": ["宿管权限按楼栋授权，只能查看和维护自己负责的楼栋。", "超级管理员可以跨楼栋查看统计，普通宿管不能。"],
            "数据统计": ["数据统计首页展示入住率、空床数、晚归次数和访客数量。", "统计数据按天刷新，第一版不做实时大屏。"],
            "通知提醒": ["通知提醒用于入住审核、退宿确认、晚归预警和访客到期提醒。", "通知渠道第一版只做站内消息。"]
        },
        "updates": [
            ("换宿管理", "跨学院换宿审批", "最初方案是跨学院换宿只需要宿管审批。", "后来发现跨学院换宿涉及学院管理责任，需要辅导员复核。", "最终确定跨学院换宿采用宿管初审加辅导员复核，旧的单审批方案作废。"),
            ("晚归记录", "晚归提醒阈值", "最初计划晚归一次就提醒辅导员。", "评审后认为一次晚归噪声太大，改为累计三次后提醒。", "最终确认晚归超过三次才触发辅导员提醒。"),
            ("访客登记", "访客二维码有效期", "最初二维码有效期设置为 24 小时。", "安全评审认为时间过长，容易被重复使用。", "最终将访客二维码有效期调整为 2 小时。"),
            ("床位管理", "床位冻结规则", "最初冻结床位允许管理员手动解除后立即入住。", "测试发现迎新预留床位容易被误占。", "最终确认冻结床位必须先解除冻结并记录原因，才能用于入住。"),
            ("通知提醒", "通知渠道范围", "最初计划同时支持站内消息和短信。", "考虑成本和开发进度，短信通知暂缓。", "最终确认第一版通知渠道只做站内消息。")
        ],
        "bugs": [("入住登记", "入住后床位仍显示空闲", "入住保存成功后未同步床位状态，修复为同一事务内更新床位状态。"), ("退宿管理", "退宿后床位没有释放", "退宿确认只更新申请状态，修复为确认后释放床位。"), ("宿管权限", "普通宿管看到其他楼栋", "楼栋过滤条件缺失，修复为所有查询追加楼栋权限过滤。")]
    },
    {
        "project_id": "P-DORM-REPAIR",
        "project_name": "宿舍报修系统项目",
        "code": "DORM-REPAIR",
        "modules": ["报修提交", "报修派单", "维修处理", "验收评价", "维修材料", "故障分类", "超时提醒", "维修工排班", "统计看板", "消息通知"],
        "focus": "宿舍报修、派单、维修处理、材料记录和验收评价",
        "points": {
            "报修提交": ["报修提交需要填写宿舍位置、故障类型、问题描述和图片。", "报修单提交后状态为待派单。"],
            "报修派单": ["派单优先根据维修工负责区域和当前工单数量分配。", "紧急报修可以人工指定维修工。"],
            "维修处理": ["维修处理需要记录到场时间、处理结果和完成照片。", "维修无法完成时应转为待二次处理。"],
            "验收评价": ["学生确认维修完成后可以评分和填写评价。", "超过 48 小时未验收的工单转为待回访。"],
            "维修材料": ["维修材料记录材料名称、数量和费用。", "材料费第一版只做记录，不接入支付。"],
            "故障分类": ["故障分类包括水电、门窗、家具、网络和其他。", "分类用于派单和统计，不直接决定优先级。"],
            "超时提醒": ["超时提醒用于待派单、处理中和待验收三个状态。", "待派单超时阈值最终调整为 8 小时。"],
            "维修工排班": ["维修工排班按日期和负责区域维护。", "派单时优先选择当日值班维修工。"],
            "统计看板": ["统计看板展示报修数量、完成率、平均处理时长和满意度。", "看板第一版按楼栋和故障类型筛选。"],
            "消息通知": ["消息通知覆盖报修提交、派单、完成和验收提醒。", "通知渠道第一版只做站内消息。"]
        },
        "updates": [
            ("超时提醒", "待派单超时阈值", "最初待派单超过 24 小时提醒管理员。", "试运行发现报修高峰期 24 小时太晚。", "最终将待派单超时阈值调整为 8 小时。"),
            ("验收评价", "自动验收规则", "最初计划 24 小时未验收自动完成。", "用户反馈学生可能未及时查看，24 小时过短。", "最终改为 48 小时未验收转待回访，不直接自动完成。"),
            ("报修派单", "派单策略", "最初按维修工空闲状态随机派单。", "测试发现跨区域派单导致到场慢。", "最终按负责区域优先，再按当前工单数排序派单。"),
            ("维修材料", "材料费处理", "最初计划材料费直接在线支付。", "考虑支付接入复杂度，第一版暂不接入支付。", "最终确认材料费只记录明细，不做支付闭环。"),
            ("消息通知", "通知渠道范围", "最初计划站内消息、短信和微信提醒。", "考虑成本和接口申请周期，外部通知后置。", "最终确认第一版只做站内消息。")
        ],
        "bugs": [("报修提交", "图片上传后报修单保存失败", "图片地址未在事务中回填，修复为先保存附件再创建报修单。"), ("报修派单", "同一维修工被重复派单", "并发派单未加状态校验，修复为派单时锁定待派单记录。"), ("超时提醒", "已完成工单仍然提醒超时", "定时任务没有过滤完成状态，修复为只扫描待派单和处理中。")]
    },
    {
        "project_id": "P-FOOD-RECO",
        "project_name": "美食推荐项目",
        "code": "FOOD-RECO",
        "modules": ["用户画像", "餐厅管理", "菜品标签", "推荐算法", "评分评价", "位置距离", "搜索筛选", "榜单推荐", "优惠套餐", "内容审核"],
        "focus": "餐厅、菜品、口味标签、位置距离、评分和推荐理由",
        "points": {
            "用户画像": ["用户画像基于口味偏好、价格区间、常点品类和收藏记录生成。", "冷启动用户最终采用三题口味问卷加热门榜单。"],
            "餐厅管理": ["餐厅管理维护名称、地址、营业时间、人均价格和商圈。", "下架餐厅不能参与推荐。"],
            "菜品标签": ["菜品标签包括辣度、甜度、荤素、菜系和适合场景。", "标签用于推荐解释和搜索筛选。"],
            "推荐算法": ["推荐算法第一版采用规则打分，综合口味匹配、距离和评分。", "最终确认口味匹配权重最高。"],
            "评分评价": ["评分评价包括总体评分、口味评分、服务评分和环境评分。", "低质量评价需要进入内容审核。"],
            "位置距离": ["位置距离用于计算附近餐厅，默认优先推荐 3 公里内结果。", "用户可以手动放宽距离范围。"],
            "搜索筛选": ["搜索筛选支持菜系、价格、距离、评分和营业状态。", "筛选条件必须和推荐排序共同生效。"],
            "榜单推荐": ["榜单推荐包括附近热门、学生最爱和高评分榜。", "榜单每天离线刷新一次。"],
            "优惠套餐": ["优惠套餐展示套餐价格、适用时间和剩余数量。", "过期套餐不参与推荐。"],
            "内容审核": ["内容审核处理违规评价、虚假餐厅和异常图片。", "审核未通过内容不展示给用户。"]
        },
        "updates": [
            ("用户画像", "冷启动策略", "最初冷启动用户直接展示热门榜单。", "评审认为热门榜单无法体现个人口味。", "最终确认冷启动先用三题口味问卷，再结合热门榜单。"),
            ("推荐算法", "推荐排序权重", "最初距离权重最高。", "测试发现距离太近但评分低的餐厅频繁靠前。", "最终确认排序综合口味匹配、评分和距离，口味匹配权重最高。"),
            ("位置距离", "默认推荐范围", "最初默认推荐 5 公里内餐厅。", "用户反馈范围过大，通勤成本高。", "最终将默认推荐范围调整为 3 公里。"),
            ("内容审核", "评价审核策略", "最初所有评价直接展示。", "发现存在广告和无意义评价。", "最终确认低质量评价进入审核后再展示。"),
            ("榜单推荐", "榜单刷新频率", "最初榜单实时刷新。", "考虑计算成本，实时刷新没有必要。", "最终确认榜单每天离线刷新一次。")
        ],
        "bugs": [("推荐算法", "已下架餐厅仍出现在推荐列表", "推荐候选没有过滤餐厅状态，修复为候选阶段排除下架餐厅。"), ("搜索筛选", "营业状态筛选不生效", "筛选条件没有传入排序服务，修复为统一构造筛选参数。"), ("优惠套餐", "过期套餐仍展示", "套餐过期时间比较使用本地时区错误，修复为统一使用服务端时间。")]
    }
]

raw_headers = ["raw_id", "global_index", "project_id", "project_name", "turn_no", "module", "memory_type", "business_type", "status", "user_message", "assistant_message", "memory_text", "entities", "facts", "decisions", "risks", "supersedes_raw_id", "value_score", "expected_retrieval_weight"]
question_headers = ["question_id", "global_index", "project_id", "project_name", "question_no", "question_type", "question_text", "ambiguous_level", "requires_project_filter", "requires_latest_state", "related_projects", "negative_case", "query_focus_entities", "notes"]
answer_headers = ["answer_id", "question_id", "global_index", "project_id", "expected_raw_ids", "must_hit_raw_ids", "support_raw_ids", "superseded_raw_ids", "expected_answer_points", "expected_behavior", "min_recall_k", "difficulty", "evaluation_notes"]

raw_rows = []
questions = []
answers = []
project_raw = {}

def js(value):
    return json.dumps(value, ensure_ascii=False)

global_raw = 1
for project in projects:
    rows = []
    turn_no = 1
    for module in project["modules"]:
        point1, point2 = project["points"][module]
        templates = [
            ("requirement", "semantic", f"{module}第一版需要覆盖哪些核心能力？", f"{module}第一版重点是：{point1}同时注意：{point2}", 0.86, "high"),
            ("decision", "semantic", f"{module}的 MVP 边界怎么收敛？", f"{module}先保留最小闭环，复杂能力后置。当前决定：{point2}", 0.88, "high"),
            ("task", "episodic", f"{module}可以拆成哪些开发任务？", f"建议拆成字段设计、接口实现、页面联调、异常处理和验收用例五类任务。核心依据是：{point1}", 0.74, "medium"),
            ("risk", "semantic", f"{module}有什么容易影响交付的风险？", f"主要风险是状态同步、权限边界和异常流程遗漏。需要重点验证：{point2}", 0.84, "high"),
            ("bug", "semantic", f"{module}如果出现数据不一致，一般可能是哪类问题？", f"优先检查事务边界、状态更新顺序和查询过滤条件。结合本模块，重点关注：{point1}", 0.82, "high"),
            ("status_update", "episodic", f"{module}目前进度怎么样？", f"{module}需求已经确认，接口和页面可以并行推进，验收重点围绕：{point1}", 0.68, "medium"),
            ("progress", "episodic", f"{module}下一个开发步骤是什么？", "下一步先完成数据字段和接口草稿，再补充页面交互。暂不扩展非 MVP 能力。", 0.60, "medium"),
            ("requirement", "semantic", f"{module}用户侧最关心什么？", f"用户侧最关心流程是否简单、状态是否清晰、异常是否可追踪。这里需要体现：{point1}", 0.78, "high"),
            ("decision", "semantic", f"{module}有没有需要暂缓的能力？", f"有，非核心自动化和外部渠道先暂缓，第一版以可用闭环为主。相关约束是：{point2}", 0.80, "high"),
            ("other", "episodic", f"今天讨论{module}有点累，能简单总结一下吗？", f"可以，{module}当前只需要抓住一个重点：{point1}其余增强能力后续再做。", 0.35, "low")
        ]
        for business_type, memory_type, user_message, assistant_message, score, weight in templates:
            raw_id = f"RAW-{project['code']}-{turn_no:03d}"
            row = {
                "raw_id": raw_id,
                "global_index": global_raw,
                "project_id": project["project_id"],
                "project_name": project["project_name"],
                "turn_no": turn_no,
                "module": module,
                "memory_type": memory_type,
                "business_type": business_type,
                "status": "active",
                "user_message": user_message,
                "assistant_message": assistant_message,
                "memory_text": f"项目：{project['project_name']}。模块：{module}。用户问题：{user_message}。LLM回答：{assistant_message}",
                "entities": js([module, project["focus"]]),
                "facts": js([assistant_message.split("。")[0] + "。"]),
                "decisions": js([assistant_message] if business_type == "decision" else []),
                "risks": js([assistant_message] if business_type == "risk" else []),
                "supersedes_raw_id": "",
                "value_score": f"{score:.2f}",
                "expected_retrieval_weight": weight
            }
            raw_rows.append(row)
            rows.append(row)
            turn_no += 1
            global_raw += 1
    for index in range(15):
        module, bug, fix = project["bugs"][index % len(project["bugs"])]
        raw_id = f"RAW-{project['code']}-{turn_no:03d}"
        user_message = f"{module}出现了“{bug}”，可能是什么原因，怎么修？"
        assistant_message = f"{bug}的定位结论是：{fix}需要补充回归用例，避免同类问题再次出现。"
        row = {
            "raw_id": raw_id,
            "global_index": global_raw,
            "project_id": project["project_id"],
            "project_name": project["project_name"],
            "turn_no": turn_no,
            "module": module,
            "memory_type": "semantic",
            "business_type": "bug",
            "status": "active",
            "user_message": user_message,
            "assistant_message": assistant_message,
            "memory_text": f"项目：{project['project_name']}。模块：{module}。Bug：{bug}。修复结论：{assistant_message}",
            "entities": js([module, bug]),
            "facts": js([fix]),
            "decisions": js([]),
            "risks": js([f"{module}存在回归风险"]),
            "supersedes_raw_id": "",
            "value_score": "0.90",
            "expected_retrieval_weight": "high"
        }
        raw_rows.append(row)
        rows.append(row)
        turn_no += 1
        global_raw += 1
    for module, topic, old_text, middle_text, final_text in project["updates"]:
        chain_ids = []
        update_texts = [old_text, f"针对“{topic}”，补充讨论：{middle_text}", f"再次追问“{topic}”是否影响验收，结论是必须更新验收口径。", f"方案评审后记录“{topic}”进入最终待办。", final_text]
        for step, assistant_message in enumerate(update_texts):
            raw_id = f"RAW-{project['code']}-{turn_no:03d}"
            chain_ids.append(raw_id)
            row = {
                "raw_id": raw_id,
                "global_index": global_raw,
                "project_id": project["project_id"],
                "project_name": project["project_name"],
                "turn_no": turn_no,
                "module": module,
                "memory_type": "semantic" if step in (0, 4) else "episodic",
                "business_type": "decision" if step in (0, 4) else "status_update",
                "status": "superseded" if step == 0 else "active",
                "user_message": f"关于{topic}，第{step + 1}次讨论现在怎么处理？",
                "assistant_message": assistant_message,
                "memory_text": f"项目：{project['project_name']}。模块：{module}。主题：{topic}。讨论结论：{assistant_message}",
                "entities": js([module, topic]),
                "facts": js([assistant_message]),
                "decisions": js([assistant_message] if step in (0, 4) else []),
                "risks": js([]),
                "supersedes_raw_id": chain_ids[0] if step == 4 else "",
                "value_score": "0.92" if step == 4 else "0.70",
                "expected_retrieval_weight": "high" if step == 4 else "medium"
            }
            raw_rows.append(row)
            rows.append(row)
            turn_no += 1
            global_raw += 1
    chats = ["今天先到这里，明天继续整理。", "这个项目名字听起来挺像校园系统。", "先帮我简单鼓励一下开发进度。", "这些模块太多了，稍后再细化。", "先不用写代码，等我确认。", "今天只做口头讨论。", "这个页面后面再美化。", "先记录一下，没有新决策。", "暂时没有更多问题。", "换个话题聊一下项目展示。"]
    for chat in chats:
        module = project["modules"][(turn_no - 1) % len(project["modules"])]
        raw_id = f"RAW-{project['code']}-{turn_no:03d}"
        assistant_message = f"已记录，这条内容不包含新的业务决策，后续仍以{project['project_name']}已确认的模块设计为准。"
        row = {
            "raw_id": raw_id,
            "global_index": global_raw,
            "project_id": project["project_id"],
            "project_name": project["project_name"],
            "turn_no": turn_no,
            "module": module,
            "memory_type": "episodic",
            "business_type": "other",
            "status": "active",
            "user_message": chat,
            "assistant_message": assistant_message,
            "memory_text": f"项目：{project['project_name']}。闲聊或低价值记录：{chat}。回复：{assistant_message}",
            "entities": js([project["project_name"]]),
            "facts": js([]),
            "decisions": js([]),
            "risks": js([]),
            "supersedes_raw_id": "",
            "value_score": "0.20",
            "expected_retrieval_weight": "low"
        }
        raw_rows.append(row)
        rows.append(row)
        turn_no += 1
        global_raw += 1
    assert len(rows) == 150
    project_raw[project["code"]] = rows

def ids_by(code, module, limit=2):
    return [row["raw_id"] for row in project_raw[code] if row["module"] == module][:limit]

def update_ids(code, chain_index):
    start = 116 + chain_index * 5
    return [f"RAW-{code}-{number:03d}" for number in range(start, start + 5)]

irrelevant_questions = ["这个项目的股票交易撮合规则是什么？", "火箭发动机燃料配比如何设计？", "区块链挖矿收益如何预测？", "视频剪辑软件的转场模板怎么做？", "智能手表的心率传感器硬件怎么选型？"]
q_global = 1
for project in projects:
    code = project["code"]
    project_id = project["project_id"]
    project_name = project["project_name"]
    for question_no, module in enumerate(project["modules"], start=1):
        qid = f"Q-{code}-RELATED-{question_no:03d}"
        aid = f"A-{code}-RELATED-{question_no:03d}"
        raw_ids = ids_by(code, module)
        questions.append({
            "question_id": qid,
            "global_index": q_global,
            "project_id": project_id,
            "project_name": project_name,
            "question_no": question_no,
            "question_type": "current_related",
            "question_text": f"{module}第一版的核心设计要点是什么？",
            "ambiguous_level": "low",
            "requires_project_filter": "true",
            "requires_latest_state": "false",
            "related_projects": js([]),
            "negative_case": "false",
            "query_focus_entities": js([module]),
            "notes": f"测试{module}模块当前项目召回"
        })
        answers.append({
            "answer_id": aid,
            "question_id": qid,
            "global_index": q_global,
            "project_id": project_id,
            "expected_raw_ids": js(raw_ids),
            "must_hit_raw_ids": js(raw_ids[:1]),
            "support_raw_ids": js(raw_ids[1:]),
            "superseded_raw_ids": js([]),
            "expected_answer_points": f"应围绕{project_name}的{module}回答核心能力、MVP边界和验收重点。",
            "expected_behavior": "answer_with_context",
            "min_recall_k": "5",
            "difficulty": "easy" if question_no <= 4 else "medium",
            "evaluation_notes": "应优先命中当前项目同模块记录。"
        })
        q_global += 1
    cross_questions = [("登录模块怎么设计才合适？", "high"), ("通知提醒最后怎么定的？", "high"), ("管理员权限应该怎么控制？", "medium"), ("统计看板要看哪些指标？", "medium"), ("用户提交信息后状态怎么流转？", "high"), ("图片或附件上传失败怎么处理？", "medium"), ("评价和反馈模块要不要第一版就做？", "high"), ("消息渠道是否需要短信？", "medium"), ("移动端页面应该优先做哪些？", "medium"), ("异常数据怎么避免影响业务流程？", "high")]
    for question_no, (question_text, ambiguous_level) in enumerate(cross_questions, start=11):
        if "通知" in question_text or "短信" in question_text:
            module = "通知提醒" if code == "DORM-STAFF" else "消息通知" if code == "DORM-REPAIR" else "内容审核"
        elif "统计" in question_text:
            module = "数据统计" if code == "DORM-STAFF" else "统计看板" if code == "DORM-REPAIR" else "榜单推荐"
        elif "权限" in question_text or "登录" in question_text or "管理员" in question_text:
            module = "宿管权限" if code == "DORM-STAFF" else "报修派单" if code == "DORM-REPAIR" else "用户画像"
        elif "评价" in question_text:
            module = "访客登记" if code == "DORM-STAFF" else "验收评价" if code == "DORM-REPAIR" else "评分评价"
        elif "图片" in question_text:
            module = "学生档案" if code == "DORM-STAFF" else "报修提交" if code == "DORM-REPAIR" else "内容审核"
        elif "状态" in question_text:
            module = "床位管理" if code == "DORM-STAFF" else "维修处理" if code == "DORM-REPAIR" else "餐厅管理"
        else:
            module = project["modules"][1]
        qid = f"Q-{code}-CROSS-{question_no:03d}"
        aid = f"A-{code}-CROSS-{question_no:03d}"
        raw_ids = ids_by(code, module)
        questions.append({
            "question_id": qid,
            "global_index": q_global,
            "project_id": project_id,
            "project_name": project_name,
            "question_no": question_no,
            "question_type": "cross_project_ambiguous",
            "question_text": question_text,
            "ambiguous_level": ambiguous_level,
            "requires_project_filter": "true",
            "requires_latest_state": "false",
            "related_projects": js([item["project_id"] for item in projects if item["project_id"] != project_id]),
            "negative_case": "false",
            "query_focus_entities": js([module]),
            "notes": "故意设置跨项目共享词，测试项目过滤和消歧。"
        })
        answers.append({
            "answer_id": aid,
            "question_id": qid,
            "global_index": q_global,
            "project_id": project_id,
            "expected_raw_ids": js(raw_ids),
            "must_hit_raw_ids": js(raw_ids[:1]),
            "support_raw_ids": js(raw_ids[1:]),
            "superseded_raw_ids": js([]),
            "expected_answer_points": f"应限定在{project_name}语境下回答，不能混用其他项目的同名模块或相似概念。",
            "expected_behavior": "answer_with_cross_project_disambiguation",
            "min_recall_k": "5",
            "difficulty": "hard" if ambiguous_level == "high" else "medium",
            "evaluation_notes": "重点观察是否错误召回其他项目记录。"
        })
        q_global += 1
    update_questions = []
    for chain_index, (_, topic, *_rest) in enumerate(project["updates"]):
        ids = update_ids(code, chain_index)
        update_questions.append((topic, f"{topic}最后是怎么定的？", ids))
        update_questions.append((topic, f"关于{topic}，旧方案是否还有效？", ids))
    for question_no, (topic, question_text, ids) in enumerate(update_questions[:10], start=21):
        qid = f"Q-{code}-UPDATE-{question_no:03d}"
        aid = f"A-{code}-UPDATE-{question_no:03d}"
        questions.append({
            "question_id": qid,
            "global_index": q_global,
            "project_id": project_id,
            "project_name": project_name,
            "question_no": question_no,
            "question_type": "multi_turn_update",
            "question_text": question_text,
            "ambiguous_level": "medium",
            "requires_project_filter": "true",
            "requires_latest_state": "true",
            "related_projects": js([]),
            "negative_case": "false",
            "query_focus_entities": js([topic]),
            "notes": "测试多轮更新和旧结论替代识别。"
        })
        answers.append({
            "answer_id": aid,
            "question_id": qid,
            "global_index": q_global,
            "project_id": project_id,
            "expected_raw_ids": js([ids[-1]] + ids[1:4]),
            "must_hit_raw_ids": js([ids[-1]]),
            "support_raw_ids": js(ids[1:4]),
            "superseded_raw_ids": js([ids[0]]),
            "expected_answer_points": f"应以{topic}的最后一次确认记录为准，说明早期方案已被后续结论替代。",
            "expected_behavior": "answer_latest_state",
            "min_recall_k": "5",
            "difficulty": "hard",
            "evaluation_notes": "如果只命中旧方案，视为最新状态识别失败。"
        })
        q_global += 1
    for question_no, question_text in enumerate(irrelevant_questions, start=31):
        qid = f"Q-{code}-IRRELEVANT-{question_no:03d}"
        aid = f"A-{code}-IRRELEVANT-{question_no:03d}"
        questions.append({
            "question_id": qid,
            "global_index": q_global,
            "project_id": project_id,
            "project_name": project_name,
            "question_no": question_no,
            "question_type": "irrelevant",
            "question_text": question_text,
            "ambiguous_level": "high",
            "requires_project_filter": "true",
            "requires_latest_state": "false",
            "related_projects": js([]),
            "negative_case": "true",
            "query_focus_entities": js([]),
            "notes": "无关问题，测试拒答和防幻觉。"
        })
        answers.append({
            "answer_id": aid,
            "question_id": qid,
            "global_index": q_global,
            "project_id": project_id,
            "expected_raw_ids": js([]),
            "must_hit_raw_ids": js([]),
            "support_raw_ids": js([]),
            "superseded_raw_ids": js([]),
            "expected_answer_points": "当前项目资料中未找到该问题相关依据，应提示缺少上下文，不应编造答案。",
            "expected_behavior": "no_relevant_context",
            "min_recall_k": "5",
            "difficulty": "medium",
            "evaluation_notes": "如果高置信命中业务记录，说明负样本过滤较弱。"
        })
        q_global += 1

for filename, headers, rows in [
    ("rag_raw_dialogues_v1.csv", raw_headers, raw_rows),
    ("rag_questions_v1.csv", question_headers, questions),
    ("rag_gold_answers_v1.csv", answer_headers, answers)
]:
    with (base / filename).open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

assert len(raw_rows) == 450
assert len(questions) == 105
assert len(answers) == 105
assert Counter(row["project_id"] for row in raw_rows) == Counter({"P-DORM-STAFF": 150, "P-DORM-REPAIR": 150, "P-FOOD-RECO": 150})
question_type_counter = Counter((row["project_id"], row["question_type"]) for row in questions)
for project in projects:
    assert question_type_counter[(project["project_id"], "current_related")] == 10
    assert question_type_counter[(project["project_id"], "cross_project_ambiguous")] == 10
    assert question_type_counter[(project["project_id"], "multi_turn_update")] == 10
    assert question_type_counter[(project["project_id"], "irrelevant")] == 5
raw_ids = {row["raw_id"] for row in raw_rows}
question_ids = {row["question_id"] for row in questions}
assert {row["question_id"] for row in answers} == question_ids
for row in raw_rows:
    for column in ["entities", "facts", "decisions", "risks"]:
        json.loads(row[column])
for row in questions:
    for column in ["related_projects", "query_focus_entities"]:
        json.loads(row[column])
for row in answers:
    for column in ["expected_raw_ids", "must_hit_raw_ids", "support_raw_ids", "superseded_raw_ids"]:
        ids = json.loads(row[column])
        assert all(raw_id in raw_ids for raw_id in ids), (row["question_id"], column, ids)
    if row["expected_behavior"] == "no_relevant_context":
        assert json.loads(row["expected_raw_ids"]) == []
        assert json.loads(row["must_hit_raw_ids"]) == []
    else:
        assert json.loads(row["must_hit_raw_ids"])

print("CSV generation and validation passed")
print("raw_rows=450, questions=105, answers=105")
