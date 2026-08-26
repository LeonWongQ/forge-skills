# 模块化 AI 工程助手仓库说明（中文指南）

## 这是什么

这不是一个"把所有规则都写进一个大 Prompt"的仓库。

它是一套面向工程任务的 **模块化 AI 助手操作体系**。

它把 AI 在工程场景下需要的东西拆成多个层次：

- 全局原则
- 工作流阶段
- 行为模式
- 技术领域知识
- 输出模板
- 质量检查清单
- 报告模板
- 机器可读注册表
- 校验脚本
- 预组装任务包

因此，这个仓库更接近一个：

> 面向工程任务的 AI 操作系统（Prompt Operating Model）

而不是单一 Prompt 文件。

---

## 为什么要这样设计

传统做法通常会把下面这些内容全塞进一个文件：

- 角色设定
- 流程规则
- 技术知识
- 输出格式
- 质量要求

这样做的典型问题是：

- 一个场景能用，换个场景就要重写
- review / debug / refactor 很容易混在一起
- Java / Spring / Redis / Playwright 这些知识难以复用
- 输出结构不稳定
- 后期维护会越来越混乱

本仓库的设计目标，是把这些关注点拆开，让它们可以独立演进、组合使用。

---

## 核心分层

### 1. `CLAUDE.md`
全局原则层。

定义：
- 基本工作原则
- 证据优先
- 上下文优先
- 不确定性表达
- 作用域控制
- 默认执行顺序

它相当于整套系统的"宪法"。

---

### 2. `/engine`
工作流阶段层。

定义任务执行过程中的标准阶段：

- discover
- evidence
- context
- reasoning
- planning
- execution
- verification
- delivery
- transitions

它回答的是：

> 这类任务应该按什么阶段推进？

---

### 3. `/runtime`
运行时编排层。

定义：
- 如何路由任务
- 如何选择模块
- 运行时有哪些约束
- 多层规则冲突时怎么处理
- 全仓库模式下如何按需激活

主要文件：
- `router.md`
- `runtime-contract.md`
- `conflict-resolution.md`

它回答的是：

> 这些模块在真正执行任务时，怎么组合、怎么启动、怎么收束？

---

### 4. `/behaviors`
行为模式层。

定义任务模式，比如：

- review
- debug
- refactor
- optimize
- document
- explain

它回答的是：

> 做这件事时，应该以什么视角和优先级来思考？

例如：
- review 强调问题发现和风险排序
- debug 强调根因定位和假设验证
- refactor 强调结构改善和行为保持
- optimize 强调瓶颈、收益和代价

---

### 5. `/domains`
技术领域层。

定义领域知识和技术关注点，比如：

- java
- spring
- spring-ai
- mysql
- redis
- playwright
- testing

它回答的是：

> 做这件事时，需要懂哪些技术细节？需要注意哪些典型坑？

---

### 6. `/templates`
输出模板层。

定义最终输出长什么样，比如：

- default
- review-report
- debug-report
- refactor-plan
- implementation-plan
- explanation
- test-plan
- test-report

它回答的是：

> 最终结果应该怎么组织成用户可读、可执行的输出？

---

### 7. `/checklists`
质量门禁层。

定义交付前需要检查什么，比如：

- general-quality
- review-checklist
- debug-checklist
- refactor-checklist
- verification-checklist
- delivery-checklist

它回答的是：

> 输出前应该检查哪些关键质量项？

---

### 8. `/reports`
沉淀物层。

定义哪些结果值得沉淀为长期可复用的报告，例如：

- task-report
- incident-report
- review-summary

它回答的是：

> 哪些产物适合保存、交接、归档？

---

### 9. `/registry`
机器可读注册表层。

定义：
- 有哪些模块
- 有哪些 workflows
- 有哪些 compositions
- 有哪些 packs
- 哪些模板对应哪些输出 schema

它是后续工具化、脚本化、CI 校验的基础。

---

### 10. `/packs`
任务包层。

这是高频任务的预组装组合包，例如：

- Spring review
- Playwright flaky debug
- Redis stale-read incident
- Java refactor

它的作用是：

> 把常见任务的模块组合提前打包，减少重复手工装配。

---

### 11. `/scripts`
验证与维护工具层。

目前用于：
- 校验 registry schema
- 检查模块路径
- 检查交叉引用
- 检查 pack 合法性

这是仓库长期保持一致性的关键。

---

## 这套系统最适合什么场景

这套体系特别适合下面几类任务：

### 1. Java / Spring 工程分析
例如：
- 代码 review
- bug 分析
- 事务问题分析
- 缓存一致性分析
- 重构方案设计
- 优化建议

### 2. 测试相关工作
例如：
- 测试代码评审
- flaky test 诊断
- 测试计划
- 测试报告
- 页面测试计划
- 页面测试结果输出

### 3. 结构化交付任务
例如：
- review report
- debug report
- refactor plan
- implementation plan
- incident summary
- release validation summary

---

## 不太适合"全套开满"的场景

虽然仓库很完整，但并不意味着所有任务都应该全量激活。

以下场景不适合全套重模式：

