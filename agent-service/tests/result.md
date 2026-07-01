# 用户习惯 Prompt 测试记录

## 版本1

- 提示词：

当前 `UserHabitsPrompt.USER_HABITS` 版本，职责为从 `existing_habits_json` 与 `new_content` 中识别用户习惯并融合，输出 `user_habits`、`changes`、`ignored_items` 三段 JSON。

- 对话轮次：

  1. 对话1：我喜欢上午喝茶，下午喝咖啡

     记录的 json 内容：

     ```json
     {
       "user_habits": [
         {
           "id": "daily_drink",
           "category": "life",
           "habit": "早上喜欢喝茶，下午喜欢喝咖啡。",
           "status": "active",
           "confidence": "high",
           "evidence": [
             {
               "source": "new_content",
               "quote": "我喜欢上午喝茶，下午喝咖啡。"
             }
           ],
           "previous_versions": []
         }
       ],
       "changes": [
         {
           "type": "added",
           "habit_id": "daily_drink",
           "summary": "根据新输入内容添加了用户的生活习惯：早上喜欢喝茶，下午喜欢喝咖啡。"
         }
       ],
       "ignored_items": []
     }
     ```

  2. 对话2：我发现下午喝咖啡容易导致晚上睡不着，于是我把上下午的习惯互换了一下

     记录的 json 内容：

     ```json
     {
       "user_habits": [
         {
           "id": "daily_drink",
           "category": "life",
           "habit": "早上喜欢喝茶，晚上喜欢喝咖啡。",
           "status": "evolved",
           "confidence": "high",
           "evidence": [
             {
               "source": "new_content",
               "quote": "我发现下午喝咖啡容易导致晚上睡不着，于是我把上下午的习惯互换了一下"
             },
             {
               "source": "existing_habits_json",
               "quote": "早上喜欢喝茶，下午喜欢喝咖啡。"
             }
           ],
           "previous_versions": [
             {
               "habit": "早上喜欢喝茶，下午喜欢喝咖啡。",
               "reason": "新输入内容表明用户更改了习惯以改善睡眠质量。"
             }
           ]
         }
       ],
       "changes": [
         {
           "type": "evolved",
           "habit_id": "daily_drink",
           "summary": "根据新输入内容，将原有的下午喝茶、晚上喝咖啡的习惯调整为早上喝茶、晚上喝咖啡，并记录了变化原因。"
         }
       ],
       "ignored_items": []
     }
     ```

  3. 对话3：医生告诉我说我摄入太多的茶多酚和咖啡因，导致我晚上神经亢奋，然后第二天精神衰弱，为此我现在只喝白开水

     记录的 json 内容：

     ```json
     {
       "user_habits": [
         {
           "id": "daily_drink",
           "category": "life",
           "habit": "现在偏好饮用白开水，减少茶和咖啡的摄入。",
           "status": "evolved",
           "confidence": "high",
           "evidence": [
             {
               "source": "new_content",
               "quote": "医生告诉我说我摄入太多的茶多酚和咖啡因，导致我晚上神经亢奋，然后第二天精神衰弱，为此我现在只喝白开水下"
             },
             {
               "source": "existing_habits_json",
               "quote": "早上喜欢喝茶，下午喜欢喝咖啡。现在只喝白开水"
             }
           ],
           "previous_versions": [
             {
               "habit": "早上喜欢喝茶，下午喜欢喝咖啡。",
               "reason": "新输入内容表明用户因医生建议调整了饮水习惯以改善健康状况。"
             },
             {
               "habit": "早上喜欢喝茶，晚上喜欢喝咖啡。",
               "reason": "用户更改了习惯以改善睡眠质量。"
             }
           ]
         }
       ],
       "changes": [
         {
           "type": "evolved",
           "habit_id": "daily_drink",
           "summary": "根据医生的建议和新输入内容，用户的饮水习惯从下午喝咖啡、晚上喝茶调整为现在只饮用白开水，并记录了变化原因。"
         }
       ],
       "ignored_items": []
     }
     ```

- 问题总结：

  1. 出现无依据改写：第 2 轮把“上下午互换”错误写成“早上喝茶，晚上喝咖啡”，凭空引入“晚上”。
  2. 历史版本被幻觉补全：`changes.summary` 中出现“下午喝茶、晚上喝咖啡”等历史中不存在的状态。
  3. 证据引用不严格：第 3 轮 `new_content.quote` 多出“下”，`existing_habits_json.quote` 把旧习惯与新结论拼接成不存在的证据。
  4. `previous_versions` 不够可信：记录了真实旧版本，也混入了基于错误中间态的版本。
  5. `changes.summary` 过度重写历史，没有只描述“本轮输入导致的变化”。
  6. 对“互换”这类指代关系缺少约束，没有要求基于已有 JSON 做确定性推导。

- 改进方向：

  1. 增加“证据忠实性”规则：`evidence.quote` 必须原样摘录或明确标注为摘要，禁止拼接多个来源。
  2. 增加“历史不可改写”规则：`previous_versions` 只能来自已有 JSON 的真实 `habit` 字段，不能由模型重构。
  3. 增加“指代解析”规则：遇到“互换、改成、换一下、以后不再”等变化表达时，必须先根据旧习惯推导新状态；无法确定时降为 `pending_review`。
  4. 增加“变化摘要只描述本轮变化”规则：`changes.summary` 不能引入未在旧 JSON 或本轮输入出现的状态。
  5. 增加“当前有效习惯唯一性”规则：同一 `id` 下只保留当前有效 `habit`，旧版本进入 `previous_versions`。
  6. 增加“健康原因与偏好结果分离”规则：原因可进入 `evidence` 或 `reason`，当前习惯只写稳定偏好本身。

