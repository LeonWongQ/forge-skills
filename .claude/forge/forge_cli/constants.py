# -*- coding: utf-8 -*-
"""Forge CLI — constants, exit codes, schema mappings, keyword sets."""

# ============================================================
# Exit Codes
# ============================================================

EXIT_OK = 0
EXIT_GENERAL_ERROR = 1
EXIT_VALIDATION_FAILED = 2
EXIT_REGISTRY_ERROR = 3
EXIT_PATH_ERROR = 4
EXIT_REFERENCE_ERROR = 5
EXIT_USAGE_ERROR = 6

# ============================================================
# Check Names
# ============================================================

CHECK_REGISTRY = "registry"
CHECK_PATHS = "paths"
CHECK_REFS = "refs"
CHECK_PACKS = "packs"
CHECK_PACK_REFS = "pack-refs"
CHECK_SEMANTICS = "semantics"
CHECK_CONTRACTS = "contracts"
CHECK_DERIVED_REGISTRY = "derived-registry"

ALL_CHECKS = [
    CHECK_REGISTRY,
    CHECK_PATHS,
    CHECK_REFS,
    CHECK_PACKS,
    CHECK_PACK_REFS,
    CHECK_SEMANTICS,
    CHECK_CONTRACTS,
    CHECK_DERIVED_REGISTRY,
]

# ============================================================
# Schema Mappings
# ============================================================

REGISTRY_SCHEMA_CANDIDATES = {
    "modules.json": ["modules.schema.json"],
    "skills.json": ["skills.schema.json"],
    "workflows.json": ["workflows.schema.json"],
    "compositions.json": ["compositions.schema.json"],
    "skill-routing.json": ["skill-routing.schema.json"],
    "behaviors.json": ["behaviors.schema.json"],
    "domains.json": ["domains.schema.json"],
    "templates.json": ["templates.schema.json"],
    "checklists.json": ["checklists.schema.json"],
    "reports.json": ["reports.schema.json"],
    "project.json": ["project.schema.json"],
    "packs.json": ["packs-index.schema.json"],
    "route-regression.json": ["route-regression.schema.json"],
    "template-outputs.json": ["template-outputs.schema.json"],
    "contracts.json": ["contracts.schema.json"],
}

REGISTRY_WITHOUT_SCHEMA = set()

NON_REGISTRY_SCHEMAS = {
    "runtime-state.schema.json",
    "resolved-context.schema.json",
    "template-default-output.schema.json",
    "template-debug-report-output.schema.json",
    "template-explanation-output.schema.json",
    "template-implementation-plan-output.schema.json",
    "template-refactor-plan-output.schema.json",
    "template-review-report-output.schema.json",
    "template-test-plan-output.schema.json",
    "template-test-report-output.schema.json",
    "template-exploration-output.schema.json",
}

# ============================================================
# Keyword Sets
# ============================================================

GENERIC_PLAN_TRIGGERS = {
    "plan",
    "方案",          # Chinese: "plan / proposal"
    "计划",          # Chinese: "plan / schedule"
    "设计一下",       # Chinese: "let me design it"
    "怎么做",        # Chinese: "how to do it"
    "implementation plan",
}

TEST_DESIGN_KEYWORDS = {
    "测试",           # Chinese: "test"
    "test", "test case", "testcase",
    "用例",           # Chinese: "use case"
    "测试用例",       # Chinese: "test case"
    "测试设计",       # Chinese: "test design"
    "测试方案",       # Chinese: "test plan"
    "测试策略",       # Chinese: "test strategy"
    "测试计划",       # Chinese: "test plan / schedule"
    "怎么测",         # Chinese: "how to test"
    "如何测试",       # Chinese: "how to test"
    "覆盖",           # Chinese: "coverage"
    "覆盖率",         # Chinese: "coverage rate"
    "场景",           # Chinese: "scenario"
    "回归",           # Chinese: "regression"
    "验证",           # Chinese: "verify / validation"
    "边界",           # Chinese: "boundary / edge"
    "异常场景",       # Chinese: "exception scenario"
    "测试点",         # Chinese: "test point"
    "接口测试",       # Chinese: "API test"
    "单元测试",       # Chinese: "unit test"
    "集成测试",       # Chinese: "integration test"
    "e2e", "playwright",
}

