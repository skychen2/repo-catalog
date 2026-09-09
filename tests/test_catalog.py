#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""目录生成、审计和刷新脚本的回归测试。"""
import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(filename, module_name):
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CatalogScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.scripts = self.root / "scripts"
        self.scripts.mkdir()
        self.generate = load_script("generate.py", "generate_for_test")
        self.audit = load_script("audit.py", "audit_for_test")
        self.refresh = load_script("refresh_external_repos.py", "refresh_for_test")

    def tearDown(self):
        self.temp.cleanup()

    def write_curated(self, entries):
        (self.scripts / "curated.json").write_text(
            json.dumps(entries), encoding="utf-8"
        )

    def write_repos(self, rows):
        path = self.root / "repos.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        return path

    def run_generate(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        argv = ["generate.py", *(str(arg) for arg in args)]
        with mock.patch.object(self.generate, "HERE", str(self.scripts)), \
             mock.patch.object(self.generate, "ROOT", str(self.root)), \
             mock.patch.object(sys, "argv", argv), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.generate.main()

    def test_public_generation_rejects_unknown_flags_and_private_entries(self):
        self.write_curated({
            "public-repo": {
                "category": "dev-data-tools",
                "cn": "public",
                "keywords": ["public"],
            },
            "external-repo": {
                "external": True,
                "owner": "owner",
                "category": "dev-data-tools",
                "cn": "external",
                "keywords": ["external"],
                "topics": "web, crawler",
                "checkError": "http_403",
                "lastCheckedAt": "2026-01-01",
            },
            "private-repo": {
                "visibility": "PRIVATE",
                "category": "personal-projects",
                "cn": "private",
                "keywords": ["private"],
            },
        })
        repos_path = self.write_repos([{
            "name": "public-repo",
            "url": "https://github.com/skychen2/public-repo",
            "visibility": "PUBLIC",
            "isFork": False,
            "primaryLanguage": {"name": "Python"},
            "stargazerCount": 1,
            "forkCount": 0,
            "updatedAt": "2026-01-01",
            "pushedAt": "2026-01-01",
            "archived": False,
            "disabled": True,
            "license": "MIT",
            "repositoryTopics": [{"name": "python"}],
        }])

        with self.assertRaises(SystemExit) as error:
            self.run_generate("--publci", repos_path)
        self.assertEqual(error.exception.code, 2)

        self.run_generate("--public", repos_path)
        rows = json.loads((self.root / "data" / "repos.json").read_text(encoding="utf-8"))
        by_name = {row["name"]: row for row in rows}
        self.assertNotIn("private-repo", by_name)
        self.assertEqual(by_name["public-repo"]["topics"], ["python"])
        self.assertTrue(by_name["public-repo"]["disabled"])
        self.assertEqual(by_name["public-repo"]["license"], "MIT")
        self.assertEqual(by_name["external-repo"]["topics"], ["web", "crawler"])
        self.assertEqual(by_name["external-repo"]["checkError"], "http_403")

        review_path = self.root / "review.json"
        with mock.patch.object(sys, "argv", [
            "audit.py", "--input", str(self.root / "data" / "repos.json"),
            "--output", str(review_path),
        ]), contextlib.redirect_stdout(io.StringIO()):
            self.audit.main()
        review = json.loads(review_path.read_text(encoding="utf-8"))
        external = next(item for item in review["items"] if item["name"] == "external-repo")
        self.assertIn("external_metadata_refresh_failed", external["reasons"])

    def test_owner_qualified_keys_preserve_same_named_projects(self):
        self.write_curated({
            "owner-a/shared": {
                "external": True,
                "owner": "owner-a",
                "category": "dev-data-tools",
                "cn": "a",
                "keywords": ["a"],
            },
            "owner-b/shared": {
                "external": True,
                "owner": "owner-b",
                "category": "dev-data-tools",
                "cn": "b",
                "keywords": ["b"],
            },
        })
        repos_path = self.write_repos([])
        self.run_generate("--public", repos_path)
        rows = json.loads((self.root / "data" / "repos.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(row["name"] for row in rows), ["owner-a/shared", "owner-b/shared"])
        self.assertEqual(
            {row["url"] for row in rows},
            {"https://github.com/owner-a/shared", "https://github.com/owner-b/shared"},
        )

    def test_invalid_category_fails_before_writing_outputs(self):
        self.write_curated({
            "bad-repo": {
                "category": "not-a-category",
                "cn": "bad",
                "keywords": ["bad"],
            }
        })
        repos_path = self.write_repos([{
            "name": "bad-repo",
            "visibility": "PUBLIC",
            "isFork": False,
            "primaryLanguage": None,
            "repositoryTopics": [],
        }])

        with self.assertRaises(SystemExit) as error:
            self.run_generate("--public", repos_path)
        self.assertEqual(error.exception.code, 2)
        self.assertFalse((self.root / "data" / "repos.json").exists())

    def test_invalid_lifecycle_fails_before_writing_outputs(self):
        self.write_curated({
            "bad-repo": {
                "category": "dev-data-tools",
                "cn": "bad",
                "keywords": ["bad"],
                "status": "not-a-status",
            }
        })
        repos_path = self.write_repos([{
            "name": "bad-repo",
            "visibility": "PUBLIC",
            "isFork": False,
            "primaryLanguage": None,
            "repositoryTopics": [],
        }])

        with self.assertRaises(SystemExit) as error:
            self.run_generate("--public", repos_path)
        self.assertEqual(error.exception.code, 2)
        self.assertFalse((self.root / "data" / "repos.json").exists())

    def test_refresh_failure_keeps_last_success_and_returns_failure(self):
        curated_path = self.scripts / "curated.json"
        curated_path.write_text(json.dumps({
            "external-repo": {
                "external": True,
                "owner": "owner",
                "lastCheckedAt": "2025-01-01",
            }
        }), encoding="utf-8")
        with mock.patch.object(self.refresh, "CURATED_PATH", str(curated_path)), \
             mock.patch.object(self.refresh, "auth_token", return_value="token"), \
             mock.patch.object(self.refresh, "fetch_repo", return_value=("external-repo", None, "http_403")), \
             mock.patch.object(sys, "argv", ["refresh_external_repos.py"]), \
             contextlib.redirect_stdout(io.StringIO()):
            result = self.refresh.main()

        self.assertEqual(result, 1)
        saved = json.loads(curated_path.read_text(encoding="utf-8"))["external-repo"]
        self.assertEqual(saved["checkError"], "http_403")
        self.assertEqual(saved["lastCheckedAt"], "2025-01-01")


if __name__ == "__main__":
    unittest.main()
