#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发现当前账号 star 的第三方仓库并加入 curated.json。

用法:
    python3 scripts/fetch_starred_repos.py
    python3 scripts/fetch_starred_repos.py --dry-run

新增条目只写入 GitHub 自动元数据和保守的人工默认值,不会覆盖已有说明、分类、关键词或生命周期判断。
取消 star 不会自动删除目录条目。
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CURATED_PATH = os.path.join(HERE, "curated.json")
OWNER = "skychen2"


def auth_token():
    token = (
        os.environ.get("STARRED_REPOS_TOKEN")
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
    )
    if token:
        return token
    try:
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def repo_identity(owner, name):
    return f"{owner.strip().lower()}/{name.strip().removesuffix('.git').lower()}"


def key_identity(key, entry):
    if isinstance(entry, dict) and entry.get("owner"):
        return repo_identity(entry["owner"], key.rsplit("/", 1)[-1])
    if "/" in key:
        owner, name = key.split("/", 1)
        return repo_identity(owner, name)
    return repo_identity(OWNER, key)


def find_entry(curated, identity):
    for key, entry in curated.items():
        if isinstance(entry, dict) and key_identity(key, entry) == identity:
            return key, entry
    return None, None


def fetch_starred(headers):
    starred = []
    page = 1
    while True:
        url = f"https://api.github.com/user/starred?per_page=100&page={page}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                batch = json.load(response)
        except urllib.error.HTTPError as error:
            if error.code in {401, 403}:
                raise RuntimeError(
                    "无法读取 Star 列表,请提供有权读取用户 starred repositories 的 token"
                ) from error
            raise RuntimeError(f"GitHub API 请求失败: HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise RuntimeError(f"GitHub API 网络请求失败: {type(error).__name__}") from error

        if not batch:
            break
        for item in batch:
            repo = item.get("repo", item)
            if repo.get("full_name") and repo.get("name"):
                starred.append({
                    "repo": repo,
                    "starredAt": item.get("starred_at", ""),
                })
        if len(batch) < 100:
            break
        page += 1
    return starred


def license_name(value):
    if isinstance(value, dict):
        return value.get("spdx_id") or value.get("spdxId") or ""
    return str(value or "")


def automatic_fields(repo, starred_at, checked_at):
    full_name = repo.get("full_name", "")
    owner = full_name.split("/", 1)[0] if "/" in full_name else ""
    parent = repo.get("parent") or {}
    fields = {
        "external": True,
        "owner": owner,
        "url": repo.get("html_url", ""),
        "language": repo.get("language") or "-",
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "updatedAt": (repo.get("updated_at") or "")[:10],
        "pushedAt": (repo.get("pushed_at") or "")[:10],
        "archived": bool(repo.get("archived", False)),
        "disabled": bool(repo.get("disabled", False)),
        "license": license_name(repo.get("license")),
        "topics": repo.get("topics", []),
        "description": repo.get("description") or "",
        "lastCheckedAt": checked_at,
    }
    if starred_at:
        fields["starredAt"] = starred_at
    if repo.get("fork") and parent.get("full_name"):
        fields["forkedFrom"] = parent["full_name"]
        fields["isFork"] = True
    else:
        fields["isFork"] = False
    return fields


def new_entry(repo, starred_at, checked_at):
    description = repo.get("description") or ""
    return {
        "category": "dev-data-tools",
        "cn": description + "(待补充中文说明)" if description else "(待补充中文说明)",
        "keywords": [],
        "status": "unreviewed",
        "priority": "unclassified",
        "lastReviewedAt": "",
        "duplicateGroup": "",
        "alternatives": [],
        "replacement": "",
        **automatic_fields(repo, starred_at, checked_at),
    }


def merge_starred(curated, starred, checked_at):
    stats = {"discovered": 0, "added": 0, "updated": 0, "migrated": 0, "owned": 0}
    for item in starred:
        repo = item["repo"]
        full_name = repo.get("full_name", "")
        if "/" not in full_name:
            continue
        owner, name = full_name.split("/", 1)
        if owner.lower() == OWNER.lower():
            stats["owned"] += 1
            continue
        stats["discovered"] += 1
        identity = repo_identity(owner, name)
        starred_at = item.get("starredAt", "")
        existing_key, existing = find_entry(curated, identity)
        if existing is not None:
            existing.update(automatic_fields(repo, starred_at, checked_at))
            existing.pop("missing", None)
            existing.pop("checkError", None)
            stats["updated"] += 1
            continue

        conflict_key = next(
            (
                key for key, entry in curated.items()
                if isinstance(entry, dict)
                and key.rsplit("/", 1)[-1].lower() == name.lower()
            ),
            None,
        )
        if conflict_key is not None:
            conflict_entry = curated.pop(conflict_key)
            conflict_identity = key_identity(conflict_key, conflict_entry)
            curated[conflict_identity] = conflict_entry
            stats["migrated"] += 1
        storage_key = identity if conflict_key is not None else name
        curated[storage_key] = new_entry(repo, starred_at, checked_at)
        stats["added"] += 1
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只检查,不写回 curated.json")
    args = parser.parse_args()
    token = auth_token()
    if not token:
        parser.error("读取 Star 列表需要 STARRED_REPOS_TOKEN 或已登录的 gh")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "repo-catalog-star-discovery",
        "Authorization": f"Bearer {token}",
    }
    try:
        starred = fetch_starred(headers)
    except RuntimeError as error:
        parser.error(str(error))

    with open(CURATED_PATH, encoding="utf-8") as file:
        curated = json.load(file)
    checked_at = dt.datetime.now(dt.timezone.utc).date().isoformat()
    stats = merge_starred(curated, starred, checked_at)

    if not args.dry_run:
        fd, temp_path = tempfile.mkstemp(prefix="curated-starred-", suffix=".json", dir=HERE)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(curated, file, ensure_ascii=False, indent=2)
                file.write("\n")
            os.replace(temp_path, CURATED_PATH)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    action = "检查" if args.dry_run else "发现"
    print(
        f"{action} Star 仓库 {stats['discovered']} 个: "
        f"新增 {stats['added']}, 更新 {stats['updated']}, "
        f"主键迁移 {stats['migrated']}, 名下仓库跳过 {stats['owned']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
