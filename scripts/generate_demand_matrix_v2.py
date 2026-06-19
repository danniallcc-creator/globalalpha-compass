#!/usr/bin/env python3
"""
Generate demand_matrix_v2.json for GlobalAlpha Compass website.

Reads taxonomy.json, category_index.json, and per-category detail files
to produce a comprehensive demand analysis matrix with regional demand,
china export stats, and keyword data for every L2 category.
"""

import json
import os
import sys
from datetime import date
from collections import defaultdict

# ──────────────────────────── paths ────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data"))
CATEGORIES_DIR = os.path.join(DATA_DIR, "categories")
TAXONOMY_FILE = os.path.join(DATA_DIR, "taxonomy.json")
CATEGORY_INDEX_FILE = os.path.join(DATA_DIR, "category_index.json")
COUNTRY_CORE_DEMANDS_FILE = os.path.join(DATA_DIR, "country_core_demands.json")
OUTPUT_FILE = os.path.join(DATA_DIR, "demand_matrix_v2.json")

# ──────────────────────────── regions ────────────────────────────
REGIONS = {
    "北美": ["美国", "加拿大"],
    "欧洲": ["德国", "英国", "法国"],
    "东亚": ["日本", "韩国"],
    "东南亚": ["越南", "印度尼西亚"],
    "南亚": ["印度"],
    "中东": ["沙特阿拉伯", "阿联酋"],
    "南美": ["巴西", "墨西哥"],
    "大洋洲": ["澳大利亚"],
    "非洲": [],
}

# Build reverse map: country -> region
COUNTRY_TO_REGION = {}
for region, countries in REGIONS.items():
    for c in countries:
        COUNTRY_TO_REGION[c] = region

# Some names in export data that should map to regions directly
REGION_NAME_ALIASES = {
    "东南亚": "东南亚",
    "中东": "中东",
    "欧洲": "欧洲",
    "欧盟": "欧洲",
    "非洲": "非洲",
}

# ──────────────────────────── helpers ────────────────────────────

def load_json(path):
    """Load a JSON file, return None on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def build_l1_en_map(category_index):
    """Build L1 Chinese -> English name map from category_index."""
    m = {}
    if not category_index:
        return m
    for cat in category_index.get("categories", []):
        l1_cn = cat.get("l1_cn", "")
        l1_en = cat.get("l1_en", "")
        if l1_cn and l1_en:
            m[l1_cn] = l1_en
    return m


def build_l2_info_map(category_index):
    """Build (l1_cn, l2_slug) -> info map from category_index."""
    m = {}
    if not category_index:
        return m
    for cat in category_index.get("categories", []):
        key = (cat.get("l1_cn", ""), cat.get("l2_slug", ""))
        m[key] = cat
    return m


def map_country_to_region(country_name):
    """Map a country/region name from export data to a region name."""
    # Direct country mapping
    if country_name in COUNTRY_TO_REGION:
        return COUNTRY_TO_REGION[country_name]
    # Region alias mapping (e.g., "欧盟" -> "欧洲")
    if country_name in REGION_NAME_ALIASES:
        return REGION_NAME_ALIASES[country_name]
    return None


def aggregate_regional_exports(export_data):
    """
    Aggregate export amounts by region from export_data.
    Returns: dict of {region: {"amount": float, "countries": {country: amount}, "products": set}}
    """
    region_data = defaultdict(lambda: {"amount": 0.0, "countries": defaultdict(float), "products": set()})

    if not export_data:
        return region_data

    for entry in export_data:
        product_name = entry.get("name", "")
        for top in entry.get("top5", []):
            country = top.get("c", "")
            amt = top.get("amt", 0) or 0
            region = map_country_to_region(country)
            if region:
                region_data[region]["amount"] += amt
                region_data[region]["countries"][country] += amt
                if product_name:
                    region_data[region]["products"].add(product_name)

    return region_data


def compute_demand_levels(region_amounts):
    """
    Given {region: amount}, assign demand levels.
    top 3 by amount -> high, next 3 -> medium, rest with data -> low, none -> none
    """
    # Filter regions with actual data
    active = sorted(
        [(r, a) for r, a in region_amounts.items() if a > 0],
        key=lambda x: -x[1],
    )

    levels = {r: "none" for r in REGIONS}

    for i, (region, _) in enumerate(active):
        if i < 3:
            levels[region] = "high"
        elif i < 6:
            levels[region] = "medium"
        else:
            levels[region] = "low"

    return levels


def generate_insight(region, region_info, levels):
    """Generate a brief insight string for a region's demand."""
    level = levels.get(region, "none")
    if level == "none":
        return ""
    amt = region_info.get("amount", 0)
    countries = region_info.get("countries", {})
    top_country = max(countries, key=countries.get) if countries else ""
    if level == "high":
        return f"{top_country}为主要市场，出口额约{amt:.0f}百万美元，需求强劲"
    elif level == "medium":
        return f"以{top_country}为代表，出口额约{amt:.0f}百万美元，稳步增长"
    else:
        return f"出口额约{amt:.0f}百万美元，市场处于培育期"


