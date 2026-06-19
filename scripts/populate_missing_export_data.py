#!/usr/bin/env python3
"""
Populate export_data for category JSON files that are missing it.
Matches by HS code 2-digit chapter prefix to CUSTOMS_EXPORT_DATA.
"""
import json
import os
import re
import sys

# Load CUSTOMS_EXPORT_DATA from index.html
def load_customs_export():
    """Extract CUSTOMS_EXPORT_DATA from index.html"""
    html_path = os.path.join(os.path.dirname(__file__), '..', 'index.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # Find CUSTOMS_EXPORT_DATA block
    start = html.find('var CUSTOMS_EXPORT_DATA = {')
    if start == -1:
        print("ERROR: CUSTOMS_EXPORT_DATA not found in index.html")
        sys.exit(1)
    
    # Extract the JS object
    brace_count = 0
    in_string = False
    escape = False
    end = start
    for i in range(start + len('var CUSTOMS_EXPORT_DATA = '), len(html)):
        c = html[i]
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == "'" and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            brace_count += 1
        elif c == '}':
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break
    
    js_obj = html[start:end]
    # Convert JS to JSON-parseable format
    # Replace single quotes with double quotes
    js_obj = js_obj.replace('var CUSTOMS_EXPORT_DATA = ', '')
    js_obj = js_obj.replace("'", '"')
    # Handle unquoted keys (there shouldn't be any in this data, but just in case)
    
    try:
        customs = json.loads(js_obj)
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse CUSTOMS_EXPORT_DATA: {e}")
        # Try a more lenient approach
        print("Trying regex extraction...")
        customs = {}
    
    return customs

def build_chapter_lookup(customs):
    """Build lookup by 2-digit HS chapter prefix"""
    lookup = {}
    for hs_code, data in customs.items():
        if hs_code == '999999':
            continue
        chapter = hs_code[:2]
        if chapter not in lookup:
            lookup[chapter] = []
        lookup[chapter].append({
            'hs_code': hs_code,
            'name': data.get('name', ''),
            'data': data.get('data', []),
            'top5': data.get('top5', [])
        })
    return lookup

def main():
    base_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'categories')
    
    print("Loading CUSTOMS_EXPORT_DATA...")
    customs = load_customs_export()
    print(f"  Loaded {len(customs)} HS codes")
    
    chapter_lookup = build_chapter_lookup(customs)
    print(f"  Built chapter lookup: {len(chapter_lookup)} chapters")
    
    # Process all category files
    updated = 0
    skipped = 0
    no_match = 0
    
    for l1_dir in sorted(os.listdir(base_dir)):
        l1_path = os.path.join(base_dir, l1_dir)
        if not os.path.isdir(l1_path):
            continue
        
        for f in sorted(os.listdir(l1_path)):
            if not f.endswith('.json'):
                continue
            
            fpath = os.path.join(l1_path, f)
            with open(fpath, 'r', encoding='utf-8') as fh:
                cat_data = json.load(fh)
            
            # Skip if already has export_data
            if cat_data.get('export_data') and isinstance(cat_data['export_data'], list) and len(cat_data['export_data']) > 0:
                skipped += 1
                continue
            
            # Get HS codes from category
            hs_codes = cat_data.get('hs_codes', [])
            if not hs_codes:
                no_match += 1
                continue
            
            # Try to match by chapter prefix
            matches = []
            seen_chapters = set()
            for hs_code in hs_codes:
                # Extract numeric prefix
                numeric = re.match(r'(\d+)', str(hs_code))
                if numeric:
                    prefix = numeric.group(1)
                    chapter = prefix[:2]
                    if chapter not in seen_chapters and chapter in chapter_lookup:
                        seen_chapters.add(chapter)
                        matches.extend(chapter_lookup[chapter])
            
            if matches:
                # Deduplicate by hs_code
                seen_hs = set()
                unique_matches = []
                for m in matches:
                    if m['hs_code'] not in seen_hs:
                        seen_hs.add(m['hs_code'])
                        unique_matches.append(m)
                
                cat_data['export_data'] = unique_matches
                
                with open(fpath, 'w', encoding='utf-8') as fh:
                    json.dump(cat_data, fh, ensure_ascii=False, indent=2)
                
                updated += 1
                print(f"  UPDATED: {l1_dir}/{f} -> {len(unique_matches)} HS codes (chapters: {sorted(seen_chapters)})")
            else:
                no_match += 1
                # Find what chapters the HS codes belong to
                chapters = set()
                for hs_code in hs_codes:
                    numeric = re.match(r'(\d+)', str(hs_code))
                    if numeric:
                        chapters.add(numeric.group(1)[:2])
                print(f"  NO MATCH: {l1_dir}/{f} (chapters: {sorted(chapters)})")
    
    print(f"\nSummary: {updated} updated, {skipped} already had data, {no_match} no match")

if __name__ == '__main__':
    main()
