# -*- coding: utf-8 -*-
"""Tests for forge_cli.query_helpers — registry listing and search."""

import json

from forge_cli.query_helpers import (
    contains_any,
    find_item,
    find_pack_by_query,
    find_skill_by_query,
    list_modules_by_kind,
    match_all_keyword_groups,
)


class TestListModulesByKind:
    def test_skills(self, populated_forge_root):
        items = list_modules_by_kind(populated_forge_root, "skills")
        assert len(items) >= 3
        ids = [i["id"] for i in items]
        assert "skill.code_review" in ids

    def test_packs(self, populated_forge_root):
        items = list_modules_by_kind(populated_forge_root, "packs")
        assert isinstance(items, list)

    def test_behaviors(self, populated_forge_root):
        items = list_modules_by_kind(populated_forge_root, "behaviors")
        # modules.json layers take priority; we have 1 behavior registered there
        assert len(items) >= 1
        ids = [i["id"] for i in items]
        assert "behavior.review" in ids

    def test_unknown_kind(self, populated_forge_root):
        items = list_modules_by_kind(populated_forge_root, "nonexistent")
        assert items == []


class TestFindItem:
    def test_by_id(self, populated_forge_root):
        item = find_item(populated_forge_root, "skills", "skill.code_review")
        assert item is not None
        assert item["name"] == "code-review"

    def test_by_name(self, populated_forge_root):
        item = find_item(populated_forge_root, "skills", "code-review")
        assert item is not None
        assert item["id"] == "skill.code_review"

    def test_by_name_with_hyphen(self, populated_forge_root):
        item = find_item(populated_forge_root, "skills", "code-review")
        assert item is not None

    def test_not_found(self, populated_forge_root):
        item = find_item(populated_forge_root, "skills", "nonexistent")
        assert item is None


class TestFindSkillByQuery:
    def test_finds_skill(self, populated_forge_root):
        skill = find_skill_by_query(populated_forge_root, "code-review")
        assert skill is not None
        assert skill["id"] == "skill.code_review"


class TestFindPackByQuery:
    def test_finds_pack_on_disk(self, populated_forge_root):
        pack = find_pack_by_query(populated_forge_root, "pack.test_pack")
        assert pack is not None
        assert pack["id"] == "pack.test_pack"

    def test_finds_by_name(self, populated_forge_root):
        pack = find_pack_by_query(populated_forge_root, "Test Pack")
        assert pack is not None
        assert pack["id"] == "pack.test_pack"

    def test_not_found(self, populated_forge_root):
        pack = find_pack_by_query(populated_forge_root, "nonexistent")
        assert pack is None


class TestContainsAny:
    def test_finds_keywords(self):
        hits = contains_any("review this spring code", ["spring", "java", "debug"])
        assert "spring" in hits
        assert "java" not in hits
        assert "debug" not in hits

    def test_chinese(self):
        hits = contains_any("帮我排查线上故障", ["排查", "debug"])
        assert "排查" in hits

    def test_no_hits(self):
        hits = contains_any("hello world", ["debug", "error"])
        assert hits == []


class TestMatchAllKeywordGroups:
    def test_all_groups_match(self):
        ok, hits = match_all_keyword_groups(
            "review this spring code",
            [["review", "debug"], ["spring", "java"]]
        )
        assert ok is True
        assert "review" in hits
        assert "spring" in hits

    def test_one_group_fails(self):
        ok, hits = match_all_keyword_groups(
            "review this python code",
            [["review"], ["spring", "java"]]
        )
        assert ok is False

    def test_empty_groups(self):
        ok, hits = match_all_keyword_groups("anything", [])
        assert ok is True