def build_demand_intersection(levels, region_data):
    """Build demand_intersection string describing shared demand patterns."""
    active_regions = [r for r, lv in levels.items() if lv in ("high", "medium")]
    if not active_regions:
        return "暂无显著跨区域需求交叉"
    if len(active_regions) == 1:
        return f"需求集中在{active_regions[0]}地区，尚未形成跨区域联动"

    # Find products that appear in multiple regions
    all_products = defaultdict(set)
    for r in active_regions:
        info = region_data.get(r, {})
        for p in info.get("products", set()):
            all_products[p].add(r)

    shared = [(p, regs) for p, regs in all_products.items() if len(regs) >= 2]
    if shared:
        shared_desc = "、".join(f"{p}({len(regs)}个地区)" for p, regs in shared[:3])
        return f"{', '.join(active_regions)}等地区存在交叉需求，共享品类包括{shared_desc}"
    else:
        return f"{', '.join(active_regions)}等地区均有需求，但各区域侧重品类不同"


def compute_china_export(export_data):
    """
    Compute china_export summary from export_data.
    Returns dict with total_2024, growth_2024, top_markets.
    """
    if not export_data:
        return {"total_2024": None, "growth_2024": None, "top_markets": []}

    total_2024 = 0.0
    weighted_yoy_num = 0.0
    weighted_yoy_den = 0.0
    country_totals = defaultdict(lambda: {"amount": 0.0, "growth": None})

    for entry in export_data:
        # Get 2024 data
        for d in entry.get("data", []):
            if str(d.get("yr")) == "2024":
                amt = d.get("amt", 0) or 0
                yoy = d.get("yoy", 0) or 0
                total_2024 += amt
                weighted_yoy_num += amt * yoy
                weighted_yoy_den += amt
                break

        # Aggregate country-level from top5
        for top in entry.get("top5", []):
            c = top.get("c", "")
            amt = top.get("amt", 0) or 0
            yoy = top.get("yoy", 0)
            country_totals[c]["amount"] += amt
            if yoy is not None:
                if country_totals[c]["growth"] is None:
                    country_totals[c]["growth"] = []
                country_totals[c]["growth"].append((amt, yoy))

    # Weighted growth
    growth_2024 = None
    if weighted_yoy_den > 0:
        growth_2024 = round(weighted_yoy_num / weighted_yoy_den, 1)

    # Top 5 markets
    sorted_countries = sorted(country_totals.items(), key=lambda x: -x[1]["amount"])[:5]
    top_markets = []
    for c, info in sorted_countries:
        # Compute weighted growth for this country
        g = None
        if info["growth"]:
            num = sum(a * y for a, y in info["growth"])
            den = sum(a for a, _ in info["growth"])
            g = round(num / den, 1) if den > 0 else None
        top_markets.append({
            "country": c,
            "amount": round(info["amount"], 2),
            "growth": g,
        })

    return {
        "total_2024": round(total_2024, 2) if total_2024 else None,
        "growth_2024": growth_2024,
        "top_markets": top_markets,
    }


def build_keywords(detail_data, l2_tax):
    """Build keyword list from detail file and taxonomy L3 keywords."""
    kw = set()
    if detail_data:
        for k in detail_data.get("keywords_en", []):
            kw.add(k)
        for k in detail_data.get("keywords_cn", []):
            kw.add(k)
    # Add some L3 keywords from taxonomy
    if l2_tax:
        for l3 in l2_tax.get("l3_items", []):
            for k in l3.get("keywords", []):
                kw.add(k)
    return sorted(kw)[:20]  # Cap at 20 keywords to keep file size reasonable


