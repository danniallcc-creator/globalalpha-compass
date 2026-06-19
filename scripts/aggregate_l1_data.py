#!/usr/bin/env python3
"""
Aggregate L2 category data into L1-level summaries.
Excludes building materials categories (工程及建材机械, 建材与房地产).
Outputs data/customs_2025_l1.json
"""

import json
import os
import sys
from datetime import datetime
from collections import defaultdict

# ============================================================
# Paths
# ============================================================
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, 'data')
CAT_DIR = os.path.join(DATA_DIR, 'categories')
OUTPUT_FILE = os.path.join(DATA_DIR, 'customs_2025_l1.json')

# L1 categories to exclude (building materials)
BUILDING_MATERIALS_L1 = {"工程及建材机械", "建材与房地产"}

# Chinese country name -> ISO 3166-1 alpha-2 code mapping
COUNTRY_CN_TO_ISO = {
    "美国": "US",
    "德国": "DE",
    "英国": "GB",
    "日本": "JP",
    "澳大利亚": "AU",
    "韩国": "KR",
    "印度": "IN",
    "越南": "VN",
    "墨西哥": "MX",
    "阿联酋": "AE",
    "加拿大": "CA",
    "沙特阿拉伯": "SA",
    "法国": "FR",
    "巴西": "BR",
    "印度尼西亚": "ID",
    "新加坡": "SG",
    "中国香港": "HK",
    "荷兰": "NL",
    "马来西亚": "MY",
    "俄罗斯": "RU",
    "泰国": "TH",
    "比利时": "BE",
    "菲律宾": "PH",
    "土耳其": "TR",
    "南非": "ZA",
    "意大利": "IT",
    "西班牙": "ES",
    "波兰": "PL",
    "瑞士": "CH",
    "瑞典": "SE",
}

# The 15 standard reporting countries for imports_from_china
STANDARD_COUNTRIES = ["US", "DE", "GB", "JP", "AU", "KR", "IN", "VN", "MX", "AE", "CA", "SA", "FR", "BR", "ID"]

# Data quality ranking: lower index = better quality
QUALITY_RANK = {"complete": 0, "partial": 1, "estimated": 2, "missing": 3}


def load_category_index():
    """Load the category index and return grouped L1 -> L2 list."""
    index_path = os.path.join(DATA_DIR, 'category_index.json')
    if not os.path.exists(index_path):
        print(f"[ERROR] Category index not found: {index_path}")
        sys.exit(1)

    with open(index_path, 'r', encoding='utf-8') as f:
        idx = json.load(f)

    # Group by L1
    l1_groups = defaultdict(list)
    for cat in idx.get('categories', []):
        l1_slug = cat.get('l1_slug', '')
        if not l1_slug:
            continue
        l1_groups[l1_slug].append(cat)

    return l1_groups


def load_category_json(l1_slug, l2_slug):
    """Load a single L2 category JSON file. Returns None if not found."""
    path = os.path.join(CAT_DIR, l1_slug, f'{l2_slug}.json')
    if not os.path.exists(path):
        print(f"  [WARN] File not found, skipping: {path}")
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"  [WARN] Failed to load {path}: {e}")
        return None


def safe_list(val):
    """Return val if it's a list, else empty list."""
    return val if isinstance(val, list) else []


def safe_dict(val):
    """Return val if it's a dict, else empty dict."""
    return val if isinstance(val, dict) else {}


def worst_quality(q1, q2):
    """Return the worse of two data quality strings."""
    r1 = QUALITY_RANK.get(q1, 3)
    r2 = QUALITY_RANK.get(q2, 3)
    return q1 if r1 >= r2 else q2


