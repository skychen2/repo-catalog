#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新增仓库入口的回归测试。"""
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


def load_add_repo():
    path = ROOT / "scripts" / "add_repo.py"
    spec = importlib.util.spec_from_file_location("add_repo_for_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AddRepoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.here = self.root / "scripts"
        self.here.mkdir()
        (self.here / "curated.json").write_text("{}", encoding="utf-8")
        self.add_repo = load_add_repo()

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def fake_gh(args):
        class Response:
            returncode = 0
            stderr = ""
            stdout = ""

        response = Response()
        target = args[1].split("/")
        owner, name = target[1], target[2]
        response.stdout = json.dumps({
            "name": name,
            "full_name": f"{owner}/{name}",
            "description": "description",
            "fork": False,
            "language": "Python",
            "html_url": f"https://github.com/{owner}/{name}",
            "visibility": "PUBLIC",
            "archived": False,
            "disabled": False,
            "stars": 1,
            "forks": 0,
            "updated_at": "2026-01-01",
            "pushed_at": "2026-01-01",
        })
        return response

    def run_add(self, *args):
        with mock.patch.object(self.add_repo, "HERE", str(self.here)), \
             mock.patch.object(self.add_repo, "gh", side_effect=self.fake_gh), \
             mock.patch.object(sys, "argv", ["add_repo.py", *args]), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.add_repo.main()

    def test_same_name_different_owner_is_rejected(self):
        self.run_add("owner-a/shared", "--cat", "dev-data-tools")
        self.run_add("owner-b/shared", "--cat", "dev-data-tools")

        curated = json.loads((self.here / "curated.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(curated), ["owner-a/shared", "owner-b/shared"])
        self.assertEqual(curated["owner-a/shared"]["owner"], "owner-a")
        self.assertEqual(curated["owner-b/shared"]["owner"], "owner-b")

    def test_existing_owned_repo_is_migrated_on_external_name_collision(self):
        (self.here / "curated.json").write_text(json.dumps({
            "shared": {
                "category": "dev-data-tools",
                "cn": "owned",
                "keywords": ["owned"],
            }
        }), encoding="utf-8")

        self.run_add("owner-b/shared", "--cat", "dev-data-tools")
        curated = json.loads((self.here / "curated.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(curated), ["owner-b/shared", "skychen2/shared"])

    def test_same_repo_is_reported_as_existing(self):
        self.run_add("owner-a/shared", "--cat", "dev-data-tools")
        with self.assertRaises(SystemExit) as error:
            self.run_add("https://github.com/OWNER-A/shared", "--cat", "dev-data-tools")
        self.assertEqual(error.exception.code, 0)

        curated = json.loads((self.here / "curated.json").read_text(encoding="utf-8"))
        self.assertEqual(list(curated), ["shared"])

    def test_invalid_category_is_rejected_before_api_call(self):
        with mock.patch.object(self.add_repo, "gh") as gh:
            with self.assertRaises(SystemExit) as error:
                with mock.patch.object(self.add_repo, "HERE", str(self.here)), \
                     mock.patch.object(sys, "argv", [
                         "add_repo.py", "owner/repo", "--cat", "bad-category"
                     ]), \
                     contextlib.redirect_stderr(io.StringIO()):
                    self.add_repo.main()
        self.assertEqual(error.exception.code, 2)
        gh.assert_not_called()
        curated = json.loads((self.here / "curated.json").read_text(encoding="utf-8"))
        self.assertEqual(curated, {})


if __name__ == "__main__":
    unittest.main()