## 版本2

- 提示词：

当前新版 `UserHabitsPrompt.USER_HABITS`，已补充证据忠实性、历史不可改写、指代解析、变化摘要聚焦本轮变化、当前有效习惯唯一性等约束。

- 对话轮次：

  1. 对话1：我喜欢上午喝茶，下午喝咖啡.

     记录的 json 内容（`0-user_habits.json`）：

     ```json
     {
       "user_habits": [
         {
           "id": "work-coffee-tea-pattern",
           "category": "life",
           "habit": "喜欢上午喝茶，下午喝咖啡。",
           "status": "active",
           "confidence": "high",
           "evidence": [
             {
               "source": "new_content",
               "quote": "我喜欢上午喝茶，下午喝咖啡."
             }
           ],
           "previous_versions": []
         }
       ],
       "changes": [
         {
           "type": "added",
           "habit_id": "work-coffee-tea-pattern",
           "summary": "根据 new_content 添加了当前有效的生活习惯。"
         }
       ],
       "ignored_items": []
     }
     ```

  2. 对话2：我发现下午喝咖啡容易导致晚上睡不着，于是我把上下午的习惯互换了一下。

     记录的 json 内容（`2-user_habits.json`）：

     ```json
     {
       "user_habits": [
         {
           "id": "work-coffee-tea-pattern",
           "category": "life",
           "habit": "上午喝咖啡，下午喝茶。",
           "status": "evolved",
           "confidence": "high",
           "evidence": [
             {
               "source": "new_content",
               "quote": "我发现下午喝咖啡容易导致晚上睡不着，于是我把上下午的习惯互换了一下。"
             }
           ],
           "previous_versions": [
             {
               "habit": "喜欢上午喝茶，下午喝咖啡。",
               "reason": "为了改善晚上睡眠质量而进行了调整。"
             }
           ]
         }
       ],
       "changes": [
         {
           "type": "evolved",
           "habit_id": "work-coffee-tea-pattern",
           "summary": "根据 new_content 将上午喝茶，下午喝咖啡的习惯改为上午喝咖啡，下午喝茶。"
         }
       ],
       "ignored_items": []
     }
     ```

  3. 对话3：医生告诉我说我摄入太多的茶多酚和咖啡因，导致我晚上神经亢奋，然后第二天精神衰弱，为此我现在只喝白开水。

     记录的 json 内容（`1-user_habits.json`）：

     ```json
     {
       "user_habits": [
         {
           "id": "work-coffee-tea-pattern",
           "category": "life",
           "habit": "上午喝咖啡，下午喝茶。",
           "status": "evolved",
           "confidence": "high",
           "evidence": [
             {
               "source": "new_content",
               "quote": "医生告诉我说我摄入太多的茶多酚和咖啡因，导致我晚上神经亢奋，然后第二天精神衰弱，为此我现在只喝白开水。"
             }
           ],
           "previous_versions": [
             {
               "habit": "上午喝咖啡，下午喝茶。",
               "reason": "根据 new_content 中医生的建议进行调整。"
             },
             {
               "habit": "喜欢上午喝茶，下午喝咖啡。",
               "reason": "为了改善晚上睡眠质量而进行了调整。"
             }
           ]
         }
       ],
       "changes": [
         {
           "type": "evolved",
           "habit_id": "work-coffee-tea-pattern",
           "summary": "根据 new_content 中医生的建议，将上午喝咖啡，下午喝茶的习惯改为只喝白开水。"
         }
       ],
       "ignored_items": []
     }
     ```

- 问题总结：

  1. 第 2 轮“上下午互换”推导正确，当前习惯从“上午喝茶，下午喝咖啡”变为“上午喝咖啡，下午喝茶”，未再凭空引入“晚上”。
  2. 证据引用明显改善，`evidence.quote` 基本保持对 `new_content` 的原文摘录，没有再拼接旧习惯与新结论。
  3. 第 3 轮存在关键错误：`changes.summary` 已写出“改为只喝白开水”，但 `user_habits[0].habit` 仍保留为“上午喝咖啡，下午喝茶”，当前有效习惯没有更新。
  4. 第 3 轮 `previous_versions` 把“上午喝咖啡，下午喝茶”作为基于医生建议调整后的历史版本，原因不准确；它应是第 2 轮旧版本，而不是第 3 轮变化结果。
  5. `changes.summary` 使用了 `new_content` 这类来源标识，表达偏技术化，可读性不如直接描述“根据本轮输入”。
  6. 输出文件命名与对话顺序不一致：`1-user_habits.json` 对应第 3 轮，`2-user_habits.json` 对应第 2 轮，后续测试记录需要按内容重新排序核对。

- 改进方向：

  1. 增加“变化结果一致性”规则：当 `changes.summary` 描述当前习惯已变更时，`user_habits[].habit` 必须同步写入变更后的当前有效习惯。
  2. 强化“当前习惯优先”规则：遇到“现在只……”“以后只……”“不再……”等明确覆盖表达时，应直接覆盖当前 `habit`，旧习惯进入 `previous_versions`。
  3. 调整 `previous_versions.reason` 生成规则：原因应说明旧版本为何被替换，不能把本轮新原因写成旧版本自身的形成原因。
  4. 约束 `changes.summary` 面向人类阅读，避免暴露 `new_content`、`existing_habits_json` 等内部字段名。
  5. 检查测试脚本的结果文件写入顺序，确保文件序号与对话轮次一致，避免人工复盘时误判。
