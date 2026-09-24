(() => {
  "use strict";

  const STORAGE_KEY = "forge-learning-language-v2";
  const SUPPORTED = new Set(["zh-CN", "en"]);
  const messages = {
    "zh-CN": {
      language: "语言", chinese: "中文", english: "English",
      allProjects: "全部项目", allSkills: "全部 Skill", allStatuses: "全部状态",
      refreshData: "刷新数据", refreshVersions: "刷新汇总", versions: "汇总管理",
      active: "有效", excluded: "已排除", deleted: "已删除", reviewed: "已审核",
      draft: "草稿", confirmed: "已确认", pending: "待审核", archived: "已归档",
      unavailable: "不可用", conflict: "身份冲突", disabled: "已停用", published: "已发布",
      previous: "上一页", next: "下一页", page: "第 {current} / {total} 页",
      records: "采集记录", summaries: "Skill 学习汇总", projectOverlay: "项目 Overlay",
      selectScope: "请选择项目和 Skill", noScope: "未选择范围",
      loadingFailed: "加载失败", operationFailed: "操作失败",
      preCheck: "执行前检查", finalValidation: "输出前校验",
      statusPending: "待审核", statusConfirmed: "确认采用", statusExcluded: "排除",
      reviewHomeTitle: "学习数据审核",
      reviewHomeEyebrow: "Forge · 本地学习工作区",
      reviewHomeSubtitle: "按项目隔离采集结果，人工审核后生成可启用的 Skill 汇总版本。",
      currentScope: "当前范围：", filterRecords: "筛选采集记录", perPage: "每页 20 条",
      searchPlaceholder: "搜索输出、备注或运行 ID", applyFilters: "应用筛选",
      archiveProject: "归档项目", restoreProject: "恢复项目",
      summaryNote: "仅使用当前项目与 Skill 下的有效审核数据生成新版本。生成后仍需人工启用。",
      generateVersion: "生成新版本", editedContent: "修订内容", reviewNote: "审核备注",
      classicCase: "标记为经典案例", classicReason: "经典案例理由",
      keep: "保留", exclude: "排除", delete: "删除",
      currentResults: "当前结果", pageActive: "本页有效", pageExcluded: "本页排除", pageDeleted: "本页删除",
      noRecords: "没有符合条件的记录", recordCount: "{count} 条",
      reviewedTag: "已审核", projectsUnavailable: "{count} 个项目不可用或存在身份冲突",
      archivedProjectsSuffix: "，另有 {count} 个已归档项目", archivedProjects: "{count} 个项目已归档，不参与全部项目扫描。",
      archiveConfirm: "归档项目“{name}”？数据不会删除，但默认的全部项目视图将不再扫描它。",
      projectUpdateFailed: "更新项目状态失败", projectArchived: "项目已归档，数据仍保留。",
      projectRestored: "项目已恢复。", projectStillUnavailable: "项目仍不可用：{reason}",
      checkProjectPath: "请检查项目路径与数据库", chooseScopeFirst: "请先选择项目和 Skill",
      summarizeFailed: "汇总失败", versionGenerated: "已生成 v{version}，可作为项目 Overlay 的来源",
      overlayAutoDisabled: "Overlay v{version} 已自动停用：{reviewed} 条已审核记录中 {negative} 条被排除（{rate}%）",
      chooseScope: "请选择项目和 Skill", summariesLoadFailed: "无法加载汇总版本",
      effectiveRecords: "{count} 条有效记录", summarySourceNote: "汇总仅作为项目 Overlay 的生成来源，不直接参与 Skill 运行。",
      viewSummarySnapshot: "查看汇总快照", noSummary: "当前 Skill 尚无汇总版本",
      recordsLoadFailed: "无法加载采集记录",
      hookConfiguration: "采集 Hook", hookConfigurationNote: "三个宿主的 Forge Hook 可同时启用。开启只安装或修复对应宿主；关闭会在确认后仅卸载该宿主，各项目仍通过 Skill 开关独立决定是否采集。",
      codexTrustHint: "信任提示", codexTrustSummary: "如尚未信任 Codex Hook，请在 Codex Desktop 中确认",
      codexTrustSteps: "应用 Codex Hook 后，打开 Codex Desktop → Settings → Hooks，找到用户 Hook，检查命令并点击 Trust / 信任，然后新建 Codex 会话以重新加载 Hook 配置。",
      codexTrustNote: "“已安装”只表示配置已写入，不代表 Codex 已信任。修改 Hook 后需重新信任；如果没有信任入口，请检查默认用户配置文件：",
      codexTrustCustomHome: "如设置了 CODEX_HOME，请检查该目录下的 hooks.json。",
      globalSetting: "本机用户设置",
      codexHost: "Codex", claudeCodeHost: "Claude Code", cursorHost: "Cursor",
      hookHostsActive: "已启用宿主：{hosts}", hookNoneActive: "当前未启用采集 Hook", globalHookReady: "本机用户 Hook 已安装",
      globalHookMissing: "本机用户 Hook 未安装", globalHookDrifted: "Hook 配置已被修改",
      globalHookInvalid: "宿主配置文件无效", hookRepairRequired: "Hook 需要修复",
      hookNeverObserved: "尚未观察到事件", hookHealthy: "最近事件正常",
      hookStale: "最近事件已过期", hookRuntimeError: "最近事件失败",
      hookInvoked: "Hook 脚本已调用", hookSkipped: "Hook 已触发，未采集", hookCaptured: "Hook 已采集",
      hookHandled: "Hook 已处理事件", hookNoInvocation: "尚未观察到 Hook 调用",
      hookHistorical: "仅有历史回执", enabledUnverified: "启用状态未验证", trustUnverified: "信任状态未验证", trustManual: "信任需在 Codex Desktop 手动确认",
      latestRecordEvidence: "当前列表最新记录", sourceSkill: "Skill 采集", sourceHook: "Hook 采集",
      sourceRuntime: "Runtime 采集", hookPending: "Hook 待触发", hookMissed: "Hook 未采集",
      hookNotExpected: "未要求 Hook", hookCapturedAt: "Hook 采集时间：{time}",
      hookInvocationId: "调用 ID：{id}", hookHostEvidence: "Hook 宿主：{host}", hookReceiptMatched: "最新 Hook 回执与该调用一致",
      hookQualityEvidence: "采集画像：{format} · {attribution} · {characters} 字符", hookMatchedSkills: "匹配 Skill：{skills}",
      hookOnlyAuxiliary: "Hook-only 辅助证据", sharedReviewGroup: "共享审核 · {count} 个 Skill",
      sharedCapturePending: "共享采集正在完成，暂不可审核",
      sharedReviewApplied: "已审核一次并同步应用到 {count} 个 Skill 记录",
      hookConfigured: "已启用或修复 {host} 的采集 Hook", hookRemoved: "已卸载 {host} 的采集 Hook",
      hookUpdateFailed: "Hook 配置失败", hookStatusFailed: "Hook 状态加载失败",
      hookPartialWarning: "Hook 已部分更新，请处理残留配置：{detail}",
      hookLastEvent: "最近 Hook 回执：{outcome} · {time}", hostRenderedOutput: "宿主最终输出",
      removeHookConfirm: "卸载 {host} 的本机用户采集 Hook？其他宿主 Hook 和 Skill 约束采集不会受影响。",
      versionsTitle: "Skill 汇总管理", versionsEyebrow: "Forge · 训练汇总",
      versionsSubtitle: "逐条审核精炼规则；所有规则处理完成后，版本才能进入 Overlay。",
      backToReview: "返回审核页", llmConfig: "LLM 精炼与评测配置",
      llmConfigNote: "仅在点击“LLM 精炼”或“自动评测并发布”时调用。",
      baseUrlPlaceholder: "API 基础地址，例如 https://example.com/v1",
      modelPlaceholder: "模型名称", keyEnvPlaceholder: "API Key 环境变量名",
      enableLlm: "启用 LLM 精炼与评测", enableLlmTitle: "启用或停用 LLM 精炼与评测",
      saveConfig: "保存配置", eligibleRecords: "合格记录", originalFindings: "原始问题",
      candidateThemes: "候选主题", candidateRules: "候选规则", compressedThemes: "已压缩主题",
      evidenceCount: "{count} 条证据", truncatedSources: "（仅展示前 20 条，完整关系已入库）",
      rationale: "依据：", reviewRules: "审核 {count} 条精炼规则", legacySnapshot: "查看旧版完整快照",
      lockedSummary: "历史汇总不可编辑或删除", saveReview: "保存审核", refineLlm: "LLM 精炼",
      overlaySourceHint: "可作为项目 Overlay 的来源", sourceRecords: "{count} 条来源记录",
      summaryWindow: "窗口 {months} 个月，经典 {classic} 条", noVersions: "暂无汇总版本",
      versionCount: "{count} 个汇总版本", refineConfirm: "确认调用已配置的 LLM，并使用当前页面语言生成新的精炼版本？原版本不会修改。",
      refineFailed: "LLM 精炼失败", llmReady: "LLM 配置已就绪", llmUnavailable: "LLM 未配置或未启用",
      saveReviewFailed: "审核保存失败", deleteVersionConfirm: "确认物理删除此汇总版本？删除后无法恢复。",
      deleteFailed: "删除失败", llmConfigSaveFailed: "LLM 配置保存失败",
      llmSavedNeedsEnv: "LLM 配置已保存；请设置对应的用户级环境变量",
      createOverlay: "生成 Overlay 草稿", select: "选择", manageOverlayScope: "请选择项目和 Skill 后管理 Overlay",
      overlayLoadFailed: "Overlay 加载失败", summarySources: "{count} 个 Summary 来源",
      review: "审核", evaluatePublish: "自动评测并发布", reevaluatePublish: "重新评测并发布",
      activate: "启用", disable: "停用", overlayDelete: "删除", noOverlay: "暂无 Overlay",
      evaluationFailed: "评测失败：{error}", evaluationSummary: "LLM 评测 {count} 个固定案例 · 置信度 {confidence} · {gates}",
      gatePassed: "通过", gateFailed: "失败", evaluationReady: "评测案例已就绪 {count}/{required} · {categories}",
      evaluationInsufficient: "评测案例不足 {count}/{required}", evaluateTitle: "使用固定案例自动评测并发布",
      activateConfirm: "确认启用此 Overlay？同一项目和 Skill 的其他 ACTIVE Overlay 将停用。",
      disableConfirm: "确认停用此 Overlay？", deleteOverlayConfirm: "确认物理删除此 Overlay？删除后无法恢复。",
      overlayOperationFailed: "Overlay 操作失败", chooseReviewedSummaries: "请选择同一项目和 Skill 下的已审核 Summary",
      chooseOneSummary: "请至少选择一个已审核 Summary", replaceOverlayConfirm: "已存在相同来源的 Overlay 草稿 v{version}。是否替换并重新生成？",
      overlayGenerated: "已生成 Overlay 草稿 v{version}，等待审核", overlayGenerationFailed: "Overlay 生成失败",
      evaluationConfirm: "将使用固定案例分别运行 Baseline 和 Candidate，并调用 LLM 盲评。通过后发布但不会自动启用，是否继续？",
      evaluationPublished: "自动评测通过，Overlay v{version} 已发布，未自动启用",
      evaluationRejected: "自动评测未通过：{gates}", evaluationDidNotPass: "自动评测未通过",
      overlayPageTitle: "Overlay 配置管理", overlayPageEyebrow: "Forge · 项目级 Skill 修正",
      overlayPageSubtitle: "审核、评测、发布并启用项目级 Overlay；同一项目和 Skill 同时只能启用一个版本。",
      overlayManagement: "Overlay 管理", reviewPage: "数据审核", summaryVersionsPage: "汇总管理",
      refreshOverlays: "刷新 Overlay", allOverlayStates: "全部 Overlay 状态",
      totalOverlays: "Overlay 总数", draftOverlays: "草稿", publishedOverlays: "已发布", activeOverlays: "已启用",
      overlayCount: "{count} 个 Overlay", noFilteredOverlays: "当前筛选范围没有 Overlay",
      overlayReviewApprove: "审核并确认", overlayContent: "Overlay 内容",
      overlayDraftHint: "确认内容后进入自动评测；审核不会自动发布或启用。",
      overlayCreated: "创建于 {time}", overlayPublishedAt: "发布于 {time}", overlayDisabledAt: "停用于 {time}",
      llmConfigSaved: "LLM 配置已保存", operationSucceeded: "操作完成",
      overlayReviewed: "Overlay 已审核，等待自动评测与发布",
      overlayActivated: "Overlay 已启用", overlayDisabled: "Overlay 已停用", overlayDeleted: "Overlay 已删除"
    },
    en: {
      language: "Language", chinese: "中文", english: "English",
      allProjects: "All projects", allSkills: "All Skills", allStatuses: "All statuses",
      refreshData: "Refresh data", refreshVersions: "Refresh summaries", versions: "Summary Management",
      active: "Active", excluded: "Excluded", deleted: "Deleted", reviewed: "Reviewed",
      draft: "Draft", confirmed: "Confirmed", pending: "Pending review", archived: "Archived",
      unavailable: "Unavailable", conflict: "Identity conflict", disabled: "Disabled", published: "Published",
      previous: "Previous", next: "Next", page: "Page {current} of {total}",
      records: "Collected records", summaries: "Skill training summaries", projectOverlay: "Project Overlay",
      selectScope: "Select a project and Skill", noScope: "No scope selected",
      loadingFailed: "Failed to load", operationFailed: "Operation failed",
      preCheck: "Pre-check", finalValidation: "Final validation",
      statusPending: "Pending", statusConfirmed: "Confirm", statusExcluded: "Exclude",
      reviewHomeTitle: "Learning Data Review",
      reviewHomeEyebrow: "Forge · local learning workspace",
      reviewHomeSubtitle: "Review project-isolated results and turn approved evidence into versioned Skill summaries.",
      currentScope: "Current scope:", filterRecords: "Filter collected records", perPage: "20 per page",
      searchPlaceholder: "Search output, notes, or run ID", applyFilters: "Apply filters",
      archiveProject: "Archive project", restoreProject: "Restore project",
      summaryNote: "Generate a version from reviewed active data in the selected project and Skill. Activation remains manual.",
      generateVersion: "Generate version", editedContent: "Edited content", reviewNote: "Review note",
      classicCase: "Mark as classic case", classicReason: "Why this is a classic case",
      keep: "Keep", exclude: "Exclude", delete: "Delete",
      currentResults: "Current results", pageActive: "Active on page", pageExcluded: "Excluded on page", pageDeleted: "Deleted on page",
      noRecords: "No records match the filters", recordCount: "{count} records",
      reviewedTag: "Reviewed", projectsUnavailable: "{count} projects are unavailable or have identity conflicts",
      archivedProjectsSuffix: "; {count} more are archived", archivedProjects: "{count} projects are archived and omitted from the all-project scan.",
      archiveConfirm: "Archive project “{name}”? Its data remains, but the all-project view will stop scanning it by default.",
      projectUpdateFailed: "Failed to update project status", projectArchived: "Project archived; its data remains available.",
      projectRestored: "Project restored.", projectStillUnavailable: "Project is still unavailable: {reason}",
      checkProjectPath: "Check the project path and database", chooseScopeFirst: "Select a project and Skill first",
      summarizeFailed: "Summary generation failed", versionGenerated: "Generated v{version}; it can be used as a project Overlay source",
      overlayAutoDisabled: "Overlay v{version} was disabled automatically: {negative} of {reviewed} reviewed records were excluded ({rate}%)",
      chooseScope: "Select a project and Skill", summariesLoadFailed: "Failed to load summary versions",
      effectiveRecords: "{count} active records", summarySourceNote: "A Summary is an Overlay source and does not directly affect Skill execution.",
      viewSummarySnapshot: "View summary snapshot", noSummary: "This Skill has no summary versions",
      recordsLoadFailed: "Failed to load collected records",
      hookConfiguration: "Collection Hook", hookConfigurationNote: "Forge Hooks for all three hosts can be enabled together. Turning one on installs or repairs only that host; turning it off asks for confirmation and removes only that host. Each project still controls collection through its enabled Skills.",
      codexTrustHint: "Trust reminder", codexTrustSummary: "If the Codex Hook is not yet trusted, confirm it in Codex Desktop",
      codexTrustSteps: "After applying the Codex Hook, open Codex Desktop → Settings → Hooks. Find the user Hook, review its command and select Trust, then start a new Codex session to reload the Hook configuration.",
      codexTrustNote: "Installed means the configuration was written, not that Codex trusts it. Trust it again after changing the Hook. If Trust is unavailable, check the default user config file:",
      codexTrustCustomHome: "If CODEX_HOME is set, check hooks.json in that directory instead.",
      globalSetting: "Local user setting",
      codexHost: "Codex", claudeCodeHost: "Claude Code", cursorHost: "Cursor",
      hookHostsActive: "Enabled hosts: {hosts}", hookNoneActive: "No collection Hooks are enabled", globalHookReady: "Local user Hook installed",
      globalHookMissing: "Local user Hook not installed", globalHookDrifted: "Hook configuration was modified",
      globalHookInvalid: "Host configuration file is invalid", hookRepairRequired: "Hook requires repair",
      hookNeverObserved: "Never observed", hookHealthy: "Recent event healthy",
      hookStale: "Last event is stale", hookRuntimeError: "Last event failed",
      hookInvoked: "Hook script invoked", hookSkipped: "Hook ran without capture", hookCaptured: "Hook captured",
      hookHandled: "Hook handled the event", hookNoInvocation: "No Hook invocation observed",
      hookHistorical: "Historical receipt only", enabledUnverified: "Enable status unverified", trustUnverified: "Trust status unverified", trustManual: "Confirm trust manually in Codex Desktop",
      latestRecordEvidence: "Latest record in this list", sourceSkill: "Captured by Skill", sourceHook: "Captured by Hook",
      sourceRuntime: "Captured by Runtime", hookPending: "Hook pending", hookMissed: "Hook did not capture",
      hookNotExpected: "Hook not expected", hookCapturedAt: "Hook captured at: {time}",
      hookInvocationId: "Invocation ID: {id}", hookHostEvidence: "Hook host: {host}", hookReceiptMatched: "Latest Hook receipt matches this invocation",
      hookQualityEvidence: "Capture profile: {format} · {attribution} · {characters} characters", hookMatchedSkills: "Matched Skills: {skills}",
      hookOnlyAuxiliary: "Hook-only supporting evidence", sharedReviewGroup: "Shared review · {count} Skills",
      sharedCapturePending: "Shared capture is finalizing; review is temporarily unavailable",
      sharedReviewApplied: "Reviewed once and applied to {count} Skill records",
      hookConfigured: "Enabled or repaired the {host} collection Hook", hookRemoved: "Removed the {host} collection Hook",
      hookUpdateFailed: "Hook configuration failed", hookStatusFailed: "Failed to load Hook status",
      hookPartialWarning: "Hook was partially updated; resolve the remaining configuration: {detail}",
      hookLastEvent: "Latest Hook receipt: {outcome} · {time}", hostRenderedOutput: "Host final output",
      removeHookConfirm: "Remove the local {host} user collection Hook? Other host Hooks and Skill-contract capture will remain available.",
      versionsTitle: "Skill Summary Management", versionsEyebrow: "Forge · training summaries",
      versionsSubtitle: "Review each refined rule before allowing the Summary to enter an Overlay.",
      backToReview: "Back to review", llmConfig: "LLM Refinement and Evaluation",
      llmConfigNote: "Used only when you select LLM refinement or automatic evaluation and publication.",
      baseUrlPlaceholder: "API base URL, e.g. https://example.com/v1",
      modelPlaceholder: "Model name", keyEnvPlaceholder: "API key environment variable",
      enableLlm: "Enable LLM refinement and evaluation", enableLlmTitle: "Enable or disable LLM refinement and evaluation",
      saveConfig: "Save configuration", eligibleRecords: "Eligible records", originalFindings: "Original findings",
      candidateThemes: "Candidate themes", candidateRules: "Candidate rules", compressedThemes: "Compressed themes",
      evidenceCount: "{count} evidence items", truncatedSources: " (showing 20; complete links are stored)",
      rationale: "Rationale:", reviewRules: "Review {count} refined rules", legacySnapshot: "View legacy snapshot",
      lockedSummary: "Historical summaries cannot be edited or deleted", saveReview: "Save review", refineLlm: "Refine with LLM",
      overlaySourceHint: "Available as a project Overlay source", sourceRecords: "{count} source records",
      summaryWindow: "{months}-month window, {classic} classic cases", noVersions: "No summary versions",
      versionCount: "{count} summary versions", refineConfirm: "Call the configured LLM and create a refined version in the current page language? The source version will remain unchanged.",
      refineFailed: "LLM refinement failed", llmReady: "LLM configuration is ready", llmUnavailable: "LLM is not configured or enabled",
      saveReviewFailed: "Failed to save review", deleteVersionConfirm: "Permanently delete this Summary version? This cannot be undone.",
      deleteFailed: "Delete failed", llmConfigSaveFailed: "Failed to save LLM configuration",
      llmSavedNeedsEnv: "LLM configuration saved; set the corresponding user environment variable",
      createOverlay: "Create Overlay draft", select: "Select", manageOverlayScope: "Select a project and Skill to manage Overlays",
      overlayLoadFailed: "Failed to load Overlays", summarySources: "{count} Summary sources",
      review: "Review", evaluatePublish: "Evaluate and publish", reevaluatePublish: "Re-evaluate and publish",
      activate: "Activate", disable: "Disable", overlayDelete: "Delete", noOverlay: "No Overlays",
      evaluationFailed: "Evaluation failed: {error}", evaluationSummary: "LLM evaluation · {count} fixed cases · confidence {confidence} · {gates}",
      gatePassed: "Passed", gateFailed: "Failed", evaluationReady: "Evaluation cases ready {count}/{required} · {categories}",
      evaluationInsufficient: "Insufficient evaluation cases {count}/{required}", evaluateTitle: "Evaluate fixed cases and publish automatically",
      activateConfirm: "Activate this Overlay? Any other ACTIVE Overlay for the same project and Skill will be disabled.",
      disableConfirm: "Disable this Overlay?", deleteOverlayConfirm: "Permanently delete this Overlay? This cannot be undone.",
      overlayOperationFailed: "Overlay operation failed", chooseReviewedSummaries: "Select reviewed Summaries from the same project and Skill",
      chooseOneSummary: "Select at least one reviewed Summary", replaceOverlayConfirm: "Overlay draft v{version} already uses the same sources. Replace and regenerate it?",
      overlayGenerated: "Created Overlay draft v{version}; review is pending", overlayGenerationFailed: "Overlay generation failed",
      evaluationConfirm: "Run fixed cases against Baseline and Candidate, then use an LLM for blind judging? Passing publishes the Overlay but does not activate it.",
      evaluationPublished: "Automatic evaluation passed; Overlay v{version} is published but not activated",
      evaluationRejected: "Automatic evaluation failed: {gates}", evaluationDidNotPass: "Automatic evaluation failed",
      overlayPageTitle: "Overlay Configuration", overlayPageEyebrow: "Forge · project Skill corrections",
      overlayPageSubtitle: "Review, evaluate, publish, and activate project Overlays. Only one version can be active for each project and Skill.",
      overlayManagement: "Overlay Management", reviewPage: "Data review", summaryVersionsPage: "Summary management",
      refreshOverlays: "Refresh Overlays", allOverlayStates: "All Overlay states",
      totalOverlays: "Total Overlays", draftOverlays: "Drafts", publishedOverlays: "Published", activeOverlays: "Active",
      overlayCount: "{count} Overlays", noFilteredOverlays: "No Overlays match the current filters",
      overlayReviewApprove: "Review and approve", overlayContent: "Overlay content",
      overlayDraftHint: "Approve the content before automatic evaluation. Review does not publish or activate it.",
      overlayCreated: "Created {time}", overlayPublishedAt: "Published {time}", overlayDisabledAt: "Disabled {time}",
      llmConfigSaved: "LLM configuration saved", operationSucceeded: "Operation completed",
      overlayReviewed: "Overlay reviewed; automatic evaluation and publication are pending",
      overlayActivated: "Overlay activated", overlayDisabled: "Overlay disabled", overlayDeleted: "Overlay deleted"
    }
  };

  function readLanguage() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return SUPPORTED.has(saved) ? saved : "en";
    } catch (_error) {
      return "en";
    }
  }

  let language = readLanguage();

  function t(key, values = {}) {
    const template = messages[language][key] ?? messages["zh-CN"][key] ?? key;
    return String(template).replace(/\{([a-zA-Z]+)\}/g, (_match, name) => values[name] ?? "");
  }

  function apply(root = document) {
    document.documentElement.lang = language;
    root.querySelectorAll("[data-i18n]").forEach(element => {
      element.textContent = t(element.dataset.i18n);
    });
    root.querySelectorAll("[data-i18n-placeholder]").forEach(element => {
      element.placeholder = t(element.dataset.i18nPlaceholder);
    });
    root.querySelectorAll("[data-i18n-title]").forEach(element => {
      element.title = t(element.dataset.i18nTitle);
    });
  }

  function setLanguage(next) {
    if (!SUPPORTED.has(next)) return;
    language = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch (_error) {
      // Language still applies for the current page when storage is unavailable.
    }
    apply();
  }

  function mountSelector(container) {
    if (container.querySelector(".language-control")) return;
    if (!document.getElementById("forge-learning-language-style")) {
      const style = document.createElement("style");
      style.id = "forge-learning-language-style";
      style.textContent = ".language-control{display:flex;align-items:center;gap:7px;color:#c9d7e5;font-size:11px;font-weight:600;white-space:nowrap}.language-control select{min-width:96px;height:36px;padding:7px 28px 7px 10px;border:1px solid #557189;background:#fff;color:#172033;border-radius:6px}.language-control select:focus{outline:2px solid rgba(80,173,220,.32);outline-offset:1px}@media(max-width:760px){.language-control{grid-column:1/-1;justify-content:space-between;width:100%}.language-control select{flex:0 0 112px}}";
      document.head.appendChild(style);
    }
    const wrapper = document.createElement("label");
    wrapper.className = "language-control";
    wrapper.innerHTML = `<span data-i18n="language"></span><select aria-label="Language"><option value="zh-CN">中文</option><option value="en">English</option></select>`;
    const select = wrapper.querySelector("select");
    select.value = language;
    select.addEventListener("change", () => {
      setLanguage(select.value);
      window.location.reload();
    });
    container.prepend(wrapper);
    apply(wrapper);
  }

  document.documentElement.lang = language;
  window.ForgeI18n = {t, apply, setLanguage, mountSelector, get language() { return language; }};
})();
