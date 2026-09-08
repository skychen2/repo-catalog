#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据完整性验证脚本

用法:
    python3 scripts/validate.py

检查项:
    - curated.json 与 repos.json 的一致性
    - categories/*.md 文件与 CATEGORIES 定义的一致性
    - 所有仓库是否有中文说明、关键词、分类
    - fork 仓库的 forkedFrom 字段完整性
    - 分类分布统计
    - 外部收藏(external)标记正确性

退出码:
    0 - 所有检查通过
    1 - 发现问题（详见输出）
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 导入 CATEGORIES 定义（与 generate.py 保持一致）
sys.path.insert(0, HERE)
from generate import CATEGORIES

def error(msg):
    print(f"❌ {msg}")
    return False

def warn(msg):
    print(f"⚠️  {msg}")

def ok(msg):
    print(f"✓ {msg}")

def main():
    os.chdir(ROOT)
    issues = []
    
    print("=" * 60)
    print("repo-catalog 数据验证")
    print("=" * 60)
    
    # 加载数据
    try:
        repos = json.load(open('data/repos.json', encoding='utf-8'))
        curated = json.load(open('scripts/curated.json', encoding='utf-8'))
    except FileNotFoundError as e:
        print(f"❌ 文件未找到: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析错误: {e}")
        return 1
    
    repos_dict = {r['name']: r for r in repos}
    curated_repos = {k: v for k, v in curated.items() if k != '_comment'}
    
    print(f"\n📊 数据量: repos.json={len(repos)}, curated.json={len(curated_repos)}")
    
    # 1. 检查 curated 与 repos 一致性
    print("\n[1] 检查 curated.json 与 repos.json 一致性")
    in_curated_not_repos = set(curated_repos.keys()) - set(repos_dict.keys())
    if in_curated_not_repos:
        issues.append(f"curated 中有但 repos.json 缺失: {in_curated_not_repos}")
        error(f"curated 中有 {len(in_curated_not_repos)} 个仓库不在 repos.json 中")
    else:
        ok("curated 中的仓库都在 repos.json 中")
    
    # 名下仓库必须在 curated
    personal_repos = {r['name'] for r in repos if not r.get('external')}
    missing_curated = personal_repos - set(curated_repos.keys())
    if missing_curated:
        issues.append(f"名下仓库缺 curated 条目: {missing_curated}")
        error(f"{len(missing_curated)} 个名下仓库缺 curated 条目")
    else:
        ok(f"所有 {len(personal_repos)} 个名下仓库都在 curated 中")
    
    # external 仓库也应在 curated（根据 add_repo.py 逻辑）
    external_repos = {r['name'] for r in repos if r.get('external')}
    external_missing = external_repos - set(curated_repos.keys())
    if external_missing:
        warn(f"{len(external_missing)} 个 external 仓库缺 curated 条目")
        for name in list(external_missing)[:3]:
            print(f"    - {name}")
    else:
        ok(f"所有 {len(external_repos)} 个 external 仓库都在 curated 中")
    
    # 2. 检查分类定义与文件一致性
    print("\n[2] 检查分类定义与 categories/*.md 一致性")
    cat_files = {f.replace('.md', '') for f in os.listdir('categories') if f.endswith('.md')}
    cat_defined = {c[0] for c in CATEGORIES}
    
    missing_files = cat_defined - cat_files
    extra_files = cat_files - cat_defined
    
    if missing_files:
        issues.append(f"定义了但缺 .md 文件的分类: {missing_files}")
        error(f"缺少分类文件: {missing_files}")
    if extra_files:
        issues.append(f"有 .md 文件但未定义的分类: {extra_files}")
        error(f"多余分类文件: {extra_files}")
    if not missing_files and not extra_files:
        ok(f"分类定义与文件一致 ({len(cat_defined)} 个)")
    
    # repos.json 中的分类是否都已定义
    repo_cats = {r['category'] for r in repos if r.get('category')}
    undefined = repo_cats - cat_defined
    if undefined:
        issues.append(f"repos.json 中有未定义分类: {undefined}")
        error(f"未定义的分类: {undefined}")
        for cat in undefined:
            count = sum(1 for r in repos if r.get('category') == cat)
            print(f"    {cat}: {count} 个仓库")
    else:
        ok("repos.json 中所有分类都已定义")
    
    # 3. 检查数据完整性
    print("\n[3] 检查仓库数据完整性")
    no_cn = [r for r in repos if not r.get('cn')]
    no_keywords = [r for r in repos if not r.get('keywords')]
    no_category = [r for r in repos if not r.get('category')]
    pending_cn = [r for r in repos if '待补充中文说明' in r.get('cn', '')]
    
    if no_cn:
        issues.append(f"{len(no_cn)} 个仓库缺中文说明")
        error(f"{len(no_cn)} 个仓库缺中文说明")
        for r in no_cn[:3]:
            print(f"    - {r['name']}")
    else:
        ok("所有仓库都有中文说明")
    
    if no_keywords:
        issues.append(f"{len(no_keywords)} 个仓库缺关键词")
        error(f"{len(no_keywords)} 个仓库缺关键词")
        for r in no_keywords[:3]:
            print(f"    - {r['name']}")
    else:
        ok("所有仓库都有关键词")
    
    if no_category:
        issues.append(f"{len(no_category)} 个仓库未分类")
        error(f"{len(no_category)} 个仓库未分类")
        for r in no_category[:3]:
            print(f"    - {r['name']}")
    else:
        ok("所有仓库都已分类")
    
    if pending_cn:
        warn(f"{len(pending_cn)} 个仓库标注「待补充中文说明」")
        for r in pending_cn[:3]:
            print(f"    - {r['name']}: {r['cn'][:60]}")
    
    # 4. 检查 fork 仓库
    print("\n[4] 检查 fork 仓库的 forkedFrom 字段")
    fork_repos = [r for r in repos if r.get('isFork')]
    fork_no_source = [r for r in fork_repos if not r.get('forkedFrom')]
    
    if fork_no_source:
        warn(f"{len(fork_no_source)} 个 fork 仓库缺 forkedFrom 字段")
        for r in fork_no_source[:3]:
            print(f"    - {r['name']}")
    else:
        ok(f"所有 {len(fork_repos)} 个 fork 仓库都有 forkedFrom")
    
    # 5. 分类分布统计
    print("\n[5] 分类分布统计")
    from collections import Counter
    cat_count = Counter(r['category'] for r in repos if r.get('category'))
    print(f"{'分类':<30s} {'仓库数':>6s}")
    print("-" * 38)
    for cat, count in cat_count.most_common():
        print(f"{cat:<30s} {count:>6d}")
    
    # 6. external 标记一致性检查
    print("\n[6] 检查 external 标记一致性")
    external_count = len([r for r in repos if r.get('external')])
    # external 仓库的 owner 应该不是 skychen2
    external_wrong_owner = [r for r in repos if r.get('external') and r.get('owner') == 'skychen2']
    if external_wrong_owner:
        warn(f"{len(external_wrong_owner)} 个 external 仓库的 owner 是 skychen2（可能标记错误）")
        for r in external_wrong_owner[:3]:
            print(f"    - {r['name']}")
    
    # 名下仓库不应标记 external
    personal_marked_external = [r for r in repos if r.get('external') and not r.get('owner')]
    if personal_marked_external:
        issues.append(f"{len(personal_marked_external)} 个仓库标记 external 但无 owner 字段")
        error(f"{len(personal_marked_external)} 个 external 仓库缺 owner 字段")
    
    ok(f"external 标记: {external_count} 个外部收藏")
    
    # 总结
    print("\n" + "=" * 60)
    if issues:
        print(f"❌ 发现 {len(issues)} 个问题:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        return 1
    else:
        print("✅ 所有检查通过！数据完整且一致。")
        return 0

if __name__ == "__main__":
    sys.exit(main())
