#!/usr/bin/env python3
"""
Merge rich existing data from extracted JSON files into generated category JSON files.

Data sources:
- industry_trends.json: 24 industries with six-dimensional analysis
- demand_matrix.json: 19 categories with detailed demand scenarios
- customs_export.json: 43 HS codes with export history
- compliance_db.json: 21 product categories with compliance data

Target: 466 category JSON files under data/categories/{l1_name}/{l2_slug}.json
"""

import json
import os
import re
from pathlib import Path
from collections import defaultdict

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CATEGORIES_DIR = DATA_DIR / "categories"

INDUSTRY_TRENDS_FILE = DATA_DIR / "industry_trends.json"
DEMAND_MATRIX_FILE = DATA_DIR / "demand_matrix.json"
CUSTOMS_EXPORT_FILE = DATA_DIR / "customs_export.json"
COMPLIANCE_DB_FILE = DATA_DIR / "compliance_db.json"
CATEGORY_INDEX_FILE = DATA_DIR / "category_index.json"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── Build mapping tables ────────────────────────────────────────────────────

def build_demand_matrix_lookup(demand_matrix):
    """
    Build a lookup from multiple key variants to demand matrix entries.
    Keys in demand_matrix: 储能, 家具, 玩具, 家电, 服装, 建材, 汽车零配件,
    消费电子, 医疗器械, 灯具, 新能源汽车, 农业, 食品及饮料, 服装及配饰,
    面料及纺织原材料, 电气设备及用品, 化学品, 金属与合金, 家居园艺,
    礼品与工艺品, 陶瓷
    """
    lookup = {}
    # Direct mapping and common aliases
    aliases = {
        "储能": ["储能", "储能系统", "电池"],
        "家具": ["家具", "家居家具", "商用家具", "户外家具", "家具配件", "家具零配件", "家具五金", "婴童家具"],
        "玩具": ["玩具", "母婴&玩具", "母婴及玩具"],
        "家电": ["家电", "家用电器", "厨房小家电", "厨房大家电", "清洁家电", "智能家用电器",
                 "供暖及制冷电器", "冰箱冰柜", "热水器", "洗衣设备", "空气质量电器", "水处理设备", "家电零配件"],
        "服装": ["服装", "服装及配饰"],
        "服装及配饰": ["服装及配饰", "服装"],
        "建材": ["建材", "建材与房地产"],
        "汽车零配件": ["汽车零配件"],
        "消费电子": ["消费电子"],
        "医疗器械": ["医疗器械", "医疗器械和用品"],
        "灯具": ["灯具", "灯具照明"],
        "新能源汽车": ["新能源汽车"],
        "农业": ["农业"],
        "食品及饮料": ["食品及饮料"],
        "面料及纺织原材料": ["面料及纺织原材料"],
        "电气设备及用品": ["电气设备及用品"],
        "化学品": ["化学品"],
        "金属与合金": ["金属与合金"],
        "家居园艺": ["家居园艺"],
        "礼品与工艺品": ["礼品与工艺品"],
        "陶瓷": ["陶瓷"],
    }
    for key in demand_matrix:
        lookup[key] = demand_matrix[key]
        if key in aliases:
            for alias in aliases[key]:
                if alias not in lookup:
                    lookup[alias] = demand_matrix[key]
    return lookup


def build_compliance_lookup(compliance_db):
    """
    Build lookup from L1 category names to compliance data.
    Keys in compliance_db: 消费电子, 家用电器, 食品及饮料, 服装及配饰, 玩具,
    医疗器械, 家具, 美妆, 汽车零配件, 母婴及玩具, 灯具照明, 安防, 工业机械,
    化学品, 可再生能源, 健康护理, 橡胶与塑料制品, 五金工具, 建材与房地产, 农业, 仪器仪表
    """
    lookup = {}
    # Map compliance keys to L1 names used in category files
    l1_aliases = {
        "消费电子": ["消费电子"],
        "家用电器": ["家用电器"],
        "食品及饮料": ["食品及饮料"],
        "服装及配饰": ["服装及配饰"],
        "玩具": ["母婴&玩具", "母婴及玩具"],
        "医疗器械": ["医疗器械和用品"],
        "家具": ["家具"],
        "美妆": ["美妆"],
        "汽车零配件": ["汽车零配件"],
        "母婴及玩具": ["母婴&玩具", "母婴及玩具"],
        "灯具照明": ["灯具照明"],
        "安防": ["安防"],
        "工业机械": ["工业机械"],
        "化学品": ["化学品"],
        "可再生能源": ["可再生能源"],
        "健康护理": ["健康护理"],
        "橡胶与塑料制品": ["橡胶与塑料制品"],
        "五金工具": ["五金工具"],
        "建材与房地产": ["建材与房地产"],
        "农业": ["农业"],
        "仪器仪表": ["仪器仪表"],
    }
    for key in compliance_db:
        lookup[key] = compliance_db[key]
        if key in l1_aliases:
            for alias in l1_aliases[key]:
                if alias not in lookup:
                    lookup[alias] = compliance_db[key]
    return lookup


