# BaseSkill-CN 使用说明

> **重要：本目录不作为 Claude Code 正式开发调用 Skill。**

`BaseSkill-CN/` 是 PM-Agent 项目级 Skill 的中文参考副本，仅用于和正式英文 Skill 进行对照审阅、人工校对、术语确认与规则回查。

## 正式开发 Skill 目录

后续开发、设计、评审与实现时，应优先使用项目级正式 Skill：

```text
.claude/skills/
```

正式 Skill 使用英文 `SKILL.md` 描述与触发说明，以便更符合 Claude Code 的 Skill 调用规范；但正式 Skill 内仍会保留 PM-Agent 的项目约束，例如：

- 对话、项目文档、代码注释、错误提示统一使用中文；
- 不擅自替换既定技术选型；
- Agent 不直接操作数据库；
- 高风险操作必须人工确认；
- 按阶段引入中间件和后置能力。

## 本目录用途

本目录仅用于：

1. 对照审阅 `.claude/skills/` 中的英文正式 Skill；
2. 检查英文 Skill 是否遗漏中文原始规则；
3. 校对术语、阶段边界、技术红线和输出格式；
4. 作为中文语义参考，帮助用户快速理解 Skill 设计意图。

## 禁止用途

本目录不应用于：

- 作为后续开发时的优先调用 Skill；
- 作为 Claude Code 自动触发的正式 Skill 来源；
- 替代 `.claude/skills/` 中的英文正式 Skill；
- 在未同步正式 Skill 的情况下单独修改规则。

## 维护规则

- 正式来源：`.claude/skills/`；
- 中文参考：`BaseSkill-CN/`；
- 若需要调整 Skill 规则，应优先修改 `.claude/skills/`；
- 如需保留中英文一致性，再同步更新本目录对应中文参考文件；
- `_base-template/` 仅为中文参考模板，不参与正式开发调用。
