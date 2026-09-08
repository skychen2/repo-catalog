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

    owner, name = parse_target(args.target)
    if not name:
        print("无法解析仓库名。请提供 GitHub URL(https://github.com/owner/repo)或 owner/repo 格式。")
        sys.exit(1)

    r = gh(["api", f"repos/{owner}/{name}",
            "--jq", "{name, full_name, description, fork, language, html_url, visibility}"])
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

    curated[name] = entry
    json.dump(curated, open(curated_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✓ 已新增: {name} ({meta.get('full_name')})")
    print(f"  说明: {entry['cn'][:80]}{'…' if len(entry['cn']) > 80 else ''}")
    print(f"  关键词: {entry['keywords']} | 分类: {entry['category']} | "
          f"fork: {meta.get('fork')} {('<- ' + entry['forkedFrom']) if 'forkedFrom' in entry else ''}")
    print("\n后续步骤:")
    print("  1) python3 scripts/generate.py --public   # 重新生成公开产物")
    print("  2) git add -A && git commit -m \"add repo: <name>\" && git push")
    print("  3) python3 scripts/build_full_md.py       # 重建本地完整版")
    print("  4) 用 ctx_index 把完整版重新索引进 context-mode 知识库")


if __name__ == "__main__":
    main()
