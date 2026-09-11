# ⚡ Forge 5 分钟快速入门 / 5-Minute Quickstart

## 1. 这是什么？(30 秒)

Forge 是一个帮你自动判断「这个工程任务该用什么模式处理」的 AI 工具箱。

你不是 AI 专家也能用它做专业的事：
- 代码 Review、Bug 诊断、事故分析
- 测试方案设计、重构计划、迁移评估
- 架构设计、安全审查、依赖审计
- ...只需要用自然语言描述你的需求

Forge is a CLI tool that automatically routes your engineering task to the right skill, pack, template, and quality gates — using natural language.

---

## 2. 三步开始 (2 分钟)

### Step 1: 检查环境

```bash
cd .forge-skill/forge
python -m pip install -e ".[dev]"
forge version
```

源码开发时，可在 `.forge-skill/forge` 内改用 `python -m forge_cli version`。`../skills/forge/forge.py` 仅保留为兼容 shim。

你应该看到：
```
forge 1.2.1
```

### Step 2: 第一次路由

```bash
forge ask "帮我 review 这个 spring service 的改动"
```

### Step 3: 看懂输出

```
Suggested handling:
  Skill:  skill.code_review     ← 任务类型：代码审查
  Pack:   pack.spring_review    ← 专项增强：Spring 专项
  Template: template.review_report ← 输出格式：审查报告
  Domains: domain.java, domain.spring, domain.testing ← 需要的技术知识
  Confidence: high              ← 匹配置信度

Why:
  strategy: skill+pack-v6
  evidence: pack_keyword_any = review
  evidence: pack_keyword_group = spring
```

看到这里你就知道：这个任务应该用 **code review** 模式，搭配 **Spring review** 专项包，输出 **review report** 格式。

---

## 3. 验收已部署的项目

当 Forge 通过 `install-link-forge.bat` 部署到消费者项目后，安装脚本会先检查 Python 3.11+；不满足时不会创建项目目录或 junction。满足后，脚本会同时创建并验证 `forge`、`skills` 和 `forge-data` Junction。该检查直接使用源码，不需要 `pip install`、开发依赖、全局 `forge` 命令或手工配置 PATH。

若需要清理未注册的历史 Runtime 数据，先执行 `forge runtime-list-orphans` 查看项目 ID；只有明确确认后，才使用 `forge runtime-clean-orphan --project-id <id> --yes` 物理删除单个孤儿目录。系统不会自动删除这些数据。

---

## 4. 常用命令 (1 分钟)

| 命令 | 用途 | When to use |
|------|------|-------------|
| `forge ask "..."` | 一键路由（推荐日常使用）| Daily driver |
| `forge route "..."` | 查看路由细节和评分 | Debug routing |
| `forge recommend "..."` | 结构化推荐（CI/编程用）| Programmatic use |
| `forge list skills` | 列出所有支持的任务类型 | Discover skills |
| `forge list packs` | 列出所有预组装专项包 | Discover packs |
| `forge show skill <name>` | 查看某个 skill 详情 | Inspect config |
| `forge validate --quick` | 快速健康检查 | Quick health check |
| `forge doctor` | 运行核心健康检查 | Pre-commit check |

---

## 4. 支持哪些任务？(30 秒)

| 我想... | 这样说 |
|---------|--------|
| 代码审查 | `forge ask "帮我 review 这个改动"` |
| 排查 Bug | `forge ask "这个测试为什么偶发失败"` |
| 设计测试 | `forge ask "帮我设计测试方案"` |
| 补写测试 | `forge ask "帮我补一组单元测试"` |
| 重构代码 | `forge ask "帮我重构这个类"` |
| 性能优化 | `forge ask "这个 SQL 太慢了"` |
| 事故分析 | `forge ask "线上 Redis 出现了脏数据"` |
| 架构设计 | `forge ask "帮我设计这个系统的架构"` |
| 安全审查 | `forge ask "帮我审查这段代码的安全性"` |
| 数据库设计 | `forge ask "帮我设计用户表的索引"` |
| 依赖审计 | `forge ask "检查项目的依赖安全"` |
| 迁移升级 | `forge ask "Spring Boot 3.x 升级方案"` |
| 先摸清现状 | `forge ask "先帮我摸清楚这个模块的现状"` |
| 解释概念 | `forge ask "解释 Spring 事务传播机制"` |
| ...更多 | `forge list skills` |

---

## 5. 下一步 (30 秒)

| 我想... | 阅读 |
|---------|------|
| 了解完整 CLI 功能 | `docs/forge-user-guide.zh-CN.md` |
| 看 10 个真实场景案例 | `EXAMPLES.md` |
| 理解架构设计原理 | `ARCHITECTURE.md`（含 Mermaid 架构图）|
| 把 Forge 部署到自己的项目 | 运行 `link-forge.bat <target-dir>` |
| 运行单元测试 | `cd .forge-skill/forge && pip install -e ".[dev]" && pytest` |

---

## 常见问题 / FAQ

**Q: 路由不准确怎么办？**
A: 用 `forge route "..."` 查看评分细节和候选列表，调整描述中的关键词重试。也可以编辑 `registry/skill-routing.json` 添加自定义触发词。

**Q: 和直接用 Claude Code 有什么区别？**
A: Forge 是 Claude Code 的增强层。它自动帮你选择正确的 behavior、domain、template、checklist 组合，避免你手动记住 27 个 skill 和 9 个 pack 的配置。

**Q: 能自定义吗？**
A: 可以。所有路由规则、触发词、领域知识都可以通过编辑 `registry/` 下的 JSON 文件来定制，修改后用 `forge validate` 校验即可。