def build_customs_hs_lookup(customs_export):
    """
    Build a mapping from HS code prefixes (2-digit and 4-digit) to customs export data.
    """
    lookup_2 = defaultdict(list)  # 2-digit prefix
    lookup_4 = defaultdict(list)  # 4-digit prefix
    for hs_code, data in customs_export.items():
        entry = {"hs_code": hs_code, "name": data["name"], **{k: v for k, v in data.items() if k != "name"}}
        if len(hs_code) >= 2:
            lookup_2[hs_code[:2]].append(entry)
        if len(hs_code) >= 4:
            lookup_4[hs_code[:4]].append(entry)
    return {"2": dict(lookup_2), "4": dict(lookup_4)}


def normalize_name(name):
    """Normalize Chinese name for fuzzy matching."""
    # Remove common suffixes/prefixes and whitespace
    name = name.strip()
    return name


def find_demand_match(l1_name, l2_name_cn, demand_lookup):
    """Find the best demand matrix match for a category."""
    # Try exact L1 match first
    if l1_name in demand_lookup:
        return demand_lookup[l1_name]
    # Try L2 Chinese name
    if l2_name_cn in demand_lookup:
        return demand_lookup[l2_name_cn]
    # Try partial matching
    for key in demand_lookup:
        if key in l1_name or l1_name in key:
            return demand_lookup[key]
        if key in l2_name_cn or l2_name_cn in key:
            return demand_lookup[key]
    return None


def find_customs_match(hs_codes_list, customs_lookup):
    """Find matching customs export data based on HS code prefixes."""
    matches = []
    lookup_4 = customs_lookup["4"]
    lookup_2 = customs_lookup["2"]
    for hs_code in hs_codes_list:
        # Extract numeric prefix from hs_code like "85xx" -> "85", "8507xx" -> "8507"
        numeric = re.match(r"(\d+)", hs_code)
        if numeric:
            prefix = numeric.group(1)
            # Try 4-digit match first (more specific), then 2-digit
            if len(prefix) >= 4:
                p4 = prefix[:4]
                if p4 in lookup_4:
                    matches.extend(lookup_4[p4])
            if len(prefix) >= 2:
                p2 = prefix[:2]
                if p2 in lookup_2:
                    matches.extend(lookup_2[p2])
    # Deduplicate by hs_code
    seen = set()
    unique = []
    for m in matches:
        if m["hs_code"] not in seen:
            seen.add(m["hs_code"])
            unique.append(m)
    return unique if unique else None


def find_compliance_match(l1_name, compliance_lookup):
    """Find compliance data matching a category's L1."""
    if l1_name in compliance_lookup:
        return compliance_lookup[l1_name]
    # Partial match
    for key in compliance_lookup:
        if key in l1_name or l1_name in key:
            return compliance_lookup[key]
    return None


def modify_opportunity_for_l2(industry_analysis, l2_name_cn, l2_name_en):
    """
    Modify the opportunity field of L1 industry analysis to include L2-specific keywords.
    """
    analysis = dict(industry_analysis)  # Deep copy the top level
    original_opp = analysis.get("opportunity", "")
    # Append L2-specific context
    l2_hint = f"；{l2_name_cn}({l2_name_en})细分领域机会值得关注"
    analysis["opportunity"] = original_opp + l2_hint
    return analysis


def summarize_compliance(compliance_data):
    """
    Convert detailed compliance DB data into a compact summary string.
    """
    if not compliance_data:
        return None
    parts = []
    for region, info in compliance_data.items():
        certs = info.get("cert", [])
        cert_str = ", ".join(certs[:3])  # Top 3 certs
        parts.append(f"{region}: {cert_str}")
    return " | ".join(parts[:6])  # Top 6 regions