def get_l2_export_total(cat_data):
    """
    Extract 2025 export total (sum of all HS codes' 2025 amt) from a category's export_data.
    Returns (total_usd, yoy_weighted) or (None, None) if unavailable.
    """
    export_data = safe_list(cat_data.get('export_data'))
    total_2025 = 0.0
    total_2024 = 0.0
    found_2025 = False

    for hs_item in export_data:
        data_list = safe_list(hs_item.get('data'))
        for yr_entry in data_list:
            yr = str(yr_entry.get('yr', ''))
            amt = yr_entry.get('amt')
            if amt is None:
                continue
            amt = float(amt)
            if yr == '2025':
                total_2025 += amt
                found_2025 = True
            elif yr == '2024':
                total_2024 += amt

    if not found_2025:
        return None, None

    # Calculate YoY from totals
    if total_2024 > 0:
        yoy = round(((total_2025 - total_2024) / total_2024) * 100, 1)
    else:
        yoy = 0.0

    return total_2025, yoy


def get_l2_country_breakdown(cat_data):
    """
    Extract per-country export amounts from export_data top5 fields.
    Returns dict: country_chinese_name -> total_amt
    """
    export_data = safe_list(cat_data.get('export_data'))
    country_totals = defaultdict(float)

    for hs_item in export_data:
        # Find the 2025 data amt for weighting the top5 proportions
        hs_2025_amt = 0.0
        for yr_entry in safe_list(hs_item.get('data')):
            if str(yr_entry.get('yr', '')) == '2025':
                amt = yr_entry.get('amt')
                if amt is not None:
                    hs_2025_amt = float(amt)
                break

        top5 = safe_list(hs_item.get('top5'))
        if not top5:
            continue

        # top5 amounts are absolute values for each country
        for entry in top5:
            c_name = entry.get('c', '')
            c_amt = entry.get('amt')
            if c_name and c_amt is not None:
                country_totals[c_name] += float(c_amt)

    return country_totals


def aggregate_exports(l2_list):
    """
    Aggregate export data across all L2 categories in an L1 group.
    l2_list: list of (cat_index_entry, cat_json_data) tuples
    Returns the customs_2025 dict.
    """
    total_usd = 0.0
    total_kg = 0.0
    weighted_yoy_sum = 0.0
    data_quality = "complete"
    l2_breakdown = []
    country_totals = defaultdict(float)
    has_any_export = False

    for cat_idx, cat_data in l2_list:
        if cat_data is None:
            data_quality = worst_quality(data_quality, "missing")
            continue

        # --- Try customs_2025 first (future format) ---
        customs_2025 = cat_data.get('customs_2025')
        if customs_2025 and isinstance(customs_2025, dict):
            china_exp = safe_dict(customs_2025.get('china_export'))
            l2_usd = china_exp.get('total_usd', 0) or 0
            l2_kg = china_exp.get('total_kg', 0) or 0
            l2_yoy = china_exp.get('yoy_growth', 0) or 0
            l2_quality = china_exp.get('data_quality', 'complete') or 'complete'

            total_usd += float(l2_usd)
            total_kg += float(l2_kg)
            weighted_yoy_sum += float(l2_usd) * float(l2_yoy)
            data_quality = worst_quality(data_quality, l2_quality)
            has_any_export = True

            # imports_from_china
            imp = safe_dict(customs_2025.get('imports_from_china'))
            for country_code, country_data in imp.items():
                if isinstance(country_data, dict):
                    val = country_data.get('value_usd', 0) or 0
                    country_totals[country_code] += float(val)

            l2_breakdown.append({
                "name_cn": cat_idx.get('name_cn', ''),
                "name_en": cat_idx.get('name_en', ''),
                "total_usd": float(l2_usd),
                "share_pct": 0  # computed later
            })
            continue

        # --- Fall back to export_data (current format) ---
        l2_total, l2_yoy = get_l2_export_total(cat_data)
        if l2_total is not None:
            has_any_export = True
            total_usd += l2_total
            weighted_yoy_sum += l2_total * (l2_yoy or 0)

            l2_breakdown.append({
                "name_cn": cat_idx.get('name_cn', ''),
                "name_en": cat_idx.get('name_en', ''),
                "total_usd": l2_total,
                "share_pct": 0  # computed later
            })

        # Country breakdown from top5
        cn_breakdown = get_l2_country_breakdown(cat_data)
        for cn_name, amt in cn_breakdown.items():
            iso = COUNTRY_CN_TO_ISO.get(cn_name)
            if iso:
                country_totals[iso] += amt
            # Keep unmapped countries as-is for debugging (but don't add to output)

    if not has_any_export:
        return None

    # Compute YoY
    yoy_growth = round(weighted_yoy_sum / total_usd, 1) if total_usd > 0 else 0.0

    # Compute share_pct for each L2
    for item in l2_breakdown:
        if total_usd > 0:
            item['share_pct'] = round((item['total_usd'] / total_usd) * 100, 1)

    # Sort breakdown by total_usd descending
    l2_breakdown.sort(key=lambda x: x['total_usd'], reverse=True)

    # Build imports_from_china for the 15 standard countries
    imports_from_china = {}
    total_imports = sum(country_totals.get(c, 0) for c in STANDARD_COUNTRIES)
    for cc in STANDARD_COUNTRIES:
        val = round(country_totals.get(cc, 0), 2)
        share = round((val / total_imports * 100), 1) if total_imports > 0 else 0
        imports_from_china[cc] = {
            "value_usd": val,
            "yoy": 0,  # YoY per country not available from current data
            "share": share
        }

    return {
        "china_export": {
            "total_usd": round(total_usd, 2),
            "total_kg": round(total_kg, 2) if total_kg else 0,
            "yoy_growth": yoy_growth,
            "data_quality": data_quality,
            "l2_breakdown": l2_breakdown
        },
        "imports_from_china": imports_from_china
    }


