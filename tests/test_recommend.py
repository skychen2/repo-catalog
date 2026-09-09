#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""推荐结果回归测试。"""
import json
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASES_PATH = pathlib.Path(__file__).with_name("recommend_cases.json")


class RecommendationTests(unittest.TestCase):
    def test_representative_fuzzy_queries(self):
        cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        failures = []
        for case in cases:
            output = subprocess.check_output(
                ["python3", "scripts/recommend.py", case["query"], "--top", "3", "--json"],
                cwd=ROOT,
                text=True,
            )
            results = json.loads(output)["results"]
            if not results:
                failures.append(f"{case['query']}: no results")
                continue
            top = results[0]
            if top["name"] != case["expectedTop"]:
                failures.append(
                    f"{case['query']}: expected {case['expectedTop']}, got {top['name']}"
                )
            if top["featureScore"] <= 0:
                failures.append(f"{case['query']}: top result has no feature match")
            if not top.get("reason") or not top.get("difference"):
                failures.append(f"{case['query']}: top result lacks explanation")
            if not isinstance(top.get("alternatives"), list):
                failures.append(f"{case['query']}: alternatives is not a list")
        self.assertFalse("; ".join(failures), "\n".join(failures))


    def test_alternatives_exclude_hidden_projects(self):
        output = subprocess.check_output(
            ["python3", "scripts/recommend.py", "终端 AI 编程助手", "--top", "1", "--json"],
            cwd=ROOT,
            text=True,
        )
        result = json.loads(output)["results"][0]
        self.assertNotIn("opencode", result["alternatives"])

        for query in ["完全不存在的功能xyz", "一个完全不相关的需求"]:
            output = subprocess.check_output(
                ["python3", "scripts/recommend.py", query, "--json"],
                cwd=ROOT,
                text=True,
            )
            self.assertEqual(json.loads(output)["results"], [], query)

    def test_blank_query_is_rejected(self):
        result = subprocess.run(
            ["python3", "scripts/recommend.py", "   "],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("查询内容不能为空", result.stderr)

    def test_non_positive_top_is_rejected(self):
        result = subprocess.run(
            ["python3", "scripts/recommend.py", "网页抓取", "--top", "0"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("必须是大于 0 的整数", result.stderr)


if __name__ == "__main__":
    unittest.main()