def main():
    print("=" * 70)
    print("GlobalAlpha Compass: Merge Existing Data into Category Files")
    print("=" * 70)

    # ─── Load all data sources ───────────────────────────────────────────
    print("\n[1/6] Loading data sources...")
    industry_trends = load_json(INDUSTRY_TRENDS_FILE)
    demand_matrix = load_json(DEMAND_MATRIX_FILE)
    customs_export = load_json(CUSTOMS_EXPORT_FILE)
    compliance_db = load_json(COMPLIANCE_DB_FILE)
    category_index = load_json(CATEGORY_INDEX_FILE)

    print(f"  Industry trends: {len(industry_trends)} industries")
    print(f"  Demand matrix: {len(demand_matrix)} categories")
    print(f"  Customs export: {len(customs_export)} HS codes")
    print(f"  Compliance DB: {len(compliance_db)} product categories")
    print(f"  Category index: {len(category_index['categories'])} categories")

    # ─── Build lookup tables ─────────────────────────────────────────────
    print("\n[2/6] Building lookup tables...")
    demand_lookup = build_demand_matrix_lookup(demand_matrix)
    compliance_lookup = build_compliance_lookup(compliance_db)
    customs_lookup = build_customs_hs_lookup(customs_export)

    # ─── Process each category file ──────────────────────────────────────
    print("\n[3/6] Processing category files...")

    # Counters
    enriched_count = 0
    industry_enriched = 0
    demand_enriched = 0
    customs_enriched = 0
    compliance_enriched = 0
    total_files = 0
    enriched_ids = set()

    # Walk through all category files
    for l1_dir in sorted(CATEGORIES_DIR.iterdir()):
        if not l1_dir.is_dir():
            continue
        l1_name = l1_dir.name
        for cat_file in sorted(l1_dir.glob("*.json")):
            total_files += 1
            cat_data = load_json(cat_file)
            cat_id = cat_data.get("id", "")
            l2_name_cn = cat_data.get("name_cn", "")
            l2_name_en = cat_data.get("name_en", "")
            hs_codes = cat_data.get("hs_codes", [])
            parent_cn = cat_data.get("parent_cn", l1_name)

            got_data = False

            # ─── 1. Industry Trends (match by L1 name) ──────────────────
            if parent_cn in industry_trends or l1_name in industry_trends:
                trend_key = parent_cn if parent_cn in industry_trends else l1_name
                trend_data = industry_trends[trend_key]
                cat_data["industry_analysis"] = modify_opportunity_for_l2(
                    trend_data, l2_name_cn, l2_name_en
                )
                industry_enriched += 1
                got_data = True

            # ─── 2. Demand Matrix (fuzzy match by name) ─────────────────
            demand_match = find_demand_match(l1_name, l2_name_cn, demand_lookup)
            if demand_match:
                cat_data["demand_scenarios"] = demand_match
                demand_enriched += 1
                got_data = True

            # ─── 3. Customs Export (match by HS code prefix) ────────────
            customs_match = find_customs_match(hs_codes, customs_lookup)
            if customs_match:
                cat_data["export_data"] = customs_match
                customs_enriched += 1
                got_data = True

            # ─── 4. Compliance DB (match by L1 name) ────────────────────
            compliance_match = find_compliance_match(parent_cn, compliance_lookup)
            if compliance_match is None:
                compliance_match = find_compliance_match(l1_name, compliance_lookup)
            if compliance_match:
                summary = summarize_compliance(compliance_match)
                if summary:
                    cat_data["compliance_summary"] = summary
                # Also store detailed compliance as a separate field
                cat_data["compliance_detail"] = compliance_match
                compliance_enriched += 1
                got_data = True

            # ─── Set data_source ────────────────────────────────────────
            if got_data:
                cat_data["data_source"] = "merged_existing"
                enriched_count += 1
                enriched_ids.add(cat_id)

            # ─── Update last_updated ────────────────────────────────────
            if got_data:
                cat_data["last_updated"] = "2026-06-10"

            # ─── Save the updated file ──────────────────────────────────
            save_json(cat_file, cat_data)

    # ─── Update category_index.json ──────────────────────────────────────
    print("\n[4/6] Updating category_index.json...")
    for cat_entry in category_index["categories"]:
        cat_id = cat_entry.get("id", "")
        if cat_id in enriched_ids:
            cat_entry["has_detailed_data"] = True
        else:
            cat_entry["has_detailed_data"] = False

    save_json(CATEGORY_INDEX_FILE, category_index)

    # ─── Print summary ──────────────────────────────────────────────────
    print("\n[5/6] Summary:")
    print(f"  Total category files processed: {total_files}")
    print(f"  Categories enriched with merged data: {enriched_count}")
    print(f"    - Industry trends (from industry_trends.json): {industry_enriched}")
    print(f"    - Demand scenarios (from demand_matrix.json): {demand_enriched}")
    print(f"    - Export data (from customs_export.json): {customs_enriched}")
    print(f"    - Compliance data (from compliance_db.json): {compliance_enriched}")
    print(f"  Categories without enriched data: {total_files - enriched_count}")

    # ─── Verification ───────────────────────────────────────────────────
    print("\n[6/6] Verification - checking a few enriched files...")
    verification_files = [
        CATEGORIES_DIR / "可再生能源" / "energy-storage-system.json",
        CATEGORIES_DIR / "家用电器" / "small-kitchen-appliances.json",
        CATEGORIES_DIR / "家居园艺" / "garden-supplies.json",
    ]
    for vf in verification_files:
        if vf.exists():
            vdata = load_json(vf)
            src = vdata.get("data_source", "unknown")
            has_demand = "demand_scenarios" in vdata
            has_export = vdata.get("export_data") is not None
            has_compliance_detail = "compliance_detail" in vdata
            industry_src = "existing" if vdata.get("industry_analysis", {}).get("culture", "").startswith(("中", "东", "全", "日", "韩", "印", "穆", "欧", "非", "拉")) else "template"
            print(f"\n  {vf.relative_to(BASE_DIR)}:")
            print(f"    data_source: {src}")
            print(f"    industry_analysis source: {industry_src}")
            print(f"    has demand_scenarios: {has_demand}")
            print(f"    has export_data: {has_export}")
            print(f"    has compliance_detail: {has_compliance_detail}")

    # Verify category_index
    detailed_count = sum(1 for c in category_index["categories"] if c.get("has_detailed_data"))
    print(f"\n  category_index.json: {detailed_count}/{len(category_index['categories'])} categories have has_detailed_data=true")

    print("\n" + "=" * 70)
    print("Merge complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
