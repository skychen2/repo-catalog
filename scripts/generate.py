#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repo-catalog 生成器
用法:
    python scripts/generate.py [--public] [repos.json路径]
    --public           仅输出 PUBLIC 仓库(用于公开仓库内容,过滤私有仓库)
    不带 repos.json 时自动执行 gh repo list 拉取最新数据。
    若存在 scripts/curated.private.json(已被 gitignore),会自动合并,
    用于本地生成含私有仓库的完整目录。

生成内容:
    categories/*.md   按分类的仓库清单(中文说明 + 检索关键词)
    data/repos.json    机器可读完整元数据

设计原则:本库只服务 AI 检索。产物仅两种形态——机器可读 JSON(data/)与
分类语义文件(categories/);不为人类阅读生成冗余视图(如 INDEX 式全量索引)。
"""
import argparse
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CATEGORIES = [
    ("ai-llm-models", "AI 模型 / 微调 / 部署", "本地运行、微调训练、模型清单、部署工具"),
    ("ai-llm-prompts", "提示词 / 越狱 / 技巧", "prompt 合集、结构化提示词、系统提示词、越狱手册"),
    ("ai-llm-agents", "Agent / 自动化 / 工具调用", "Agent 框架、function calling、自动操作、工作流"),
    ("ai-llm-api", "AI 接口 / 代理 / 自部署 UI", "免费/中转 API、接口兼容代理、自部署聊天 UI"),
    ("ai-llm-tutorials", "LLM 教程 / 学习资源", "入门课程、源码解析、实战教程、资源清单"),
    ("network-proxy", "代理 / 科学上网 / Cloudflare", "机场、订阅汇聚、VLESS/Trojan、Cloudflare Workers、VPS 运维"),
    ("media", "视频 / AI 绘画 / 媒体", "视频生成与剪辑、超分插帧、AI 绘画、下载工具、音乐"),
    ("content-writing", "内容创作 / 写作 / 运营", "公众号排版、小红书运营、网文写作、内容工厂规范与素材"),
    ("dev-data-tools", "开发工具 / 效率 / 数据集", "开发者工具、安全、API 与数据集清单、自建小服务"),
    ("knowledge-books", "知识 / 教程 / 资料", "学习路线、书籍、语料库、神贴合集、生活指南"),
    ("personal-projects", "个人自建项目", "自建 / 私有项目,含个人知识库与工作流"),
]
CAT_KEYS = {c[0] for c in CATEGORIES}
LIFECYCLE_STATUSES = {"unreviewed", "active", "watch", "archived", "obsolete", "replaced"}
PRIORITIES = {"unclassified", "primary", "alternative", "reference"}


def lifecycle_fields(c):
    """读取人工维护的生命周期字段,旧条目使用保守默认值。"""
    if not isinstance(c, dict):
        c = {}
    alternatives = c.get("alternatives", [])
    if isinstance(alternatives, str):
        alternatives = [alternatives]
    return {
        "status": c.get("status", "unreviewed"),
        "priority": c.get("priority", "unclassified"),
        "lastReviewedAt": c.get("lastReviewedAt", ""),
        "duplicateGroup": c.get("duplicateGroup", ""),
        "alternatives": alternatives,
        "replacement": c.get("replacement", ""),
    }


def normalize_topics(value):
    """将 GitHub API 和 curated 中的 topics 统一为字符串数组。"""
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        return []
    topics = []
    for item in value:
        name = item.get("name", "") if isinstance(item, dict) else item
        name = str(name).strip()
        if name:
            topics.append(name)
    return topics


def extract_owner_from_url(url):
    """从 GitHub URL 提取 owner"""
    import re
    m = re.search(r'github\.com/([^/]+)/([^/?#\s]+)', url)
    return m.group(1) if m else ""


def load_repos(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    out = subprocess.run(
        ["gh", "repo", "list", "skychen2", "--limit", "2000",
         "--json", "name,visibility,description,primaryLanguage,isFork,isArchived,pushedAt,stargazerCount,forkCount,updatedAt,url,repositoryTopics,licenseInfo"],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def license_name(value):
    if isinstance(value, dict):
        return value.get("spdxId") or value.get("spdx_id") or ""
    return str(value or "")


def load_curated(public_only=False):
    curated = json.load(open(os.path.join(HERE, "curated.json"), encoding="utf-8"))
    if not public_only:
        # 私有仓库说明仅用于本地完整版;--public 时绝不合并,防止泄露
        private_path = os.path.join(HERE, "curated.private.json")
        if os.path.exists(private_path):
            curated.update(json.load(open(private_path, encoding="utf-8")))
    return curated


def curated_for_repo(curated, name):
    return curated.get(name) or curated.get(f"skychen2/{name}") or {}


def owner_from_key(key, entry):
    if isinstance(entry, dict) and entry.get("owner"):
        return entry["owner"]
    return key.split("/", 1)[0] if "/" in key else "skychen2"


def with_display(r):
    """组合展示用说明:fork 仓库自动补上游来源"""
    if r["isFork"] and r["forkedFrom"] and "fork 自" not in r["cn"]:
        r["display_cn"] = f"fork 自 {r['forkedFrom']}:" + r["cn"]
    else:
        r["display_cn"] = r["cn"]
    return r


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--public",
        action="store_true",
        dest="public_only",
        help="仅输出 PUBLIC 仓库,不合并本地私有说明",
    )
    parser.add_argument(
        "repos_path",
        nargs="?",
        help="预先拉取的仓库元数据 JSON 路径;省略时从 GitHub 拉取",
    )
    parsed = parser.parse_args()
    if parsed.repos_path and not os.path.isfile(parsed.repos_path):
        parser.error(f"仓库元数据文件不存在: {parsed.repos_path}")
    if not parsed.repos_path:
        try:
            gh_version = subprocess.run(["gh", "--version"], capture_output=True)
        except OSError:
            gh_version = None
        if gh_version is None or gh_version.returncode != 0:
            parser.error("未找到 GitHub CLI 'gh';请先安装,或提供 repos.json 路径")

    public_only = parsed.public_only
    path = parsed.repos_path
    repos = load_repos(path)
    if public_only:
        repos = [r for r in repos if r.get("visibility") == "PUBLIC"]
    curated = load_curated(public_only)
    by_name = {r["name"]: r for r in repos}

    missing = [r["name"] for r in repos if not curated_for_repo(curated, r["name"])]
    if missing:
        print("WARN: 以下仓库缺少 curated 说明,将退回上游 description:", missing)

    # 组装每条记录
    records = []
    for name, meta in sorted(by_name.items()):
        c = curated_for_repo(curated, name)
        lang = (meta.get("primaryLanguage") or {}).get("name") or "-"
        topics = normalize_topics(meta.get("repositoryTopics"))
        r = {
            "name": name,
            "url": meta.get("url", f"https://github.com/skychen2/{name}"),
            "visibility": meta.get("visibility", "PRIVATE"),
            "isFork": meta.get("isFork", False),
            "forkedFrom": c.get("forkedFrom", "") if isinstance(c, dict) else "",
            "language": lang,
            "stars": meta.get("stargazerCount", 0),
            "forks": meta.get("forkCount", 0),
            "updatedAt": (meta.get("updatedAt") or "")[:10],
            "pushedAt": (meta.get("pushedAt") or "")[:10],
            "archived": meta.get("isArchived", meta.get("archived", False)),
            "disabled": bool(meta.get("disabled", meta.get("isDisabled", False))),
            "license": license_name(meta.get("license") or meta.get("licenseInfo")),
            "topics": topics,
            "description": meta.get("description") or "",
            "category": c.get("category", "personal-projects") if isinstance(c, dict) else "personal-projects",
            "cn": c.get("cn", meta.get("description") or "(待补充)") if isinstance(c, dict) else (meta.get("description") or "(待补充)"),
            "keywords": c.get("keywords", []) if isinstance(c, dict) else [],
            **lifecycle_fields(c),
        }
        # 组合展示用说明:fork 仓库自动补上游来源
        records.append(with_display(r))

    # curated 中不在名下列表的条目:外部收藏(external=True,第三方仓库)
    # + 封禁/移除后从 GitHub 列表消失的仓库(missing,如 DMCA 封禁)——保留条目并标注不可访问
    for key, c in sorted(curated.items()):
        if not isinstance(c, dict):
            continue
        repo_name = key.rsplit("/", 1)[-1]
        if repo_name in by_name and not c.get("external"):
            continue
        name = key
        if public_only and c.get("visibility") == "PRIVATE":
            continue  # 防御:公开模式绝不输出私有条目
        if c.get("external"):
            url = c.get("url") or f"https://github.com/{owner_from_key(name, c)}/{repo_name}"
            owner = c.get("owner") or extract_owner_from_url(url) or owner_from_key(name, c)
            records.append(with_display({
                "name": name,
                "url": url,
                "owner": owner,
                "visibility": "PUBLIC",
                "isFork": bool(c.get("isFork", c.get("forkedFrom"))),
                "forkedFrom": c.get("forkedFrom", ""),
                "language": c.get("language", "-"),
                "stars": c.get("stars", 0),
                "forks": c.get("forks", 0),
                "updatedAt": c.get("updatedAt", ""),
                "pushedAt": c.get("pushedAt", ""),
                "archived": c.get("archived", False),
                "disabled": c.get("disabled", False),
                "license": c.get("license", ""),
                "lastCheckedAt": c.get("lastCheckedAt", ""),
                "starredAt": c.get("starredAt", ""),
                "topics": normalize_topics(c.get("topics", [])),
                "description": c.get("description", ""),
                "category": c.get("category", "dev-data-tools"),
                "cn": c.get("cn", "(待补充)"),
                "keywords": c.get("keywords", []),
                "external": True,
                "missing": c.get("missing", False),
                **({"checkError": c["checkError"]} if c.get("checkError") else {}),
                **lifecycle_fields(c),
            }))
            continue
        records.append(with_display({
            "name": name,
            "url": f"https://github.com/{owner_from_key(name, c)}/{repo_name}",
            "visibility": "PUBLIC",
            "isFork": bool(c.get("isFork", c.get("forkedFrom"))),
            "forkedFrom": c.get("forkedFrom", ""),
            "language": c.get("language", "-"),
            "license": license_name(c.get("license")),
            "stars": c.get("stars", 0),
            "forks": c.get("forks", 0),
            "updatedAt": c.get("updatedAt", ""),
            "pushedAt": c.get("pushedAt", ""),
            "archived": c.get("archived", False),
            "disabled": c.get("disabled", False),
            "topics": normalize_topics(c.get("topics", [])),
            "description": c.get("description", "") or "(已从 GitHub 列表移除/封禁,仓库不可访问)",
            "category": c.get("category", "dev-data-tools"),
            "cn": c.get("cn", "(待补充)"),
            "keywords": c.get("keywords", []),
            "missing": True,
            **lifecycle_fields(c),
        }))
    # 分类错误会造成 JSON 与分类 Markdown 不一致,必须在写文件前失败。
    invalid_categories = [r for r in records if r["category"] not in CAT_KEYS]
    if invalid_categories:
        details = ", ".join(f"{r['name']}={r['category']}" for r in invalid_categories)
        parser.error(f"存在非法分类: {details}")

    invalid_lifecycle = [
        r for r in records
        if r["status"] not in LIFECYCLE_STATUSES or r["priority"] not in PRIORITIES
    ]
    if invalid_lifecycle:
        details = ", ".join(
            f"{r['name']} status={r['status']} priority={r['priority']}"
            for r in invalid_lifecycle
        )
        parser.error(f"存在非法生命周期字段: {details}")

    # 分类错误和生命周期错误都必须在写文件前失败。

    os.makedirs(os.path.join(ROOT, "categories"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)

    # 清理不在当前分类列表中的旧分类文件(防止分类重命名/拆分后残留)
    for f in os.listdir(os.path.join(ROOT, "categories")):
        if f.endswith(".md") and f[:-3] not in CAT_KEYS:
            os.remove(os.path.join(ROOT, "categories", f))
            print(f"清理旧分类文件: {f}")

    # 1) categories/*.md
    for key, title, subtitle in CATEGORIES:
        items = [r for r in records if r["category"] == key]
        lines = [f"# {title}", "", f"> {subtitle}", ""]
        lines.append(f"共 {len(items)} 个仓库。")
        lines += ["", "| 仓库 | 说明 | 关键词 |", "|---|---|---|"]
        for r in sorted(items, key=lambda x: (-x["stars"], x["name"])):
            tag = "收藏🌐" if r.get("external") else ("⚠移除" if r.get("missing") else ("自建" if not r["isFork"] else "fork"))
            vis = "" if r["visibility"] == "PUBLIC" else " 🔒私有"
            name_cell = f"[{r['name']}]({r['url']}) {r['stars']}★ {tag}{vis}"
            kw = "、".join(r["keywords"]) or "-"
            safe_cn = r["display_cn"].replace("|", "\\|").replace("\n", " ")
            safe_kw = kw.replace("|", "\\|")
            lines.append(f"| {name_cell} | {safe_cn} | {safe_kw} |")
        with open(os.path.join(ROOT, "categories", f"{key}.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    # 2) data/repos.json
    with open(os.path.join(ROOT, "data", "repos.json"), "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    # 统计
    by_cat = {}
    for r in records:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1
    print("生成完成。共", len(records), "个仓库")
    for k, t, _ in CATEGORIES:
        print(f"  {t}: {by_cat.get(k, 0)}")


if __name__ == "__main__":
    main()
