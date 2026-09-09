#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""刷新 curated.json 中外部收藏的 GitHub 元数据。

用法:
    python3 scripts/refresh_external_repos.py
    python3 scripts/refresh_external_repos.py --dry-run
    python3 scripts/refresh_external_repos.py --workers 4

只更新 GitHub 自动字段,不会覆盖中文说明、分类、关键词和人工审核字段。
"""
import argparse
import concurrent.futures
import datetime as dt
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CURATED_PATH = os.path.join(HERE, "curated.json")


def auth_token():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def fetch_repo(name, entry, headers):
    repo_name = name.rsplit("/", 1)[-1]
    owner = entry.get("owner", "")
    if not owner and "/" in name:
        owner = name.split("/", 1)[0]
    if not owner:
        url = entry.get("url", "")
        parts = url.rstrip("/").split("/github.com/")
        if len(parts) == 2:
            owner = parts[1].split("/")[0]
    if not owner:
        return name, None, "missing_owner"

    url = f"https://api.github.com/repos/{owner}/{repo_name}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return name, json.load(response), ""
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return name, None, "not_found"
        return name, None, f"http_{error.code}"
    except (urllib.error.URLError, TimeoutError) as error:
        return name, None, f"network_error:{type(error).__name__}"


def metadata(meta, checked_at):
    license_info = meta.get("license") or {}
    result = {
        "owner": (meta.get("full_name") or "").split("/", 1)[0],
        "url": meta.get("html_url", ""),
        "language": meta.get("language") or "-",
        "stars": meta.get("stargazers_count", 0),
        "forks": meta.get("forks_count", 0),
        "updatedAt": (meta.get("updated_at") or "")[:10],
        "pushedAt": (meta.get("pushed_at") or "")[:10],
        "archived": bool(meta.get("archived", False)),
        "disabled": bool(meta.get("disabled", False)),
        "license": license_info.get("spdx_id") or "",
        "topics": meta.get("topics", []),
        "isFork": bool(meta.get("fork", False)),
        "description": meta.get("description") or "",
        "lastCheckedAt": checked_at,
    }
    if meta.get("fork") and (meta.get("parent") or {}).get("full_name"):
        result["detectedForkedFrom"] = meta["parent"]["full_name"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=8, help="并发请求数,范围 1-16")
    parser.add_argument("--dry-run", action="store_true", help="只检查,不写回 curated.json")
    args = parser.parse_args()
    workers = max(1, min(args.workers, 16))

    with open(CURATED_PATH, encoding="utf-8") as file:
        curated = json.load(file)
    targets = [(name, entry) for name, entry in curated.items()
               if isinstance(entry, dict) and entry.get("external")]
    token = auth_token()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "repo-catalog-refresh",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    checked_at = dt.datetime.now(dt.timezone.utc).date().isoformat()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(fetch_repo, name, entry, headers)
                   for name, entry in targets]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    updated = 0
    missing = 0
    failed = 0
    for name, meta, error in sorted(results):
        entry = curated[name]
        if meta:
            entry.update(metadata(meta, checked_at))
            detected_parent = entry.pop("detectedForkedFrom", "")
            if detected_parent and not entry.get("forkedFrom"):
                entry["forkedFrom"] = detected_parent
            entry.pop("missing", None)
            entry.pop("checkError", None)
            updated += 1
        elif error == "not_found":
            entry["missing"] = True
            entry["checkError"] = error
            entry["lastCheckedAt"] = checked_at
            missing += 1
        else:
            entry["checkError"] = error
            failed += 1


    if not args.dry_run:
        fd, temp_path = tempfile.mkstemp(prefix="curated-", suffix=".json", dir=HERE)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(curated, file, ensure_ascii=False, indent=2)
                file.write("\n")
            os.replace(temp_path, CURATED_PATH)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    action = "检查" if args.dry_run else "刷新"
    print(f"{action}外部仓库 {len(targets)} 个: 成功 {updated}, 不可访问 {missing}, 失败 {failed}")
    if failed:
        print("失败项保留原有元数据,请稍后重试;可查看 curated.json 中的 checkError。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
