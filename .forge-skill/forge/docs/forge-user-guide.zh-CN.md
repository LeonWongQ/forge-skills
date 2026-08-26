# Forge 使用说明书

Forge 是一个帮你自动判断"这个任务该怎么处理"的工具。

你不用记什么场景用什么技能、配什么模板、加什么检查项——把需求丢给它，它会告诉你该走哪条路。

---

## 一、一分钟上手

装好之后，你只需要记住一个命令：

```bash
forge ask "你的需求"
```

比如：

```bash
forge ask "帮我 review 一个 spring service 改动"
forge ask "帮我分析一个线上 redis 旧数据事故"
forge ask "帮我补一组单元测试"
forge ask "先帮我摸清楚这个模块现状"
```

它会告诉你：

```
Suggested handling:
- Skill: skill.code_review
- Pack: pack.spring_review
- Behavior: behavior.review
- Workflow: workflow.light_review
- Template: template.review_report
- Domains: domain.java, domain.spring, ...
- Checklists: checklist.general_quality, checklist.review, ...

Why:
- strategy: skill+pack-v6
- confidence: high
- evidence: pack_keyword_any = review
- evidence: pack_keyword_group = spring
```

看到这里你就知道了——这个任务应该用 **code review** 模式，搭配 **spring review** 专项包，输出成 **review report** 格式，检查项包括通用质量 + review 专项 + 验证 + 交付。

---

## 二、三个命令的区别

| 命令 | 什么时候用 | 适合谁 |
|------|-----------|--------|
| `forge ask` | 日常使用，丢一句话得到推荐 | 所有人 |
| `forge route` | 想看路由细节，包括分数、候选列表 | 调试 / 开发 forge 本身 |
| `forge recommend` | 需要结构化输出，给程序读 | 集成到工具链 |

三者内部逻辑完全一样，只是输出风格不同。

### `forge ask` — 日常首选

```bash
forge ask "帮我设计测试方案"
forge ask "这个 SQL 查询太慢了，帮我优化"
forge ask "解释一下 spring 事务传播机制"
```

输出像聊天一样，直接告诉你该用什么、为什么。

### `forge route` — 想看细节的时候

```bash
forge route "帮我设计测试方案"
```

输出会多出：
- 分数拆解（trigger 分 + keyword 加分）
- 所有候选技能排名
- 匹配到了哪些 trigger

### `forge recommend` — 给程序读

```bash
forge recommend "帮我设计测试方案"
forge --format json recommend "帮我设计测试方案"
```

输出是结构化的推荐结果，JSON 模式方便程序解析。

---

## 三、所有命令一览

### 日常使用

```bash
# 最常用：丢一句话，得到推荐
forge ask "帮你做 XXX"

# 看路由细节
forge route "帮你做 XXX"

# 结构化推荐
forge recommend "帮你做 XXX"
```

### 高级使用

```bash
# 手动拼装：指定 skill + pack + template
forge compose --skill explore --pack general_exploration

# 手动拼装：覆盖某个模块
forge compose --skill plan --template implementation_plan --domain java --domain spring
```

### 检查与维护

```bash
# 全面体检
forge validate

# 快速检查（只看文件路径是否都存在）
forge validate --quick

# 健康摘要
forge doctor

# 导出检查报告
forge validate --report out/check-report.json
forge doctor --report out/doctor-report.json

# 查看版本
forge version

# 查看概况
forge status
```

### 查询与浏览

```bash
# 列出所有技能
forge list skills

# 列出所有专项包
forge list packs

# 列出所有模板
forge list templates

# 列出所有领域
forge list domains

# 查看某个项目的详细信息
forge show skill explore
forge show pack spring_review
forge show template default
```

---

## 四、它支持哪些任务类型

