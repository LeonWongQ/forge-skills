# Forge 体系说明

Forge 是面向 Codex、Claude Code 和 Cursor 的工程工具箱。
它将工程 Skills、共享规则、任务路由、验证工具和项目学习分开维护，
按任务组合需要的模块。

安装与日常操作请先看 [快速入门](QUICKSTART.md)。
本文面向需要了解设计和集成边界的使用者。

## 源码与安装目录

源码由 `.forge-skill/forge`、`.forge-skill/skills` 等目录维护。
项目安装后，宿主通过 `.codex/`、`.claude/` 或 `.cursor/`
中的链接访问 `forge`、`skills` 和 `forge-data`。
源码目录与宿主安装目录不能混用。

## 核心分层

以下路径相对于 `.forge-skill/forge`：

| 模块 | 职责 |
|---|---|
| `CLAUDE.md` | 证据、范围、验证等共享原则 |
| `AUTOLOAD.md` | 按需加载和宿主能力归属 |
| `engine/` | 发现、取证、规划、执行、验证、交付等阶段 |
| `runtime/` | 路由、执行契约与交接规则 |
| `behaviors/` | 评审、诊断、重构、文档等任务视角 |
| `domains/` | Java、Spring、数据库、前端等技术领域 |
| `templates/`、`checklists/` | 输出结构与交付检查 |
| `packs/` | 高频技术场景的预组装模块 |
| `registry/` | 模块身份、路径、路由与契约的机器可读配置 |
| `scripts/` | 验证、安装、评估等工具 |

Skill 位于相邻的 `../skills/`，是具体任务的执行入口；
Pack 为某类技术场景补充组合规则。完整清单见 [Skills README](../skills/README.md)。

## 按需加载

仓库可见不代表所有规则同时激活。执行时先遵守宿主归属策略，再选择
适用的 Skill、Pack、领域、流程与输出要求。小任务使用较少模块，
复杂任务按实际证据扩展。

明确的宿主 Skill 调用和原生专长应保留宿主归属。
`forge ask` 对普通工程请求返回分派决定，宿主负责执行任务；
明确的学习服务和 Runtime 请求则有专用处理。

## 当前已有能力

- CLI 路由、推荐、模块组合和健康检查。
- 注册表、路径、引用、Pack、语义与契约 fixture 校验。
- Context Manifest、Context Bundle 和 Runtime Envelope。
- 外部宿主请求 / 结果交接与结构化输出校验。
- 多宿主全局 / 项目 Skill 安装。
- 项目隔离的学习采集、审核页面、分批 AI Summary 和 Overlay 管理。
- 本地质量门禁，以及 Windows、Ubuntu、macOS 的 GitHub Actions 配置。

具体命令与限制见 [脚本说明](scripts/README.md)。
注册表投影同步不等于自动从源码推导所有路由规则；
确定性验证也不等于真实模型行为已经通过评估。

## 项目学习

学习改善项目中 Skill 的外部指导，不修改模型参数或全局 Skill。
采集默认关闭，启用后仍需人工审核证据和 AI Summary，
再创建 Overlay、评估、发布并手动激活。

生成的 Overlay 只读，复制后可编辑。无效 Overlay 不影响原始 Skill。
Hook 配置和捕获证据应按宿主分别确认，不能仅凭安装状态认定采集成功。

详见 [学习生命周期](../skills/learning-collector/references/lifecycle.md)。

## 集成入口

- [BOOTSTRAP](BOOTSTRAP.md)：消费者项目安装与指令入口。
- [GETTING-STARTED](GETTING-STARTED.md)：模块组合方法。
- [ARCHITECTURE](ARCHITECTURE.md)：架构设计。
- [中文使用说明](docs/forge-user-guide.zh-CN.md)：CLI 操作。
