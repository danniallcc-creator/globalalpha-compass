#!/usr/bin/env python3
"""
GlobalAlpha Compass - L2 动态洞察 Enrichment

对 data/categories/{l1}/*.json 的 466 个 L2 文件增量添加 dynamic_insight 字段。
数据源:
  - 本 L2 的 name_cn / name_en / keywords_en / hs_codes / export_data / compliance_summary
  - 父 L1 的 v2 数据（data/industry_trends_v2.json 中的 social/search/media/amazon）

用法:
  python3 scripts/enrich_l2_dynamic_insight.py              # 全量 enrichment
  python3 scripts/enrich_l2_dynamic_insight.py --dry-run    # 预览前 5 个 L2 输出
  python3 scripts/enrich_l2_dynamic_insight.py --sample 3   # 仅处理每个 L1 前 3 个 L2
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from lib.insight import synthesize_dynamic_insight  # noqa: E402

DATA_DIR = os.path.join(REPO_ROOT, 'data')
CATEGORIES_DIR = os.path.join(DATA_DIR, 'categories')
V2_FILE = os.path.join(DATA_DIR, 'industry_trends_v2.json')


def load_v2() -> Dict[str, Any]:
    if not os.path.exists(V2_FILE):
        print(f"[ERR] {V2_FILE} not found. Run build_industry_trends_v2.py first.")
        sys.exit(1)
    with open(V2_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def enrich_one(l2_path: str, l1_v2: Dict[str, Any]) -> Dict[str, Any]:
    """加载、enrichment、回写，返回写入的 dynamic_insight"""
    with open(l2_path, 'r', encoding='utf-8') as f:
        l2_json = json.load(f)

    insight = synthesize_dynamic_insight(l2_json, l1_v2, is_l1=False)

    # 仅在 insight 有变化时回写（避免无谓的 git diff）
    prev = l2_json.get('dynamic_insight')
    if prev and prev.get('trend_summary') == insight['trend_summary'] \
       and prev.get('reasons') == insight['reasons'] \
       and prev.get('signals') == insight['signals'] \
       and prev.get('product_profile') == insight['product_profile']:
        return insight  # 无变化，跳过写盘

    l2_json['dynamic_insight'] = insight
    # 保留原字段顺序：dynamic_insight 追加到末尾
    with open(l2_path, 'w', encoding='utf-8') as f:
        json.dump(l2_json, f, ensure_ascii=False, indent=2)
    return insight


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='仅预览前 5 个 L2 输出，不写盘')
    parser.add_argument('--sample', type=int, default=0, help='每个 L1 仅处理前 N 个 L2（0=全部）')
    parser.add_argument('--l1', type=str, default='', help='仅处理指定 L1（中文名）')
    args = parser.parse_args()

    print(f"[START] enrich_l2_dynamic_insight @ {time.strftime('%Y-%m-%d %H:%M:%S')}")
    v2 = load_v2()
    l1_categories = v2.get('categories', {})
    print(f"[INFO] L1 v2 categories: {len(l1_categories)}")

    if not os.path.isdir(CATEGORIES_DIR):
        print(f"[ERR] {CATEGORIES_DIR} not found")
        sys.exit(1)

    # L1 目录名可能是 L1 v2 键名的 slug 化版本（& → -、 、→ -），建立模糊映射
    def _slug(s: str) -> str:
        return s.replace('&', '-').replace('、', '-').replace(' ', '')

    v2_by_slug: Dict[str, Dict[str, Any]] = {}
    for k, v in l1_categories.items():
        v2_by_slug[_slug(k)] = v
        v2_by_slug[k] = v

    processed = 0
    written = 0
    dry_count = 0
    total_time_start = time.time()

    for l1_name in sorted(os.listdir(CATEGORIES_DIR)):
        if args.l1 and l1_name != args.l1:
            continue
        l1_dir = os.path.join(CATEGORIES_DIR, l1_name)
        if not os.path.isdir(l1_dir):
            continue
        l1_v2 = v2_by_slug.get(l1_name) or v2_by_slug.get(_slug(l1_name))
        if not l1_v2:
            print(f"[WARN] {l1_name} not in v2 data, using empty L1 fallback")
            l1_v2 = {}

        sample_n = 0
        l2_files = sorted(f for f in os.listdir(l1_dir) if f.endswith('.json'))
        for l2_file in l2_files:
            if args.sample and sample_n >= args.sample:
                break
            l2_path = os.path.join(l1_dir, l2_file)
            processed += 1
            sample_n += 1

            if args.dry_run:
                with open(l2_path, 'r', encoding='utf-8') as f:
                    l2_json = json.load(f)
                insight = synthesize_dynamic_insight(l2_json, l1_v2, is_l1=False)
                print(f"\n--- [{l1_name}/{l2_file[:-5]}] (dry-run) ---")
                print(f"  trend_summary: {insight['trend_summary']}")
                print(f"  domain: {insight['domain']}")
                print(f"  product_profile: {insight['product_profile']}")
                print(f"  reasons ({len(insight['reasons'])}):")
                for r in insight['reasons']:
                    print(f"    - {r}")
                print(f"  signals ({len(insight['signals'])}):")
                for s in insight['signals'][:4]:
                    print(f"    [{s['dim']}] {s.get('kw') or s.get('title')} | "
                          f"{s.get('platform') or s.get('source') or s.get('market')}")
                dry_count += 1
                if dry_count >= 5:
                    break
            else:
                try:
                    enrich_one(l2_path, l1_v2)
                    written += 1
                    if written % 50 == 0:
                        print(f"[PROGRESS] processed {written} L2 files")
                except Exception as e:
                    print(f"[ERR] {l1_name}/{l2_file}: {e}")

        if args.dry_run and dry_count >= 5:
            break

    elapsed = time.time() - total_time_start
    if args.dry_run:
        print(f"\n[DONE] dry-run previewed {dry_count} L2 in {elapsed:.1f}s")
    else:
        print(f"\n[DONE] processed {processed}, written {written}, in {elapsed:.1f}s")


if __name__ == '__main__':
    main()
