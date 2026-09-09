#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据模糊功能需求推荐目录中的仓库。

用法:
    python3 scripts/recommend.py "批量生成短视频"
    python3 scripts/recommend.py "终端 AI 编程助手" --top 3
    python3 scripts/recommend.py "网页抓取" --category dev-data-tools --json

排序顺序固定为:
    1. 功能需求匹配度
    2. 人工优先级(primary > alternative > reference)
    3. GitHub 活跃度
    4. GitHub 热度
"""
import argparse
import datetime as dt
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA_PATH = os.path.join(ROOT, "data", "repos.json")
GROUP_NOTES_PATH = os.path.join(HERE, "group_notes.json")

PRIORITY_RANK = {"primary": 3, "alternative": 2, "reference": 1, "unclassified": 0}
HIDDEN_STATUSES = {"archived", "obsolete", "replaced"}
MIN_FEATURE_SCORE = 20
GENERIC_ENGLISH = {"ai", "app", "apps", "tool", "tools", "open", "source", "github", "project", "projects", "api"}
FUNCTION_ALIASES = [
    ("编程", ("编程", "编码", "代码", "code", "coding", "developer", "开发")),
    ("助手", ("助手", "agent", "智能体")),
    ("抓取", ("抓取", "爬虫", "scraping", "crawler")),
    ("提示词", ("提示词", "prompt")),
    ("笔记", ("笔记", "notes", "memos")),
    ("短视频", ("短视频", "视频生成", "自动剪辑", "video")),
]


def normalize(value):
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(value or "").lower())


def english_tokens(value):
    return set(re.findall(r"[a-z][a-z0-9+.#_-]{1,}", str(value or "").lower()))


def chinese_ngrams(value):
    runs = re.findall(r"[\u4e00-\u9fff]+", str(value or ""))
    grams = set()
    for run in runs:
        for size in (2, 3, 4):
            grams.update(run[index:index + size] for index in range(len(run) - size + 1))
    return grams


def activity_rank(row):
    date_value = row.get("pushedAt") or row.get("updatedAt")
    try:
        age = (dt.date.today() - dt.date.fromisoformat(str(date_value)[:10])).days
    except (TypeError, ValueError):
        return 0
    if age <= 90:
        return 3
    if age <= 365:
        return 2
    return 1


def activity_label(row):
    labels = {3: "近期活跃", 2: "近一年有更新", 1: "较久未更新", 0: "缺少更新时间"}
    return labels[activity_rank(row)]

def explain_result(result, rows, group_notes):
    group = result.get("duplicateGroup", "")
    peers = [row for row in rows if group and row.get("duplicateGroup") == group
             and row.get("name") != result["name"]
             and not row.get("missing")
             and row.get("status") not in HIDDEN_STATUSES]
    peers.sort(key=lambda row: PRIORITY_RANK.get(row.get("priority"), 0), reverse=True)
    alternatives = [row["name"] for row in peers]
    if result["priority"] == "primary":
        role = "同组主推荐"
    elif result["priority"] == "alternative":
        role = "同组备选"
    elif result["priority"] == "reference":
        role = "同组参考"
    else:
        role = "尚未设置组内主次"
    matched = "、".join(result["matchedKeywords"]) or "功能描述"
    reason = f"功能匹配: {matched}; {role}; {activity_label(result)}; 热度 {result['stars']}★"
    note = group_notes.get(group, {})
    scenario = note.get("summary", "")
    if alternatives:
        difference = note.get("selection", "") or f"同组项目: {', '.join(alternatives)}"
    else:
        difference = scenario or "暂无已归组的直接替代项目"
    result["alternatives"] = alternatives
    result["groupSummary"] = scenario
    result["reason"] = reason
    result["difference"] = difference

def match_row(row, query):
    query_normalized = normalize(query)
    query_english = english_tokens(query) - GENERIC_ENGLISH
    query_chinese = chinese_ngrams(query)
    keywords = [str(value) for value in row.get("keywords", []) if str(value).strip()]
    searchable = " ".join(str(value) for value in [
        row.get("name", ""), row.get("cn", ""), row.get("description", ""),
        row.get("topics", ""), " ".join(keywords)
    ])
    searchable_normalized = normalize(searchable)
    searchable_english = english_tokens(searchable)
    searchable_chinese = chinese_ngrams(searchable)

    score = 0
    matched = []
    for keyword in keywords:
        keyword_normalized = normalize(keyword)
        if keyword_normalized and (keyword_normalized in query_normalized or query_normalized in keyword_normalized):
            score += 100
            matched.append(keyword)
            continue
        shared = len(chinese_ngrams(keyword) & query_chinese)
        if shared >= 2:
            score += min(60, shared * 10)
            matched.append(keyword)

    shared_english = query_english & searchable_english
    score += len(shared_english) * 30
    matched.extend(sorted(shared_english))
    for label, aliases in FUNCTION_ALIASES:
        query_hit = any(normalize(alias) in query_normalized for alias in aliases)
        feature_hit = any(normalize(alias) in searchable_normalized for alias in aliases)
        if query_hit and feature_hit:
            score += 30
            matched.append(label)
    score += min(40, len(query_chinese & searchable_chinese) * 2)
    if query_normalized and query_normalized in searchable_normalized:
        score += 50

    return score, sorted(set(matched), key=str.lower)


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("必须是大于 0 的整数")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="模糊功能需求")
    parser.add_argument("--top", type=positive_int, default=5, help="返回数量,默认 5")
    parser.add_argument("--category", help="限定分类 key")
    parser.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    args = parser.parse_args()
    if not normalize(args.query):
        parser.error("查询内容不能为空")

    with open(DATA_PATH, encoding="utf-8") as file:
        rows = json.load(file)
    with open(GROUP_NOTES_PATH, encoding="utf-8") as file:
        group_notes = json.load(file)
    results = []
    for row in rows:
        if args.category and row.get("category") != args.category:
            continue
        if row.get("missing") or row.get("status") in HIDDEN_STATUSES:
            continue
        feature_score, matched = match_row(row, args.query)
        if feature_score < MIN_FEATURE_SCORE:
            continue
        results.append({
            "name": row["name"],
            "url": row.get("url", ""),
            "category": row.get("category", ""),
            "cn": row.get("cn", ""),
            "matchedKeywords": matched,
            "status": row.get("status", "unreviewed"),
            "priority": row.get("priority", "unclassified"),
            "duplicateGroup": row.get("duplicateGroup", ""),
            "stars": row.get("stars", 0),
            "pushedAt": row.get("pushedAt") or row.get("updatedAt", ""),
            "featureScore": feature_score,
            "sortKey": [feature_score, PRIORITY_RANK.get(row.get("priority"), 0),
                        activity_rank(row), math.log10(1 + row.get("stars", 0))],
        })
    results.sort(key=lambda row: tuple(row["sortKey"]), reverse=True)
    results = results[:args.top]
    for result in results:
        explain_result(result, rows, group_notes)

    if args.as_json:
        print(json.dumps({"query": args.query, "results": results}, ensure_ascii=False, indent=2))
        return
    if not results:
        print("目录中没有匹配项目。")
        return
    for index, row in enumerate(results, 1):
        matched = "、".join(row["matchedKeywords"]) or "功能描述"
        print(f"{index}. {row['name']} [{row['category']}]")
        print(f"   {row['cn']}")
        print(f"   匹配: {matched} | 优先级: {row['priority']} | 状态: {row['status']} | "
              f"{row['stars']}★ | {row['url']}")
        print(f"   理由: {row['reason']}")
        print(f"   差异: {row['difference']}")


if __name__ == "__main__":
    main()
