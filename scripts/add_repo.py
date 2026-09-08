#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通过 GitHub 链接 / owner/name 新增仓库到目录。

用法:
    python3 scripts/add_repo.py <GitHub URL 或 owner/name> [--cn "中文功能说明"] \
        [--kw "关键词,逗号分隔"] [--cat 分类key]

行为:
    - 校验仓库存在(任意 owner 均可,但建议只收录 skychen2 名下的仓库;
      第三方仓库请先 fork/star,见 README「新增仓库」)
    - 已收录 → 提示跳过,不重复添加
    - 未收录 → 写入 scripts/curated.json,并自动补 forkedFrom(fork 仓库查上游)
    - --cn 缺省时用上游 description 占位,标注「待补充中文说明」

完成后仍需:
    python3 scripts/generate.py --public   # 重新生成公开产物
    git add -A && git commit && git push   # 推送
    python3 scripts/build_full_md.py       # 重建本地完整版,供索引进 KB
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

CATS = ["ai-llm-models", "ai-llm-prompts", "ai-llm-agents", "ai-llm-api", "ai-llm-tutorials",
        "network-proxy", "media", "content-writing", "dev-data-tools", "knowledge-books",
        "personal-projects"]


def gh(args):
    return subprocess.run(["gh"] + args, capture_output=True, text=True)


def parse_target(s):
    m = re.search(r"github\.com/([^/]+)/([^/?#\s]+)", s)
    if m:
        return m.group(1), m.group(2)
    parts = s.strip().strip("/").split("/")
    if len(parts) == 2:
        return parts[0], parts[1]
    return None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", help="GitHub URL 或 owner/name")
    ap.add_argument("--cn", default="", help="中文功能说明(缺省用上游 description 占位)")
    ap.add_argument("--kw", default="", help="检索关键词,逗号分隔")
    ap.add_argument("--cat", default="", help=f"分类 key,可选: {', '.join(CATS)}")
    args = ap.parse_args()
    
    # 检查 gh 命令是否可用
    if subprocess.run(["gh", "--version"], capture_output=True).returncode != 0:
        print("❌ 错误: 未找到 'gh' 命令（GitHub CLI）。")
        print("   安装方法: https://cli.github.com/")
        print("   或使用: brew install gh / apt install gh / scoop install gh")
        sys.exit(1)

    owner, name = parse_target(args.target)
    if not name:
        print("无法解析仓库名。请提供 GitHub URL(https://github.com/owner/repo)或 owner/repo 格式。")
        sys.exit(1)

    r = gh(["api", f"repos/{owner}/{name}",
            "--jq", "{name, full_name, description, fork, language, html_url, visibility, "
                     "stars: .stargazers_count, forks: .forks_count, updated_at}"])
    if r.returncode != 0:
        print(f"仓库不存在或不可访问: {owner}/{name} ({r.stderr.strip()[:200]})")
        sys.exit(1)
    meta = json.loads(r.stdout)

    curated_path = os.path.join(HERE, "curated.json")
    curated = json.load(open(curated_path, encoding="utf-8"))
    if name in curated:
        print(f"已在目录中: {name} → {str(curated[name].get('cn', ''))[:60]}")
        sys.exit(0)

    if args.cat and args.cat not in CATS:
        print(f"警告: 分类 {args.cat} 不在已知列表,仍将写入(生成时会校验)。")

    if args.cn:
        cn = args.cn
    elif meta.get("description"):
        cn = meta.get("description") + "(待补充中文说明)"
    else:
        cn = "(待补充中文说明)"
    entry = {
        "category": args.cat or "dev-data-tools",
        "cn": cn,
        "keywords": [k.strip() for k in args.kw.split(",") if k.strip()],
    }
    if meta.get("fork"):
        parent = gh(["api", f"repos/{owner}/{name}", "--jq", ".parent.full_name // \"\""]).stdout.strip()
        if parent:
            entry["forkedFrom"] = parent
    is_external = owner != "skychen2"
    is_private = str(meta.get("visibility") or "").upper() == "PRIVATE"
    if is_private:
        print(f"⚠ 该仓库是私有仓库,不应写入公开版 curated.json。"
              f"私有仓库说明请维护在 scripts/curated.private.json(本地文件,不会推送)。")
        sys.exit(1)
    if is_external:
        entry["external"] = True
        entry["owner"] = owner
        entry["url"] = meta.get("html_url")
        entry["language"] = meta.get("language") or "-"
        entry["stars"] = meta.get("stars", 0)
        entry["forks"] = meta.get("forks", 0)
        entry["updatedAt"] = (meta.get("updated_at") or "")[:10]

    curated[name] = entry
    json.dump(curated, open(curated_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    kind = "外部收藏" if is_external else "名下仓库"
    print(f"✓ 已新增({kind}): {name} ({meta.get('full_name')})")
    print(f"  说明: {entry['cn'][:80]}{'…' if len(entry['cn']) > 80 else ''}")
    print(f"  关键词: {entry['keywords']} | 分类: {entry['category']} | "
          f"fork: {meta.get('fork')} {('<- ' + entry['forkedFrom']) if 'forkedFrom' in entry else ''}")
    if is_external:
        print("  提示: 该仓库不属于 skychen2 名下,将作为「外部收藏」收录(公开版与本地完整版均可见)。")
    print("\n后续步骤:")
    print("  1) python3 scripts/generate.py --public   # 重新生成公开产物")
    print("  2) git add -A && git commit -m \"add repo: <name>\" && git push")
    print("  3) python3 scripts/build_full_md.py       # 重建本地完整版")
    print("  4) 用 ctx_index 把完整版重新索引进 context-mode 知识库")


if __name__ == "__main__":
    main()
