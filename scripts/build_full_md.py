#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成本地完整版目录 Markdown(含私有仓库),供索引进 context-mode 知识库。

用法:
    python3 scripts/build_full_md.py [输出路径]

生成后由 AI 执行:
    ctx_index(path=<输出路径>, source="repo-catalog-full (skychen2 全部仓库,含私有)")
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

CATS = [
    ("ai-llm-models", "AI 模型 / 微调 / 部署"),
    ("ai-llm-prompts", "提示词 / 越狱 / 技巧"),
    ("ai-llm-agents", "Agent / 自动化 / 工具调用"),
    ("ai-llm-api", "AI 接口 / 代理 / 自部署 UI"),
    ("ai-llm-tutorials", "LLM 教程 / 学习资源"),
    ("network-proxy", "代理 / 科学上网 / Cloudflare"),
    ("media", "视频 / AI 绘画 / 媒体"),
    ("content-writing", "内容创作 / 写作 / 运营"),
    ("dev-data-tools", "开发工具 / 效率 / 数据集"),
    ("knowledge-books", "知识 / 教程 / 资料"),
    ("personal-projects", "个人自建项目"),
]


def load_repos():
    out = subprocess.run(
        ["gh", "repo", "list", "skychen2", "--limit", "2000",
         "--json", "name,visibility,description,primaryLanguage,isFork,stargazerCount,forkCount,updatedAt,url,repositoryTopics"],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/repo-catalog-full.md"
    curated = {}
    for f in ["curated.json", "curated.private.json"]:
        p = os.path.join(HERE, f)
        if os.path.exists(p):
            curated.update(json.load(open(p, encoding="utf-8")))

    records = []
    for m in load_repos():
        c = curated.get(m["name"], {})
        cn = c.get("cn") or m.get("description") or "(待补充)"
        fk = c.get("forkedFrom", "")
        if m.get("isFork") and fk and "fork 自" not in cn:
            cn = f"fork 自 {fk}:" + cn
        records.append({
            "name": m["name"],
            "url": m["url"],
            "visibility": m["visibility"],
            "isFork": m.get("isFork", False),
            "forkedFrom": fk,
            "language": (m.get("primaryLanguage") or {}).get("name") or "-",
            "stars": m.get("stargazerCount", 0),
            "updatedAt": (m.get("updatedAt") or "")[:10],
            "category": c.get("category", "personal-projects"),
            "cn": cn,
            "keywords": "、".join(c.get("keywords", []) or []),
        })

    # 外部收藏条目(curated 中 external=True 的第三方仓库)
    by_name = {r["name"] for r in records}
    for name, c in sorted(curated.items()):
        if not isinstance(c, dict) or not c.get("external") or name in by_name:
            continue
        records.append({
            "name": name,
            "url": c.get("url") or f"https://github.com/{c.get('owner', '')}/{name}",
            "visibility": "PUBLIC",
            "isFork": False,
            "forkedFrom": c.get("forkedFrom", ""),
            "language": c.get("language", "-"),
            "stars": c.get("stars", 0),
            "updatedAt": c.get("updatedAt", ""),
            "category": c.get("category", "dev-data-tools"),
            "cn": c.get("cn", "(待补充)"),
            "keywords": "、".join(c.get("keywords", []) or []),
            "external": True,
        })

    md = ["# skychen2 仓库完整目录(含私有仓库)", "",
          "> AI 检索用:按分类检索或关键词全文搜索。公开仓库亦收录,含私有仓库条目(标注 🔒)。", ""]
    for key, title in CATS:
        items = [r for r in records if r["category"] == key]
        if not items:
            continue
        md += [f"## {title} ({key})", ""]
        for r in sorted(items, key=lambda x: -x["stars"]):
            lock = " 🔒" if r["visibility"] == "PRIVATE" else ""
            tag = "外部收藏" if r.get("external") else ("fork" if r["isFork"] else "自建")
            md += [f"### {r['name']}{lock}",
                   f"- 分类: {key}",
                   f"- 说明: {r['cn']}",
                   f"- 关键词: {r['keywords'] or '-'}",
                   f"- 属性: {tag}"
                   f"{(' (fork 自 ' + r['forkedFrom'] + ')') if r['forkedFrom'] else ''}"
                   f" | {r['language']} | {r['stars']}★ | 更新 {r['updatedAt']}",
                   f"- URL: {r['url']}", ""]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    n = len(records)
    priv = sum(1 for r in records if r["visibility"] == "PRIVATE")
    print(f"完整版 {n} 仓库(私有 {priv}) -> {out_path}")
    print('下一步: ctx_index(path=上述路径, source="repo-catalog-full (skychen2 全部仓库,含私有)")')


if __name__ == "__main__":
    main()