def get_l2_products(detail_data, l2_tax):
    """Get product names from detail data or taxonomy L3 items."""
    products = []
    if detail_data and detail_data.get("export_data"):
        for ed in detail_data["export_data"]:
            name = ed.get("name", "")
            if name:
                products.append(name)
    if not products and l2_tax:
        for l3 in l2_tax.get("l3_items", []):
            cn = l3.get("cn", "")
            if cn:
                products.append(cn)
    return products[:10]  # Cap to keep size reasonable


# ──────────────────────────── main ────────────────────────────

def main():
    print("Loading source data...")

    taxonomy = load_json(TAXONOMY_FILE)
    if not taxonomy:
        print(f"ERROR: Cannot load taxonomy at {TAXONOMY_FILE}", file=sys.stderr)
        sys.exit(1)

    category_index = load_json(CATEGORY_INDEX_FILE)
    country_core = load_json(COUNTRY_CORE_DEMANDS_FILE)

    l1_en_map = build_l1_en_map(category_index)
    l2_info_map = build_l2_info_map(category_index)

    output = {
        "meta": {
            "generated": str(date.today()),
            "version": "2.0",
        },
        "categories": {},
    }

    total_l2 = 0
    l2_with_data = 0

    for l1_cat in taxonomy.get("categories", []):
        l1_cn = l1_cat.get("name_cn", "")
        l1_en = l1_en_map.get(l1_cn, "")
        l2_list = []

        for l2_cat in l1_cat.get("l2_categories", []):
            l2_cn = l2_cat.get("cn", "")
            l2_en = l2_cat.get("en", "")
            l2_slug = l2_cat.get("slug", "")
            total_l2 += 1

            # L3 items
            l3_items = [item.get("cn", "") for item in l2_cat.get("l3_items", []) if item.get("cn")]

            # Try to load detail file
            detail_path = os.path.join(CATEGORIES_DIR, l1_cn, f"{l2_slug}.json")
            detail_data = load_json(detail_path)

            # HS codes
            hs_codes = []
            if detail_data and detail_data.get("hs_codes"):
                hs_codes = detail_data["hs_codes"]

            export_data = detail_data.get("export_data") if detail_data else None

            if export_data:
                l2_with_data += 1

            # Regional demand
            region_exports = aggregate_regional_exports(export_data)
            region_amounts = {r: info["amount"] for r, info in region_exports.items()}
            levels = compute_demand_levels(region_amounts)

            regional_demand = {}
            for region in REGIONS:
                level = levels.get(region, "none")
                info = region_exports.get(region, {})
                prods = sorted(info.get("products", set()))[:5] if info.get("products") else []
                # If no products from export data, use L3 names
                if not prods and level != "none":
                    prods = get_l2_products(detail_data, l2_cat)[:3]
                insight = generate_insight(region, info, levels)
                regional_demand[region] = {
                    "demand_level": level,
                    "products": prods,
                    "insight": insight,
                }

            # Demand intersection
            demand_intersection = build_demand_intersection(levels, region_exports)

            # China export
            china_export = compute_china_export(export_data)

            # Keywords
            keywords = build_keywords(detail_data, l2_cat)

            l2_entry = {
                "name_cn": l2_cn,
                "name_en": l2_en,
                "l3_items": l3_items,
                "hs_codes": hs_codes,
                "regional_demand": regional_demand,
                "demand_intersection": demand_intersection,
                "china_export": china_export,
                "keywords": keywords,
            }
            l2_list.append(l2_entry)

        output["categories"][l1_cn] = {
            "name_en": l1_en,
            "l2_list": l2_list,
        }

    # Write output
    print(f"Writing output to {OUTPUT_FILE}...")
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    file_size = os.path.getsize(OUTPUT_FILE)
    print(f"Done! Output: {OUTPUT_FILE}")
    print(f"  L1 categories: {len(output['categories'])}")
    print(f"  L2 categories: {total_l2}")
    print(f"  L2 with export data: {l2_with_data}")
    print(f"  File size: {file_size / 1024 / 1024:.2f} MB")

    if file_size > 2 * 1024 * 1024:
        print("WARNING: File size exceeds 2MB target!", file=sys.stderr)


if __name__ == "__main__":
    main()
