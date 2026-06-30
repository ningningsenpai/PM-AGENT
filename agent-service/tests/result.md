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

待写入新版 `UserHabitsPrompt` 后补充。

- 对话轮次：

  待测试。

- 问题总结：

  待测试。

- 改进方向：

  待测试。
