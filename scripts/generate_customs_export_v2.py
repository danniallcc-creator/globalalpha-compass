#!/usr/bin/env python3
"""
Generate customs_export_v2.json and compass_keywords.json from category files.

Reads all data/categories/{L1_name}/{l2_slug}.json files, extracts export_data,
deduplicates by HS code (summing amounts), and produces:
  1. data/customs_export_v2.json - comprehensive customs export data
  2. data/compass_keywords.json  - keyword search index
"""

import json
import os
import sys
from collections import defaultdict
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(REPO_DIR, "data")
CATEGORIES_DIR = os.path.join(DATA_DIR, "categories")


def load_json(path):
    """Load a JSON file, returning None on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [WARN] Failed to load {path}: {e}", file=sys.stderr)
        return None


def merge_year_data(existing, incoming):
    """Merge two lists of year data entries, summing amounts for matching years."""
    yr_map = {}
    for entry in existing:
        yr = entry.get("yr")
        if yr:
            yr_map[yr] = {
                "yr": yr,
                "amt": (yr_map.get(yr, {}).get("amt", 0) or 0) + (entry.get("amt") or 0),
                "yoy": entry.get("yoy"),  # keep the latest yoy
            }
    for entry in incoming:
        yr = entry.get("yr")
        if yr:
            if yr in yr_map:
                yr_map[yr]["amt"] += entry.get("amt") or 0
                # Keep the yoy from whichever is the latest source
                if entry.get("yoy") is not None:
                    yr_map[yr]["yoy"] = entry["yoy"]
            else:
                yr_map[yr] = {
                    "yr": yr,
                    "amt": entry.get("amt") or 0,
                    "yoy": entry.get("yoy"),
                }
    # Sort by year descending
    return sorted(yr_map.values(), key=lambda x: x["yr"], reverse=True)


def merge_top5(existing, incoming):
    """Merge two top5 lists by summing amounts per country."""
    country_map = {}
    for entry in existing + incoming:
        c = entry.get("c")
        if c:
            if c in country_map:
                country_map[c]["amt"] += entry.get("amt") or 0
                if entry.get("yoy") is not None:
                    country_map[c]["yoy"] = entry["yoy"]
            else:
                country_map[c] = {
                    "c": c,
                    "amt": entry.get("amt") or 0,
                    "yoy": entry.get("yoy"),
                }
    # Sort by amount descending, take top 5
    sorted_countries = sorted(country_map.values(), key=lambda x: x["amt"], reverse=True)
    return sorted_countries[:5]


def round_amounts(data_list, top5_list):
    """Round amounts to 2 decimal places to keep file size reasonable."""
    for entry in data_list:
        if isinstance(entry.get("amt"), float):
            entry["amt"] = round(entry["amt"], 2)
    for entry in top5_list:
        if isinstance(entry.get("amt"), float):
            entry["amt"] = round(entry["amt"], 2)


def generate_customs_export():
    """Generate customs_export_v2.json from category files."""
    print("=" * 60)
    print("Generating customs_export_v2.json")
    print("=" * 60)

    if not os.path.isdir(CATEGORIES_DIR):
        print(f"ERROR: Categories directory not found: {CATEGORIES_DIR}", file=sys.stderr)
        sys.exit(1)

    # --- Phase 1: Collect all export_data entries ---
    # Track raw entries: hs_code -> list of (entry_dict, l1_name, l2_name)
    hs_entries = defaultdict(list)
    # Track L1/L2 occurrence counts per HS code for primary assignment
    hs_l1_counts = defaultdict(lambda: defaultdict(int))
    hs_l2_info = defaultdict(list)  # hs_code -> list of (l1, l2_name)
    hs_name = {}  # hs_code -> product name

    file_count = 0
    skip_count = 0

    l1_dirs = sorted(
        d for d in os.listdir(CATEGORIES_DIR)
        if os.path.isdir(os.path.join(CATEGORIES_DIR, d))
    )
    print(f"Found {len(l1_dirs)} L1 category directories")

    for l1_name in l1_dirs:
        l1_path = os.path.join(CATEGORIES_DIR, l1_name)
        for fname in sorted(os.listdir(l1_path)):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(l1_path, fname)
            data = load_json(fpath)
            if data is None:
                skip_count += 1
                continue

            export_data = data.get("export_data")
            if not export_data:
                skip_count += 1
                continue

            # Get L2 name from the file
            l2_name = data.get("name_cn", fname.replace(".json", ""))

            file_count += 1
            for entry in export_data:
                hs_code = entry.get("hs_code")
                if not hs_code:
                    continue
                hs_entries[hs_code].append((entry, l1_name, l2_name))
                hs_l1_counts[hs_code][l1_name] += 1
                hs_l2_info[hs_code].append((l1_name, l2_name))
                if hs_code not in hs_name:
                    hs_name[hs_code] = entry.get("name", "")

    print(f"Processed {file_count} files with export_data, skipped {skip_count}")
    print(f"Found {len(hs_entries)} unique HS codes")

    # --- Phase 2: Build hs_data with deduplication ---
    hs_data = {}
    # Also track which HS codes belong to which L1 for aggregation
    l1_hs_map = defaultdict(set)  # l1_name -> set of hs_codes

    for hs_code, entries in sorted(hs_entries.items()):
        # Determine primary L1 (most occurrences)
        l1_counts = hs_l1_counts[hs_code]
        primary_l1 = max(l1_counts, key=lambda k: l1_counts[k])

        # Determine primary L2 (first L2 under primary L1)
        primary_l2 = None
        for l1, l2 in hs_l2_info[hs_code]:
            if l1 == primary_l1:
                primary_l2 = l2
                break
        if primary_l2 is None:
            primary_l2 = hs_l2_info[hs_code][0][1]

        # Merge all year data and top5 across all entries
        merged_data = []
        merged_top5 = []
        for entry, _, _ in entries:
            merged_data = merge_year_data(merged_data, entry.get("data", []))
            merged_top5 = merge_top5(merged_top5, entry.get("top5", []))

        round_amounts(merged_data, merged_top5)

        hs_data[hs_code] = {
            "name": hs_name.get(hs_code, ""),
            "l1_category": primary_l1,
            "l2_category": primary_l2,
            "data": merged_data,
            "top5": merged_top5,
        }

        # Assign this HS code to its primary L1
        l1_hs_map[primary_l1].add(hs_code)

    # --- Phase 3: Build l1_aggregated ---
    l1_aggregated = {}

    for l1_name in sorted(l1_hs_map.keys()):
        hs_codes = l1_hs_map[l1_name]
        hs_count = len(hs_codes)

        # Sum totals per year
        year_totals = defaultdict(float)
        year_prev = defaultdict(float)
        has_data = False

        # Aggregate top5 by country across all HS codes under this L1
        country_totals = defaultdict(lambda: {"amt": 0.0, "yoy": None})

        subs = []

        for hs_code in sorted(hs_codes):
            info = hs_data[hs_code]
            for yr_entry in info.get("data", []):
                yr = yr_entry.get("yr")
                amt = yr_entry.get("amt") or 0
                year_totals[yr] += amt
                has_data = True

            for t5 in info.get("top5", []):
                c = t5.get("c")
                if c:
                    country_totals[c]["amt"] += t5.get("amt") or 0
                    if t5.get("yoy") is not None:
                        country_totals[c]["yoy"] = t5["yoy"]

            # Build sub entry
            amt_2025 = None
            yoy_2025 = None
            for yr_entry in info.get("data", []):
                if yr_entry.get("yr") == "2025":
                    amt_2025 = yr_entry.get("amt")
                    yoy_2025 = yr_entry.get("yoy")
                    break
            subs.append({
                "hs": hs_code,
                "name": info["name"],
                "amt_2025": amt_2025,
                "yoy_2025": yoy_2025,
            })

        # Sort subs by amt_2025 descending (None values at end)
        subs.sort(key=lambda x: (x["amt_2025"] is None, -(x["amt_2025"] or 0)))

        # Calculate YoY for aggregated totals
        def calc_yoy(current, previous):
            if current and previous and previous != 0:
                return round(((current - previous) / previous) * 100, 1)
            return None

        total_2025 = round(year_totals.get("2025", 0), 2) if has_data else None
        total_2024 = round(year_totals.get("2024", 0), 2) if has_data else None
        total_2023 = round(year_totals.get("2023", 0), 2) if has_data else None

        if total_2025 == 0 and total_2024 == 0 and total_2023 == 0:
            total_2025 = total_2024 = total_2023 = None

        # Top 5 countries for this L1
        top5 = sorted(
            [{"c": c, "amt": round(v["amt"], 2), "yoy": v["yoy"]} for c, v in country_totals.items()],
            key=lambda x: x["amt"],
            reverse=True,
        )[:5]

        l1_aggregated[l1_name] = {
            "name": l1_name,
            "hs_count": hs_count,
            "total_2025": total_2025,
            "total_2024": total_2024,
            "total_2023": total_2023,
            "yoy_2025": calc_yoy(total_2025, total_2024),
            "yoy_2024": calc_yoy(total_2024, total_2023),
            "top5": top5,
            "subs": subs,
        }

    # --- Phase 4: Write output ---
    output = {
        "meta": {
            "generated": str(date.today()),
            "total_hs_codes": len(hs_data),
            "source": "category_files",
        },
        "hs_data": hs_data,
        "l1_aggregated": l1_aggregated,
    }

    out_path = os.path.join(DATA_DIR, "customs_export_v2.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    file_size_kb = os.path.getsize(out_path) / 1024
    print(f"\nWrote {out_path}")
    print(f"  Total HS codes: {len(hs_data)}")
    print(f"  L1 categories: {len(l1_aggregated)}")
    print(f"  File size: {file_size_kb:.1f} KB")

    return output


def generate_compass_keywords():
    """Generate compass_keywords.json from taxonomy and category files."""
    print("\n" + "=" * 60)
    print("Generating compass_keywords.json")
    print("=" * 60)

    taxonomy_path = os.path.join(DATA_DIR, "taxonomy.json")
    taxonomy = load_json(taxonomy_path)
    if taxonomy is None:
        print("ERROR: Could not load taxonomy.json", file=sys.stderr)
        sys.exit(1)

    # Build keyword entries with deduplication
    # Key: text -> entry dict (prefer higher level type)
    seen = {}  # text -> {text, type, l1, l2, match_key}
    type_priority = {"l1": 0, "l2": 1, "l3": 2}

    def add_keyword(text, kw_type, l1, l2=None, match_key=None):
        """Add a keyword entry, deduplicating by text (prefer higher level)."""
        if not text or not text.strip():
            return
        text = text.strip()
        new_entry = {
            "text": text,
            "type": kw_type,
            "l1": l1,
            "l2": l2,
            "match_key": match_key or l1,
        }
        if text in seen:
            existing_priority = type_priority.get(seen[text]["type"], 99)
            new_priority = type_priority.get(kw_type, 99)
            if new_priority < existing_priority:
                seen[text] = new_entry
        else:
            seen[text] = new_entry

    # Phase 1: Add L1, L2, L3 names from taxonomy
    for l1_cat in taxonomy.get("categories", []):
        l1_name = l1_cat.get("name_cn", "")
        if not l1_name:
            continue

        # Add L1 keyword
        add_keyword(l1_name, "l1", l1_name, match_key=l1_name)

        for l2_cat in l1_cat.get("l2_categories", []):
            l2_name = l2_cat.get("cn", "")
            if not l2_name:
                continue

            # Add L2 keyword
            add_keyword(l2_name, "l2", l1_name, l2=l2_name, match_key=l1_name)

            # Add L3 keywords
            for l3_item in l2_cat.get("l3_items", []):
                l3_name = l3_item.get("cn", "")
                if l3_name:
                    add_keyword(l3_name, "l3", l1_name, l2=l2_name, match_key=l1_name)

    print(f"  Keywords from taxonomy: {len(seen)}")

    # Phase 2: Add keywords_cn from each category file
    kw_added = 0
    for l1_name in sorted(os.listdir(CATEGORIES_DIR)):
        l1_path = os.path.join(CATEGORIES_DIR, l1_name)
        if not os.path.isdir(l1_path):
            continue
        for fname in sorted(os.listdir(l1_path)):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(l1_path, fname)
            data = load_json(fpath)
            if data is None:
                continue

            l2_name = data.get("name_cn", "")
            keywords_cn = data.get("keywords_cn", [])
            for kw in keywords_cn:
                if kw and kw.strip():
                    # Add as l2-level keyword (lower priority than taxonomy entries)
                    kw_text = kw.strip()
                    if kw_text not in seen:
                        add_keyword(kw_text, "l2", l1_name, l2=l2_name, match_key=l1_name)
                        kw_added += 1

    print(f"  Additional keywords from category files: {kw_added}")
    print(f"  Total unique keywords: {len(seen)}")

    # Phase 3: Write output
    keywords_list = sorted(seen.values(), key=lambda x: (type_priority.get(x["type"], 99), x["text"]))

    output = {
        "meta": {
            "generated": str(date.today()),
        },
        "keywords": keywords_list,
    }

    out_path = os.path.join(DATA_DIR, "compass_keywords.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    file_size_kb = os.path.getsize(out_path) / 1024
    print(f"\nWrote {out_path}")
    print(f"  Total keywords: {len(keywords_list)}")
    print(f"  File size: {file_size_kb:.1f} KB")


def main():
    print(f"Data directory: {DATA_DIR}")
    print(f"Categories directory: {CATEGORIES_DIR}")
    print()

    generate_customs_export()
    generate_compass_keywords()

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
