---
name: pm-agent-figma-prototyper
description: Figma MCP prototyping skill for the PM-Agent intelligent project management Agent platform. Use this skill whenever the user asks to create, update, organize, or refine Figma page prototypes, formal frontend design drafts, screen flows, interaction states, or design-to-code reference screens for PM-Agent. It preserves the confirmed Warm Linear visual direction, keeps user-facing Figma canvases free of design rationale, and enforces the project’s vertical screen arrangement and right-side interaction-state layout rules.
metadata:
  status: active
  language: en-US
  owner_module: frontend
  related_skills:
    - pm-agent-frontend-builder
  related_docs:
    - docs/01-开发规划.md
    - docs/10-第1阶段业务流程与验收清单.md
---

# PM-Agent Figma Prototyping Skill

## Goal

Create formal Figma screen prototypes for PM-Agent that can directly guide later Vue 3 + Naive UI frontend implementation. The output should look like product screens, not design notes. Preserve the confirmed PM-Agent **Warm Linear workspace style** while organizing screens for later code generation and interaction review.

Use this skill together with the official Figma MCP skills:

- Load `figma:figma-use` before every `use_figma` write call.
- Load `figma:figma-generate-design` when building full screens or multi-section layouts.
- Load `figma:figma-create-new-file` before creating a new Figma file.
- Use `pm-agent-frontend-builder` for frontend architecture, component boundaries, and visual tokens.

---

## 1. When to use

Use this skill when the user asks to:

- Create a formal frontend design draft in Figma;
- Draw PM-Agent screen prototypes using Figma MCP;
- Convert confirmed PM-Agent visual direction into concrete screens;
- Create design-to-code reference screens for later Vue implementation;
- Organize multiple business screens and interaction states in one Figma file;
- Update or refine PM-Agent Figma screens while preserving the Warm Linear style.

Do not use this skill for generic frontend planning without Figma output. Use `pm-agent-frontend-builder` instead.

---

## 2. Confirmed visual direction

Use the confirmed **Warm Linear workspace style**:

- Warm white/off-white background: `#F8FAF5`, `#FFFFFF`;
- PM Blue: `#2F7DF6`, `#1F66D1` for primary actions, selected navigation, progress;
- PM Green: `#26B983`, `#15966A` for healthy progress and completed states;
- PM Yellow: `#F5B83D`, `#D8911E` for Agent insight, risk hints, and attention clues;
- Main text: `#132033`;
- Secondary text: `#667085`;
- Muted text: `#98A2B3`.

Keep the approximate visual ratio: warm white/background 65%, blue 20%, green 10%, yellow 5%.

Brand idea:

> Turn project status into traceable execution clues.

Logo direction:

- Dark rounded mark;
- Blue execution orbit;
- Green status node;
- Yellow insight node;
- Trace-like connection line.

Use the “execution clue line” motif in UI cards, state strips, timelines, progress indicators, and Agent insight areas.

---

## 3. Formal Figma canvas rules

A formal Figma design draft is not a thinking board. It should contain product UI screens only.

### 3.1 Do not put these on the visible canvas

Avoid visible text such as:

- Design rationale;
- Visual design explanation;
- Thinking notes;
- “Why this layout” explanations;
- Internal implementation notes;
- Codex/task process notes;
- Color-token documentation panels unless the user explicitly asks for a design-system page.

Frame names may be descriptive for designers and developers, but visible text inside frames should look like real product UI.

### 3.2 Use realistic mock data

Use mock data that can plausibly appear in the product. Prefer PM-Agent business terms from the glossary:

- 项目, 需求, 任务, 迭代, 风险, 报告, Agent, Trace;
- 示例项目: `PM-Agent 平台 MVP`, `项目管理后台改版`, `风险分析实验`;
- 示例用户: `宁宁`, `ning`, `admin@pm-agent.local`.

Avoid placeholder-only content like `Lorem ipsum`, `Title`, `Text`, or `Button`.