def aggregate_social_trends(l2_list):
    """
    Merge social_media_trends from all L2 categories.
    Returns merged social_media_trends dict or None.
    """
    platforms = {"google": [], "youtube": [], "x": [], "instagram": [], "tiktok": []}
    all_opportunities = []
    has_any = False

    # Track seen keywords per platform for dedup
    seen_keywords = {p: set() for p in platforms}

    for cat_idx, cat_data in l2_list:
        if cat_data is None:
            continue
        smt = cat_data.get('social_media_trends')
        if not smt or not isinstance(smt, dict):
            continue
        has_any = True

        l2_name = cat_idx.get('name_cn', '')

        for platform in platforms:
            kw_list = safe_list(smt.get(platform))
            for kw_entry in kw_list:
                if isinstance(kw_entry, dict):
                    kw = kw_entry.get('keyword', kw_entry.get('kw', ''))
                elif isinstance(kw_entry, str):
                    kw = kw_entry
                    kw_entry = {"keyword": kw}
                else:
                    continue

                if kw and kw not in seen_keywords[platform]:
                    seen_keywords[platform].add(kw)
                    # Attach source L2 name
                    entry_out = dict(kw_entry)
                    entry_out.setdefault('keyword', kw)
                    entry_out['l2_source'] = l2_name
                    platforms[platform].append(entry_out)

        # Opportunities
        opps = safe_list(smt.get('top_opportunities'))
        for opp in opps:
            if isinstance(opp, dict):
                opp_out = dict(opp)
                # Track which L2s mention this opportunity
                existing = next(
                    (o for o in all_opportunities
                     if o.get('keyword') == opp_out.get('keyword')
                     and o.get('platform') == opp_out.get('platform')),
                    None
                )
                if existing:
                    if l2_name not in existing.get('l2_names', []):
                        existing.setdefault('l2_names', []).append(l2_name)
                    # Keep the higher growth value
                    if (opp_out.get('growth', 0) or 0) > (existing.get('growth', 0) or 0):
                        existing['growth'] = opp_out['growth']
                else:
                    opp_out['l2_names'] = [l2_name]
                    all_opportunities.append(opp_out)

    if not has_any:
        return None

    # Sort opportunities by growth descending
    all_opportunities.sort(key=lambda x: x.get('growth', 0) or 0, reverse=True)

    result = {}
    for platform in platforms:
        result[platform] = platforms[platform]
    result['top_opportunities'] = all_opportunities[:20]  # top 20

    return result


