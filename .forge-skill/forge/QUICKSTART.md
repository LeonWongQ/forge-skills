# Forge 快速入门 / Quick Start

Forge 为 Codex、Claude Code 和 Cursor 提供工程 Skills、任务路由和项目学习。
下面区分直接使用 Skill 与开发 CLI，两种安装目的不同。

## 1. 安装宿主 Skills

需要 Python 3.11+。从源码仓库根目录执行：

Windows：

```powershell
install-skills.bat --client codex --scope global
```

macOS / Linux：

```bash
python .forge-skill/forge/scripts/sync-agent-skills.py --client codex --scope global
```

将 `codex` 换成 `claude` 或 `cursor` 即可选择其他宿主。
项目安装使用 `--scope project --project <path>`；添加 `--check` 可预览。
宿主加载安装后的 Skills 后，可请求代码评审、问题诊断、实施或测试等任务。
安装不会覆盖已有同名文件或冲突链接。

Skill installation does not require the Forge CLI or development dependencies.
See the [root README](../../README.md) for prerequisites and installation options.

## 2. 使用 CLI 路由与维护工具

如果需要 `forge` 命令，从仓库根目录安装 CLI：

```bash
python -m pip install -e ".forge-skill/forge[dev]"
forge version
forge ask "帮我 review 这个 spring service 的改动"
```

`[dev]` 同时安装测试依赖，适合源码开发。
未安装 CLI 时，可在 `.forge-skill/forge` 内使用
`python -m forge_cli version`，但仍需要相应 Python 依赖。

| 命令 | 用途 |
|---|---|
| `forge ask "..."` | 按宿主策略分派普通任务，或处理明确的学习服务 / Runtime 请求 |
| `forge route "..."` | 查看匹配评分和候选项 |
| `forge --format json recommend "..."` | 获取结构化路由推荐 |
| `forge list skills` | 查看注册的 Skills |
| `forge doctor` | 检查注册表、路径和引用 |
| `forge validate` | 完整的注册表确定性校验 |

普通任务的分派结果不代表宿主已执行任务。
CLI routing returns a decision; the external host performs the engineering work.

## 3. 项目接入与学习

Windows 项目接入还可从源码仓库根目录运行：

```bat
install-link-forge.bat "<target-project-path>" --tool codex
```

该工具检查 Python 版本并验证宿主目录中的 `forge`、`skills` 和
`forge-data` Junction。接入说明见 [BOOTSTRAP](BOOTSTRAP.md)。

学习采集默认关闭。配置允许采集的 Skill 后，可打开审核页面：

```bash
forge ask "启动学习审核页面"
forge ask "关闭学习审核服务"
```

学习流程、LLM 配置和人工审核要求见
[learning lifecycle](../skills/learning-collector/references/lifecycle.md)。

## 4. 开发验证

从仓库根目录执行：

```bash
python .forge-skill/forge/scripts/run-local-checks.py --full
```

验证通过说明当前确定性检查通过，不代表真实宿主与模型端到端验证已完成。

## 5. 进一步阅读

- [中文使用说明](docs/forge-user-guide.zh-CN.md) / [English user guide](docs/forge-user-guide.md)
- [模块组合与集成](GETTING-STARTED.md)
- [架构](ARCHITECTURE.md)
- [Skill 清单](../skills/README.md)
