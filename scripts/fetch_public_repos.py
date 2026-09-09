#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""拉取 skychen2 仓库元数据(供 CI 每周自动刷新)。

无需手工认证:匿名 API 只返回公开仓库。
若环境存在 GH_TOKEN / GITHUB_TOKEN 则自动携带认证(限速更高,且能拿到真实 visibility)。

输出字段与 `gh repo list --json` 对齐,可直接传给 generate.py --public 使用。

用法:
    python3 scripts/fetch_public_repos.py [输出路径]
"""
import json
import os
import subprocess
import sys
import urllib.request

OWNER = "skychen2"


def auth_token():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def fetch():
    token = auth_token()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "repo-catalog-refresh"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    repos, page = [], 1
    while True:
        url = f"https://api.github.com/users/{OWNER}/repos?per_page=100&page={page}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.load(resp)
        if not batch:
            break
        for r in batch:
            pl = r.get("language")
            vis = (r.get("visibility") or ("PRIVATE" if r.get("private") else "PUBLIC")).upper()
            repos.append({
                "name": r["name"],
                "url": r["html_url"],
                "visibility": vis,
                "isFork": r["fork"],
                "description": r["description"] or "",
                "primaryLanguage": {"name": pl} if pl else None,
                "stargazerCount": r["stargazers_count"],
                "forkCount": r["forks_count"],
                "updatedAt": r["updated_at"],
                "pushedAt": r.get("pushed_at") or "",
                "archived": r.get("archived", False),
                "disabled": r.get("disabled", False),
                "license": (r.get("license") or {}).get("spdx_id") or "",
                "repositoryTopics": [{"name": t} for t in r.get("topics", [])],
            })
        if len(batch) < 100:
            break
        page += 1
    return repos


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "repos.json"
    data = fetch()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"拉取 {len(data)} 个公开仓库 -> {out}")