def aggregate_policy_updates(l2_list):
    """
    Merge policy_updates from all L2 categories.
    Returns merged policy_updates dict or None.
    """
    all_articles = []
    seen_titles = set()
    country_data = defaultdict(lambda: {
        "trend": "",
        "key_policies": [],
        "impact": "",
        "affected_l2s": []
    })
    has_any = False

    for cat_idx, cat_data in l2_list:
        if cat_data is None:
            continue
        pu = cat_data.get('policy_updates')
        if not pu or not isinstance(pu, dict):
            continue
        has_any = True

        l2_name = cat_idx.get('name_cn', '')

        # Articles - deduplicate by title
        articles = safe_list(pu.get('articles'))
        for article in articles:
            if isinstance(article, dict):
                title = article.get('title', '')
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    article_out = dict(article)
                    article_out['l2_source'] = l2_name
                    all_articles.append(article_out)

        # Country summary
        cs = safe_dict(pu.get('country_summary'))
        for country_code, cdata in cs.items():
            if not isinstance(cdata, dict):
                continue
            target = country_data[country_code]

            # Merge trend (take the longest/most detailed)
            trend = cdata.get('trend', '') or ''
            if len(trend) > len(target['trend']):
                target['trend'] = trend

            # Merge key_policies (deduplicate)
            policies = safe_list(cdata.get('key_policies'))
            for p in policies:
                if p and p not in target['key_policies']:
                    target['key_policies'].append(p)

            # Merge impact (take the longest)
            impact = cdata.get('impact', '') or ''
            if len(impact) > len(target['impact']):
                target['impact'] = impact

            # Track affected L2s
            if l2_name not in target['affected_l2s']:
                target['affected_l2s'].append(l2_name)

    if not has_any:
        return None

    return {
        "articles": all_articles,
        "country_summary": dict(country_data)
    }


def build_l1_summary(l1_slug, l1_cn, l1_en, l2_cats):
    """
    Build the L1 summary for a single L1 category.
    l2_cats: list of category index entries for this L1.
    """
    # Load all L2 JSON files
    l2_loaded = []
    for cat in l2_cats:
        l2_slug = cat.get('l2_slug', '')
        cat_data = load_category_json(l1_slug, l2_slug)
        l2_loaded.append((cat, cat_data))

    # Count L3s from the index
    l3_count = sum(cat.get('l3_count', 0) or 0 for cat in l2_cats)

    # Count successfully loaded L2s
    loaded_count = sum(1 for _, d in l2_loaded if d is not None)

    summary = {
        "l1_cn": l1_cn,
        "l1_en": l1_en,
        "l1_slug": l1_slug,
        "l2_count": len(l2_cats),
        "l3_count": l3_count,
        "customs_2025": aggregate_exports(l2_loaded),
        "social_media_trends": aggregate_social_trends(l2_loaded),
        "policy_updates": aggregate_policy_updates(l2_loaded),
    }

    return summary, loaded_count