- 只查一个小语法问题
- 只看一小段代码会不会 NPE
- 临时问一个简单命令
- 非工程化、非结构化的小问题

这类任务更适合：
- 最小激活模式
- 或干脆只用 `CLAUDE.md` + 一个 behavior/domain

---

## 两种主要使用方式

---

### 方式一：最小模式（推荐日常轻任务）
适用于：
- 快速判断
- 小 review
- 小解释
- 小测试问题

最小组合一般是：

- `CLAUDE.md`
- 1 个 behavior
- 1 个 domain
- `templates/default.md`
- `checklists/general-quality.md`

例如：
- Java 方法 correctness quick review
- Spring transaction quick explanation
- test assertion sanity check

---

### 方式二：全仓库模式（推荐复杂任务）
适用于：
- Claude Code
- 复杂工程分析
- 需要统一工作方式的团队场景
- 高频 pack 场景

但**注意**：

> 全仓库可见 ≠ 全仓库同时激活

全仓库模式正确用法是：

- 仓库全部存在于项目中
- 使用 `CLAUDE.md + AUTOLOAD.md` 作为全局入口
- 再由任务触发按需激活 behavior / domains / workflows / templates / checklists / packs

这是最推荐的方式。

---

## `AUTOLOAD.md` 是干什么的

`AUTOLOAD.md` 是全局自动按需加载策略文件。

它的作用不是替代 `CLAUDE.md`，而是补上：

> 在全仓库可见时，如何避免所有模块同时成为活动规则？

它定义了：

- full repo available, partial repo active
- pack-first
- minimal-first
- expand-on-demand
- task-scoped activation

简单理解：

- `CLAUDE.md` = 总原则
- `AUTOLOAD.md` = 全局启动与按需激活策略

---

## 推荐的全仓库启动方式

如果你在 Claude Code 中使用，推荐把以下文件当作全局起点：

- `CLAUDE.md`
- `AUTOLOAD.md`

在此基础上，再由任务决定是否激活：

- `runtime/router.md`
- 具体 behavior
- 具体 domains
- 具体 template
- 具体 checklists
- 具体 pack

这样既能让整个仓库都"可见"，又不会因为全部激活而拖慢效率。

---

## 为什么不建议把所有 md 永远当作活动上下文

因为这样会带来几个问题：

- 小任务被大流程拖慢
- 输出过度结构化
- router / domain / template 信号互相干扰
- 模型会更容易"样样都想顾到"，导致不够直接
- 你这套模块化系统会退化回"大 Prompt"

所以这套仓库真正的高效姿势是：

> 全量存在，按需激活，而不是全量常驻激活。

---

## Pack 怎么理解

Pack 可以理解为：

- 任务包
- 场景包
- 预组装组合包

它不是"压缩包"，而是：

> 针对某类高频任务，提前定义好的标准模块组合清单

比如：
- Spring service review pack
- Playwright flaky debug pack
- Redis incident pack
- Java refactor pack

它的作用是减少高频场景下的重复装配成本。

---

## 当前这个仓库已经完成到什么程度

当前可以认为是：

# `v1.0.0 — Architecture Complete`

这意味着：

### 已完成
- 核心分层设计
- runtime 编排层
- behavior / domain 体系
- template / checklist / report 体系
- registry / schemas
- validation scripts
- CI metadata validation
- packs
- 测试计划与测试报告模板
- README / GETTING-STARTED / EXAMPLES / integrations
- AUTOLOAD 使用策略

### 还没做但未来可做
- registry 自动生成
- CLI
- pack loader
- output validator runtime
- full runtime implementation
- UI 工具
- 更强的语义级校验

所以这个仓库现在不是"半成品"，而是：

> 架构完整、可用、可维护、可扩展，但工具层仍可继续长。

---

## 如果后面还要继续做，建议只做工具，不要继续无限扩文档

这是我最重要的建议之一。

当前文档体系已经足够完整。  
后续如果继续投入，优先顺序应该是：

### 建议继续做
- validate-all 统一命令
- registry generator
- pack loader
- context builder
- output validator
- 简单 CLI

### 暂时不要优先做
- 再加很多新层
- 再加大量新 README
- 再加很多相似 report/template
- 做复杂 UI 平台
- 做多 agent orchestration 平台

现在最健康的方向是：

> 少改架构，多做工具。

---

## 推荐的冻结边界

建议暂时把下面这些目录视为"主干冻结区"，尽量少再动结构：

- `CLAUDE.md`
- `/engine`
- `/runtime`
- `/behaviors`
- `/domains`
- `/templates`
- `/checklists`
- `/reports`

可以继续扩展，但不要轻易再改层级边界。

而更适合继续演进的是：

- `/scripts`
- `/registry`
- `/packs`
- integrations / tooling

---

## 最后一句话总结

这套仓库现在已经不是"Prompt 文件集合"，而是一套：

> 面向工程开发、代码分析、测试设计、测试报告与 AI 集成的模块化操作体系

最推荐的实际用法是：

- 轻任务：最小模式
- 重任务：全仓库模式 + `AUTOLOAD.md`
- 高频任务：优先 pack
- 后续演进：优先工具化，少改主架构
