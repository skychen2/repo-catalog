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
    INDEX.md           全量一行式索引
    data/repos.json    机器可读完整元数据
"""
import json
import os
import subprocess
import sys

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


def load_repos(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    out = subprocess.run(
        ["gh", "repo", "list", "skychen2", "--limit", "2000",
         "--json", "name,visibility,description,primaryLanguage,isFork,stargazerCount,forkCount,updatedAt,url,repositoryTopics"],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def load_curated():
    curated = json.load(open(os.path.join(HERE, "curated.json"), encoding="utf-8"))
    private_path = os.path.join(HERE, "curated.private.json")
    if os.path.exists(private_path):
        curated.update(json.load(open(private_path, encoding="utf-8")))
    return curated


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    public_only = "--public" in sys.argv[1:]
    path = args[0] if args else None
    repos = load_repos(path)
    if public_only:
        repos = [r for r in repos if r.get("visibility") == "PUBLIC"]
    curated = load_curated()
    by_name = {r["name"]: r for r in repos}

    missing = [r["name"] for r in repos if r["name"] not in curated]
    if missing:
        print("WARN: 以下仓库缺少 curated 说明,将退回上游 description:", missing)

    # 组装每条记录
    records = []
    for name, meta in sorted(by_name.items()):
        c = curated.get(name, {})
        lang = (meta.get("primaryLanguage") or {}).get("name") or "-"
        topics = ", ".join(t["name"] for t in (meta.get("repositoryTopics") or []))
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
            "topics": topics,
            "description": meta.get("description") or "",
            "category": c.get("category", "personal-projects") if isinstance(c, dict) else "personal-projects",
            "cn": c.get("cn", meta.get("description") or "(待补充)") if isinstance(c, dict) else (meta.get("description") or "(待补充)"),
            "keywords": c.get("keywords", []) if isinstance(c, dict) else [],
        }
        # 组合展示用说明:fork 仓库自动补上游来源
        if r["isFork"] and r["forkedFrom"] and "fork 自" not in r["cn"]:
            r["display_cn"] = f"fork 自 {r['forkedFrom']}:" + r["cn"]
        else:
            r["display_cn"] = r["cn"]
        records.append(r)
    # 校验分类
    for r in records:
        if r["category"] not in CAT_KEYS:
            print(f"WARN: {r['name']} 分类 {r['category']} 非法,归入 personal-projects")

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
            flag = "自建" if not r["isFork"] else "fork"
            vis = "" if r["visibility"] == "PUBLIC" else " 🔒私有"
            name_cell = f"[{r['name']}]({r['url']}) {r['stars']}★ {flag}{vis}"
            kw = "、".join(r["keywords"]) or "-"
            safe_cn = r["display_cn"].replace("|", "\\|").replace("\n", " ")
            safe_kw = kw.replace("|", "\\|")
            lines.append(f"| {name_cell} | {safe_cn} | {safe_kw} |")
        with open(os.path.join(ROOT, "categories", f"{key}.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    # 2) INDEX.md
    def trunc(s, n=90):
        return s if len(s) <= n else s[:n].rstrip("，。、；:：,.; ") + "…"

    lines = ["# 仓库索引 INDEX", "", "检索方法:按分类文件检索,或用关键词全文搜索。",
             "", "| 仓库 | 分类 | 一句话说明 | 属性 |", "|---|---|---|---|"]
    cat_title = {k: t for k, t, _ in CATEGORIES}
    for r in sorted(records, key=lambda x: (x["category"], -x["stars"])):
        attr = ("自建" if not r["isFork"] else "fork") + ("" if r["visibility"] == "PUBLIC" else "/🔒")
        cn = trunc(r["display_cn"].replace("|", "\\|"))
        lines.append(f"| [{r['name']}]({r['url']}) | {cat_title.get(r['category'], r['category'])} | {cn} | {attr} |")
    with open(os.path.join(ROOT, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # 3) data/repos.json
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
