#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计仓库目录,生成需要人工处理的清单。

用法:
    python3 scripts/audit.py
    python3 scripts/audit.py --input data/repos.json --output data/review-needed.json
    python3 scripts/audit.py --stale-days 730
"""
import argparse
import datetime as dt
import json
import os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VALID_STATUSES = {"unreviewed", "active", "watch", "archived", "obsolete", "replaced"}
VALID_PRIORITIES = {"unclassified", "primary", "alternative", "reference"}


def parse_date(value):
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def grouped(rows, field):
    groups = defaultdict(list)
    for row in rows:
        value = str(row.get(field) or "").strip().lower().rstrip("/")
        if value:
            groups[value].append(row["name"])
    return {key: names for key, names in groups.items() if len(names) > 1}


def functional_candidates(rows):
    """按同分类关键词重叠生成候选,只供人工确认,不自动合并。"""
    ignored = {"ai", "api", "github", "开源", "项目", "工具", "系统", "脚本", "教程", "模型"}
    by_category = defaultdict(list)
    for row in rows:
        keywords = {str(value).strip().lower() for value in row.get("keywords", [])
                    if str(value).strip() and str(value).strip().lower() not in ignored}
        by_category[row.get("category", "")].append((row, keywords))

    candidates = []
    for category, category_rows in by_category.items():
        for index, (left, left_keywords) in enumerate(category_rows):
            for right, right_keywords in category_rows[index + 1:]:
                shared = sorted(left_keywords & right_keywords)
                if not shared:
                    continue
                union = left_keywords | right_keywords
                score = len(shared) / max(1, len(union))
                if len(shared) < 2:
                    if len(shared) != 1 or len(shared[0]) < 4 or score < 0.35:
                        continue
                elif score < 0.25:
                    continue
                candidates.append({
                    "category": category,
                    "score": round(score, 3),
                    "sharedKeywords": shared,
                    "repositories": [left["name"], right["name"]],
                    "descriptions": [left.get("cn", ""), right.get("cn", "")],
                })
    return sorted(candidates, key=lambda item: (-item["score"], item["category"], item["repositories"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=os.path.join(ROOT, "data", "repos.json"))
    parser.add_argument("--output", default=os.path.join(ROOT, "data", "review-needed.json"))
    parser.add_argument("--stale-days", type=int, default=365)
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as file:
        rows = json.load(file)
    today = dt.date.today()
    by_name = {row["name"]: row for row in rows}
    functional = functional_candidates(rows)
    unassigned_functional = [candidate for candidate in functional
                             if not (by_name[candidate["repositories"][0]].get("duplicateGroup")
                                     and by_name[candidate["repositories"][0]].get("duplicateGroup")
                                     == by_name[candidate["repositories"][1]].get("duplicateGroup"))]
    items = []
    reason_counts = Counter()
    status_counts = Counter()

    for row in rows:
        status = row.get("status", "unreviewed")
        priority = row.get("priority", "unclassified")
        reasons = []
        if status not in VALID_STATUSES:
            reasons.append("invalid_status")
        if priority not in VALID_PRIORITIES:
            reasons.append("invalid_priority")
        if status == "unreviewed":
            reasons.append("needs_manual_review")
        if row.get("archived"):
            reasons.append("github_archived")
        if row.get("disabled"):
            reasons.append("github_disabled")
        if row.get("missing"):
            reasons.append("repository_missing")
        activity = parse_date(row.get("pushedAt") or row.get("updatedAt"))
        if not activity:
            reasons.append("missing_activity_metadata")
        elif (today - activity).days > args.stale_days:
            reasons.append(f"inactive_over_{args.stale_days}_days")
        if row.get("external"):
            check_error = row.get("checkError", "")
            if check_error and check_error != "not_found":
                reasons.append("external_metadata_refresh_failed")
            elif not row.get("lastCheckedAt"):
                reasons.append("external_metadata_not_checked")


        status_counts[status] += 1
        for reason in reasons:
            reason_counts[reason] += 1
        if reasons:
            items.append({
                "name": row["name"],
                "url": row.get("url", ""),
                "category": row.get("category", ""),
                "external": bool(row.get("external")),
                "isFork": bool(row.get("isFork")),
                "forkedFrom": row.get("forkedFrom", ""),
                "status": status,
                "priority": priority,
                "duplicateGroup": row.get("duplicateGroup", ""),
                "pushedAt": row.get("pushedAt", ""),
                "updatedAt": row.get("updatedAt", ""),
                "archived": bool(row.get("archived")),
                "disabled": bool(row.get("disabled")),
                "missing": bool(row.get("missing")),
                "checkError": row.get("checkError", ""),
                "reasons": reasons,
            })

    output = {
        "generatedAt": today.isoformat(),
        "staleDays": args.stale_days,
        "summary": {
            "total": len(rows),
            "needsReview": len(items),
            "status": dict(sorted(status_counts.items())),
            "reasons": dict(sorted(reason_counts.items())),
        },
        "duplicateCandidates": {
            "assignedGroups": grouped(rows, "duplicateGroup"),
            "sameUrl": grouped(rows, "url"),
            "sameForkedFrom": grouped(rows, "forkedFrom"),
            "functional": functional,
            "unassignedFunctional": unassigned_functional,
        },
        "items": sorted(items, key=lambda row: (row["status"] != "unreviewed", row["category"], row["name"].lower())),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"审计完成: {len(rows)} 个仓库, {len(items)} 个待处理 -> {args.output}")
    functional_count = len(output["duplicateCandidates"]["functional"])
    unassigned_count = len(output["duplicateCandidates"]["unassignedFunctional"])
    print(f"重复候选: 已建组 {len(output['duplicateCandidates']['assignedGroups'])} 组, "
          f"URL {len(output['duplicateCandidates']['sameUrl'])} 组, "
          f"同上游 {len(output['duplicateCandidates']['sameForkedFrom'])} 组, "
          f"功能相似 {functional_count} 对, 仍待确认 {unassigned_count} 对")


if __name__ == "__main__":
    main()
