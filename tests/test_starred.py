#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Star 仓库发现器的回归测试。"""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script():
    path = ROOT / "scripts" / "fetch_starred_repos.py"
    spec = importlib.util.spec_from_file_location("fetch_starred_for_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StarredRepoTests(unittest.TestCase):
    def setUp(self):
        self.script = load_script()

    @staticmethod
    def repo(owner, name, description="description"):
        return {
            "full_name": f"{owner}/{name}",
            "name": name,
            "html_url": f"https://github.com/{owner}/{name}",
            "description": description,
            "language": "Python",
            "stargazers_count": 10,
            "forks_count": 2,
            "updated_at": "2026-01-01T00:00:00Z",
            "pushed_at": "2026-01-01T00:00:00Z",
            "topics": ["agent"],
            "fork": False,
        }

    def test_new_star_is_added_and_owned_repos_are_skipped(self):
        curated = {}
        stats = self.script.merge_starred(curated, [
            {"repo": self.repo("owner-a", "project"), "starredAt": "2026-01-02T00:00:00Z"},
            {"repo": self.repo("skychen2", "own-project"), "starredAt": "2026-01-03T00:00:00Z"},
        ], "2026-01-04")

        self.assertEqual(stats["added"], 1)
        self.assertEqual(stats["owned"], 1)
        self.assertIn("project", curated)
        self.assertEqual(curated["project"]["owner"], "owner-a")
        self.assertEqual(curated["project"]["starredAt"], "2026-01-02T00:00:00Z")
        self.assertEqual(curated["project"]["category"], "dev-data-tools")

    def test_existing_star_updates_metadata_without_overwriting_manual_fields(self):
        curated = {
            "project": {
                "external": True,
                "owner": "owner-a",
                "category": "ai-llm-agents",
                "cn": "人工说明",
                "keywords": ["人工关键词"],
                "status": "active",
            }
        }
        stats = self.script.merge_starred(
            curated,
            [{"repo": self.repo("owner-a", "project", "new description")}],
            "2026-01-04",
        )

        self.assertEqual(stats["updated"], 1)
        self.assertEqual(curated["project"]["category"], "ai-llm-agents")
        self.assertEqual(curated["project"]["cn"], "人工说明")
        self.assertEqual(curated["project"]["keywords"], ["人工关键词"])
        self.assertEqual(curated["project"]["status"], "active")
        self.assertEqual(curated["project"]["description"], "new description")

    def test_same_name_different_owner_migrates_both_keys(self):
        curated = {
            "shared": {
                "category": "dev-data-tools",
                "cn": "已有项目",
                "keywords": ["existing"],
            }
        }
        stats = self.script.merge_starred(
            curated,
            [{"repo": self.repo("owner-b", "shared")}],
            "2026-01-04",
        )

        self.assertEqual(stats["migrated"], 1)
        self.assertEqual(stats["added"], 1)
        self.assertEqual(sorted(curated), ["owner-b/shared", "skychen2/shared"])
        self.assertEqual(curated["skychen2/shared"]["cn"], "已有项目")
        self.assertEqual(curated["owner-b/shared"]["owner"], "owner-b")


if __name__ == "__main__":
    unittest.main()