| 你说的话 | 它识别为 | 配的专项包 |
|---------|---------|-----------|
| 帮我 review spring service 改动 | code_review | spring_review |
| playwright CI 上 flaky，帮我定位 | debug | playwright_debug |
| 线上 redis 旧数据事故 | incident | redis_incident |
| 帮我设计测试方案 | test_design | general_test_plan |
| 帮我补一组单元测试 | test_implementation | — |
| spring boot 升级迁移方案 | migration | — |
| 整理测试报告和发布建议 | report | general_test_report |
| 先帮我摸清楚模块现状 | explore | general_exploration |
| 帮我重构 java service | refactor | java_refactor |
| 解释 spring 事务传播机制 | explain | — |
| 帮这个类生成文档 | document | — |
| SQL 查询太慢帮我优化 | optimize | — |
| 分析这段报错日志 | error_analysis | — |
| 怎么实现这个导出功能 | plan | — |
| 实现 Vue 2 组件或 VMD UI 功能 | vue2 | — |
| 实现 Vue 2.7 组件或经验证的 Vue 2.7/Vite 改动 | vue2_7 | — |
| 实现 Vue 3 组件或 Vue 3/Vite 配置 | vite_vue3 | — |
| 未明确版本的 Vue/Vite 请求 | 先确认目标 package 的 Vue 版本 | — |

**支持的技能（27 个）**：code_review、debug、plan、error_analysis、report、explain、refactor、optimize、document、test_design、incident、test_implementation、migration、explore、page_test、test_strategy、implement、architecture_design、security_review、data_design、dependency_audit、release_readiness、contract_compatibility、auto_compact、vite_vue3、vue2、vue2_7

**支持的专项包（9 个）**：spring_review、playwright_debug、redis_incident、java_refactor、general_test_report、general_test_plan、general_exploration、spring_ai_review、release_readiness

---

## 五、常见使用场景

### 场景 1：不知道从哪下手

```bash
forge ask "帮我梳理一下这个模块现状"
```

→ 自动路由到 explore + general_exploration 包，帮你摸清情况再决定下一步。

### 场景 2：Review 代码

```bash
forge ask "帮我 review 这个 PR 的改动"
forge ask "帮我 review 一个 spring service 改动"
```

→ 前者走 code_review，后者还会自动匹配 spring_review 专项包。

### 场景 3：排查问题

```bash
forge ask "这个 playwright 用例在 CI 上 flaky，帮我定位下"
forge ask "帮我分析这段报错日志"
forge ask "生产环境服务异常，帮我做事故分析"
```

→ 分别路由到 debug + playwright_debug、error_analysis、incident。

### 场景 4：测试相关

```bash
forge ask "帮我设计测试方案"
forge ask "帮我补一组单元测试"
forge ask "整理测试报告和发布建议"
```

→ 分别路由到 test_design、test_implementation、report。

### 场景 5：规划和迁移

```bash
forge ask "怎么实现这个导出功能"
forge ask "给我一个 spring boot 升级迁移方案"
forge ask "帮我重构这个 java service"
```

→ 分别路由到 plan、migration、refactor。

---

## 六、输出格式

### 文本模式（默认）

所有命令默认输出人类可读的文本。

### JSON 模式

任意命令加 `--format json`：

```bash
forge --format json ask "帮我设计测试方案"
forge --format json route "帮我设计测试方案"
forge --format json recommend "帮我设计测试方案"
forge --format json validate
```

---

## 七、常见问题

### Q: 路由结果不对怎么办？

用 `forge route` 看候选列表，了解为什么别的技能得分更高。然后可以根据需要调整：
- 改 registry 文件（加 trigger、调权重）
- 加回归用例到 `route-regression.json`

### Q: 怎么确认 forge 本身没坏？

```bash
forge validate
```

8 项检查全部通过，说明注册表、路径、引用、Pack、语义和已声明的契约 fixture 均通过当前的确定性校验。完整本地门禁还会运行路由回归和 pytest。

### Q: `ask` 和 `recommend` 有什么区别？

内部逻辑完全一样。`ask` 输出像聊天，适合人看。`recommend` 输出更结构化，适合程序读。选你喜欢的用。

### Q: 能不能只装一部分？

可以。forge 是模块化的，你不用的 pack / domain / template 不影响核心功能。但现在没有提供"按需安装"的自动机制——你直接不引用就行了。

---

## 八、快速参考

```bash
# 一句话入口
forge ask "..."

# 查看路由细节
forge route "..."

# 结构化推荐
forge recommend "..."

# 手动拼装
forge compose --skill <skill> --pack <pack>

# 全面体检
forge validate

# 快速体检
forge validate --quick

# 健康摘要
forge doctor

# 导出报告
forge validate --report out/report.json

# 列清单
forge list skills
forge list packs
forge list templates
forge list domains

# 查详情
forge show skill <name>
forge show pack <name>

# 看版本
forge version

# 看概况
forge status
```