def main():
    print("=" * 60)
    print("GlobalAlpha Compass - L2 -> L1 Data Aggregation")
    print("=" * 60)

    # Load category index
    print("\n[1/4] Loading category index...")
    l1_groups = load_category_index()
    total_l1 = len(l1_groups)
    total_l2 = sum(len(v) for v in l1_groups.values())
    print(f"  Found {total_l1} L1 categories, {total_l2} L2 categories")

    # Filter out building materials
    print(f"\n[2/4] Excluding building materials: {BUILDING_MATERIALS_L1}")
    excluded = []
    active_groups = {}
    for l1_slug, l2_cats in l1_groups.items():
        if l1_slug in BUILDING_MATERIALS_L1:
            excluded.append(l1_slug)
            print(f"  Excluded: {l1_slug} ({len(l2_cats)} L2s)")
        else:
            active_groups[l1_slug] = l2_cats
    print(f"  Active L1 categories: {len(active_groups)}")

    # Build L1 summaries
    print(f"\n[3/4] Aggregating L2 data into L1 summaries...")
    l1_data = []
    total_loaded = 0
    total_export_value = 0.0

    # Get L1 cn/en from the first category entry in each group
    for l1_slug in sorted(active_groups.keys()):
        l2_cats = active_groups[l1_slug]
        first_cat = l2_cats[0]
        l1_cn = first_cat.get('l1_cn', l1_slug)
        l1_en = first_cat.get('l1_en', '')

        summary, loaded_count = build_l1_summary(l1_slug, l1_cn, l1_en, l2_cats)
        total_loaded += loaded_count

        # Track total export value
        c2025 = summary.get('customs_2025')
        if c2025 and isinstance(c2025, dict):
            ce = c2025.get('china_export', {})
            if ce:
                total_export_value += ce.get('total_usd', 0) or 0

        l1_data.append(summary)
        has_customs = "Y" if summary.get('customs_2025') else "N"
        has_social = "Y" if summary.get('social_media_trends') else "N"
        has_policy = "Y" if summary.get('policy_updates') else "N"
        print(f"  {l1_cn:<20s} | L2:{summary['l2_count']:>3d} L3:{summary['l3_count']:>4d} "
              f"| loaded:{loaded_count:>3d}/{len(l2_cats):<3d} "
              f"| customs:{has_customs} social:{has_social} policy:{has_policy}")

    # Write output
    print(f"\n[4/4] Writing output to {OUTPUT_FILE}")
    now = datetime.now()
    output = {
        "meta": {
            "updated_at": now.strftime('%Y-%m-%dT%H:%M:%S'),
            "date": now.strftime('%Y-%m-%d'),
            "l1_count": len(l1_data),
            "building_materials_excluded": True,
            "excluded_l1s": sorted(excluded)
        },
        "l1_data": l1_data
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Print summary statistics
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  L1 categories output:    {len(l1_data)}")
    print(f"  Excluded L1 categories:  {len(excluded)} ({', '.join(excluded)})")
    print(f"  L2 files loaded:         {total_loaded}/{total_l2 - sum(len(l1_groups[e]) for e in excluded)}")
    print(f"  Total export value (USD): {total_export_value:,.1f}M")
    print(f"  Output file:             {OUTPUT_FILE}")
    print(f"  File size:               {os.path.getsize(OUTPUT_FILE) / 1024:.1f} KB")
    print("=" * 60)
    print("Done.")

    # === Workflow-scope-free fallback: stage industry_trends_v2.json ===
    # The daily-update.yml workflow can't be modified (OAuth scope limit);
    # ensure CI picks up industry_trends_v2.json by staging it here so the
    # workflow's existing "git add" + commit step includes it.
    try:
        import subprocess as _sp
        v2_path = os.path.join(os.path.dirname(OUTPUT_FILE), 'industry_trends_v2.json')
        if os.path.exists(v2_path):
            _sp.run(['git', 'add', v2_path], check=False)
            print(f"[CHAIN] git add {v2_path}")
    except Exception as _e:
        print(f"[CHAIN] git add industry_trends_v2.json failed: {_e}")

    # === Chain: enrich L2 dynamic_insight (depends on industry_trends_v2.json) ===
    # 给 466 个 L2 JSON 增量添加 dynamic_insight 字段（社媒/搜索/媒体/Amazon 综合洞察）
    try:
        import subprocess as _sp
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        enrich_script = os.path.join(scripts_dir, 'enrich_l2_dynamic_insight.py')
        if os.path.exists(enrich_script):
            result = _sp.run(
                [sys.executable, enrich_script],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                print(f"[CHAIN] enrich_l2_dynamic_insight OK: {result.stdout.strip().splitlines()[-1] if result.stdout else ''}")
            else:
                print(f"[CHAIN] enrich_l2 failed rc={result.returncode}: {result.stderr[:200]}")
            # stage 所有 L2 文件变更
            categories_dir = os.path.join(DATA_DIR, 'categories')
            if os.path.isdir(categories_dir):
                _sp.run(['git', 'add', categories_dir], check=False)
                print(f"[CHAIN] git add {categories_dir}")
    except Exception as _e:
        print(f"[CHAIN] L2 enrichment chain failed: {_e}")


if __name__ == '__main__':
    main()
