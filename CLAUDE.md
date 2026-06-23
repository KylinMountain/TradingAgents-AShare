# 强制流程（每次代码任务必须执行）

**收到代码任务后，按对应场景顺序执行，不得跳过任何步骤：**

| 场景 | 步骤1 | 步骤2 | 步骤3 | 步骤4 |
|------|-------|-------|-------|-------|
| 修bug | Skill(systematic-debugging) | Skill(test-driven-development) | 写修复代码 | Skill(verification-before-completion) |
| 新功能 | Skill(brainstorming) | Skill(test-driven-development) | 写实现代码 | Skill(verification-before-completion) |
| 提交代码 | Skill(chinese-code-review) | Skill(chinese-commit-conventions) | git commit | — |

**规则：上一步 Skill 未执行完毕，不得进入下一步。**

---

<!-- superpowers-zh:begin (do not edit between these markers) -->
# Superpowers-ZH 中文增强版

本项目已安装 superpowers-zh 技能框架（20 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.claude/skills/` 目录，完整清单及描述见系统注入的可用技能列表，此处不赘述。

## 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。绝不要用 Read 工具读取 SKILL.md 文件。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。
<!-- superpowers-zh:end -->