TEST_IMPLEMENTATION_KEYWORDS = {
    "write tests", "add tests", "implement tests", "unit test", "integration test",
    "mock", "stub", "fixture", "test implementation",
    "补测试",           # Chinese: "add tests"
    "写测试",           # Chinese: "write tests"
    "补单测",           # Chinese: "add unit tests"
    "补集成测试",       # Chinese: "add integration tests"
    "加测试用例",       # Chinese: "add test cases"
    "实现测试",         # Chinese: "implement tests"
    "补回归测试",       # Chinese: "add regression tests"
    "测试实现",         # Chinese: "test implementation"
    "测试代码",         # Chinese: "test code"
    "桩",              # Chinese: "stub"
    "夹具",            # Chinese: "fixture"
}

PLAN_KEYWORDS = {
    "实现",           # Chinese: "implement"
    "改造",           # Chinese: "refactor / transform"
    "落地",           # Chinese: "roll out / land"
    "分阶段",         # Chinese: "phased / step-by-step"
    "implementation", "rollout",
}

MIGRATION_KEYWORDS = {
    "migration", "upgrade", "compatibility", "rollout", "rollback", "framework migration",
    "版本升级",         # Chinese: "version upgrade"
    "迁移",             # Chinese: "migration"
    "升级",             # Chinese: "upgrade"
    "兼容性",           # Chinese: "compatibility"
    "平滑迁移",         # Chinese: "smooth migration"
    "回滚",             # Chinese: "rollback"
    "回滚方案",         # Chinese: "rollback plan"
    "升级方案",         # Chinese: "upgrade plan"
    "迁移方案",         # Chinese: "migration plan"
    "升级计划",         # Chinese: "upgrade schedule"
    "兼容性评估",       # Chinese: "compatibility assessment"
}

REFACTOR_KEYWORDS = {
    "refactor",
    "重构",             # Chinese: "refactor"
    "整理代码",         # Chinese: "clean up code"
    "结构优化",         # Chinese: "structure optimization"
    "restructure",
}

INCIDENT_KEYWORDS = {
    "incident", "outage", "production", "postmortem", "sev1", "sev2",
    "service degradation", "availability", "degradation",
    "线上",             # Chinese: "online / production"
    "生产",             # Chinese: "production"
    "故障",             # Chinese: "failure / fault"
    "事故",             # Chinese: "incident / accident"
    "告警",             # Chinese: "alert / warning"
    "降级",             # Chinese: "degradation"
    "恢复",             # Chinese: "recovery"
    "可用性",           # Chinese: "availability"
    "服务异常",         # Chinese: "service abnormality"
    "事故复盘",         # Chinese: "incident review / postmortem"
    "生产问题",         # Chinese: "production issue"
    "线上故障",         # Chinese: "online failure"
    "线上异常",         # Chinese: "online abnormality"
}

ERROR_ANALYSIS_KEYWORDS = {
    "stack trace", "traceback",
    "异常栈",           # Chinese: "exception stack"
    "堆栈",             # Chinese: "stack trace"
    "报错日志",         # Chinese: "error log"
    "日志分析",         # Chinese: "log analysis"
    "错误分析",         # Chinese: "error analysis"
}

DEBUG_KEYWORDS = {
    "debug",
    "排查",             # Chinese: "investigate / trace"
    "定位",             # Chinese: "locate / pinpoint"
    "root cause", "why failing",
    "问题定位",         # Chinese: "problem pinpointing"
    "诊断",             # Chinese: "diagnose"
}

PACK_CROSS_SKILL_ALLOWED = {
    "pack.general_test_report",
    "pack.general_test_plan",
    "pack.playwright_debug",
}