### 3.3 Screen arrangement

Organize screens in the same Figma page using this layout rule:

1. Different business areas are arranged **from top to bottom**.
2. Interaction states for the same business area are arranged **to the right of the base screen**.
3. If the interaction change is small, draw only the changed component state and connect it with an arrow label.
4. If the interaction changes most of the screen, create a full additional screen to the right.
5. If a screen is controversial or uncertain, create multiple alternatives side by side and label them `备选 A`, `备选 B`, etc. Keep labels short and non-disruptive.

Recommended spacing:

- Screen width: 1440px for desktop web pages;
- Base frame height: 900–1024px depending on content;
- Horizontal gap between interaction states: 120–180px;
- Vertical gap between business groups: 160–240px.

### 3.4 Naming

Use clear node names:

- Page: `PM-Agent 正式界面设计稿`;
- Business group section: `业务组 / 系统介绍`, `业务组 / 用户认证`;
- Screens: `系统介绍页 / 默认`, `登录页 / 默认`, `注册页 / 切换后`;
- Interaction arrows: `交互箭头 / 点击注册账号`.

Visible labels may show screen names only when they help review interaction states. Do not add long explanations.

---

## 4. Screen requirements

### 4.1 System introduction page

A formal system introduction page should usually include:

- Header with logo, navigation, and login/register entry;
- Hero area with product positioning and primary CTA;
- Product UI preview or dashboard preview;
- Value cards focused on project, task, risk, Agent insight, and report;
- Warm Linear background glows and trace motifs;
- CTA leading to login/register.

Avoid exposing design intent. The page should read like a real landing or introduction page.

### 4.2 User auth screens

Draw login and register as formal app screens:

- Login screen as the base state;
- Register screen to the right as the interaction state after clicking “注册账号”;
- Optional small component states to the right if needed: validation error, password visible, login loading;
- Use real Chinese UI copy and form labels;
- Keep auth screen bolder than internal app screens, but do not make it decorative-only.

Recommended fields:

- Login: 用户名/邮箱, 密码, 记住登录, 忘记密码, 登录 button, 注册入口;
- Register: 显示名称, 用户名/邮箱, 密码, 确认密码, 同意协议, 注册 button, 返回登录.

---

## 5. Figma MCP workflow

1. Inspect the target file first with `use_figma` or metadata tools.
2. If a new file is needed, load `figma:figma-create-new-file`, call `whoami` if necessary, then call `create_new_file`.
3. Before writing, load `figma:figma-use`; for full screens, also load `figma:figma-generate-design`.
4. Use top-level frames for each screen. Keep content inside the frame, not scattered across the page.
5. Use realistic final UI copy, not planning notes.
6. Return all created/mutated node IDs from every `use_figma` call.
7. Validate structure with `get_metadata` and visual output with `get_screenshot` after major writes.
8. If `use_figma` errors, stop, read the error, fix the script, then retry. Failed scripts are atomic.

---

## 6. Practical build guidance

### Fonts

- In actual frontend implementation, prefer `MiSans`, `HarmonyOS Sans SC`, or `Microsoft YaHei`.
- In Figma MCP scripts, verify available fonts. If Chinese fonts are unavailable, use `Inter` and keep Chinese text readable.

### Layout

Use fixed desktop frames for formal design drafts. Absolute positioning is acceptable for static design screens, but keep related UI elements grouped in frames. For reusable or text-heavy sections, prefer auto-layout if practical.

### Visual restraint

Warm Linear allows bold brand presence in intro/auth pages, but internal screens should stay clean and implementation-friendly. Avoid cluttered decoration, purple AI gradients, and generic admin-table-only layouts.

---

## 7. Response format after drawing

After creating or updating Figma screens, respond in Chinese with:

```markdown
## 已完成
## Figma 文件
## 本轮生成界面
## 交互关系
## 关键规范落实
## 后续建议
```

Mention the Figma URL and the main frame names or node IDs. Keep the response concise and factual.
