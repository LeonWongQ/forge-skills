# -*- coding: utf-8 -*-
"""Tests for forge_cli.constants — exit codes, keyword sets, mappings."""

from forge_cli.constants import (
    ALL_CHECKS,
    CHECK_CONTRACTS,
    CHECK_DERIVED_REGISTRY,
    CHECK_PACK_REFS,
    CHECK_PACKS,
    CHECK_PATHS,
    CHECK_REFS,
    CHECK_REGISTRY,
    CHECK_SEMANTICS,
    DEBUG_KEYWORDS,
    ERROR_ANALYSIS_KEYWORDS,
    EXIT_GENERAL_ERROR,
    EXIT_OK,
    EXIT_USAGE_ERROR,
    EXIT_VALIDATION_FAILED,
    INCIDENT_KEYWORDS,
    MIGRATION_KEYWORDS,
    PACK_CROSS_SKILL_ALLOWED,
    PLAN_KEYWORDS,
    REFACTOR_KEYWORDS,
    REGISTRY_SCHEMA_CANDIDATES,
    TEST_DESIGN_KEYWORDS,
    TEST_IMPLEMENTATION_KEYWORDS,
)


class TestExitCodes:
    def test_exit_codes_are_distinct(self):
        codes = [EXIT_OK, EXIT_GENERAL_ERROR, EXIT_VALIDATION_FAILED,
                 EXIT_USAGE_ERROR]
        assert len(codes) == len(set(codes))

    def test_exit_ok_is_zero(self):
        assert EXIT_OK == 0


class TestCheckNames:
    def test_all_checks_contains_eight_items(self):
        assert len(ALL_CHECKS) == 8
        assert CHECK_REGISTRY in ALL_CHECKS
        assert CHECK_PATHS in ALL_CHECKS
        assert CHECK_REFS in ALL_CHECKS
        assert CHECK_PACKS in ALL_CHECKS
        assert CHECK_PACK_REFS in ALL_CHECKS
        assert CHECK_SEMANTICS in ALL_CHECKS
        assert CHECK_CONTRACTS in ALL_CHECKS
        assert CHECK_DERIVED_REGISTRY in ALL_CHECKS

    def test_all_checks_no_duplicates(self):
        assert len(ALL_CHECKS) == len(set(ALL_CHECKS))


class TestRegistrySchemaCandidates:
    def test_keys_are_json_filenames(self):
        for key in REGISTRY_SCHEMA_CANDIDATES:
            assert key.endswith(".json")

    def test_contains_expected_entries(self):
        assert "skills.json" in REGISTRY_SCHEMA_CANDIDATES
        assert "modules.json" in REGISTRY_SCHEMA_CANDIDATES
        assert "packs.json" in REGISTRY_SCHEMA_CANDIDATES
        assert "behaviors.json" in REGISTRY_SCHEMA_CANDIDATES


class TestKeywordSets:
    def test_all_sets_contain_strings(self):
        all_sets = [
            TEST_DESIGN_KEYWORDS, TEST_IMPLEMENTATION_KEYWORDS,
            PLAN_KEYWORDS, MIGRATION_KEYWORDS, REFACTOR_KEYWORDS,
            INCIDENT_KEYWORDS, ERROR_ANALYSIS_KEYWORDS, DEBUG_KEYWORDS,
        ]
        for kw_set in all_sets:
            assert isinstance(kw_set, set)
            for kw in kw_set:
                assert isinstance(kw, str), f"Non-string keyword: {kw}"
                assert kw.strip(), f"Empty keyword in set"

    def test_test_design_has_chinese(self):
        assert "测试" in TEST_DESIGN_KEYWORDS
        assert "测试用例" in TEST_DESIGN_KEYWORDS

    def test_incident_has_chinese(self):
        assert "线上" in INCIDENT_KEYWORDS
        assert "故障" in INCIDENT_KEYWORDS
        assert "事故" in INCIDENT_KEYWORDS

    def test_debug_has_keywords(self):
        assert "debug" in DEBUG_KEYWORDS
        assert "排查" in DEBUG_KEYWORDS

    def test_pack_cross_skill_allowed(self):
        assert "pack.general_test_report" in PACK_CROSS_SKILL_ALLOWED
        assert "pack.playwright_debug" in PACK_CROSS_SKILL_ALLOWED
