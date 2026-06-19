#!/usr/bin/env node
/**
 * Populate export_data for category JSON files that are missing it.
 * Matches by HS code 2-digit chapter prefix to CUSTOMS_EXPORT_DATA.
 */
const fs = require('fs');
const path = require('path');

const REPO_DIR = path.resolve(__dirname, '..');
const INDEX_PATH = path.join(REPO_DIR, 'index.html');
const CAT_DIR = path.join(REPO_DIR, 'data', 'categories');

// 1. Extract CUSTOMS_EXPORT_DATA from index.html
const html = fs.readFileSync(INDEX_PATH, 'utf8');
const scriptStart = html.indexOf('<script>', 0);
const scriptEnd = html.indexOf('</script>', scriptStart);
const jsCode = html.substring(scriptStart + 8, scriptEnd);

// Mock browser globals
const mockCode = `
var window = {_tickerCache:{}};
var document = {getElementById:function(){return null},querySelectorAll:function(){return[]},addEventListener:function(){}};
var $el = function(){return null};
var setTimeout = function(){};
var setInterval = function(){};
`;
eval(mockCode + jsCode);

// 2. Build chapter lookup from CUSTOMS_EXPORT_DATA
const chapterLookup = {};
Object.keys(CUSTOMS_EXPORT_DATA).forEach(hs => {
  if (hs === '999999') return;
  const chapter = hs.substring(0, 2);
  if (!chapterLookup[chapter]) chapterLookup[chapter] = [];
  chapterLookup[chapter].push({
    hs_code: hs,
    name: CUSTOMS_EXPORT_DATA[hs].name || '',
    data: CUSTOMS_EXPORT_DATA[hs].data || [],
    top5: CUSTOMS_EXPORT_DATA[hs].top5 || []
  });
});

console.log(`Loaded ${Object.keys(CUSTOMS_EXPORT_DATA).length} HS codes`);
console.log(`Chapter lookup: ${Object.keys(chapterLookup).length} chapters`);
console.log(`Chapters: ${Object.keys(chapterLookup).sort().join(', ')}`);

// 3. Process all category JSON files
let updated = 0, skipped = 0, noMatch = 0;
const l1Dirs = fs.readdirSync(CAT_DIR).filter(d => {
  return fs.statSync(path.join(CAT_DIR, d)).isDirectory();
}).sort();

l1Dirs.forEach(l1Dir => {
  const l1Path = path.join(CAT_DIR, l1Dir);
  const files = fs.readdirSync(l1Path).filter(f => f.endsWith('.json')).sort();
  
  files.forEach(f => {
    const fpath = path.join(l1Path, f);
    const catData = JSON.parse(fs.readFileSync(fpath, 'utf8'));
    
    // Skip if already has export_data
    if (catData.export_data && Array.isArray(catData.export_data) && catData.export_data.length > 0) {
      skipped++;
      return;
    }
    
    // Get HS codes
    const hsCodes = catData.hs_codes || [];
    if (!hsCodes.length) {
      noMatch++;
      return;
    }
    
    // Match by chapter prefix
    const matches = [];
    const seenChapters = new Set();
    const seenHs = new Set();
    
    hsCodes.forEach(hs => {
      const numeric = String(hs).match(/(\d+)/);
      if (numeric) {
        const chapter = numeric[1].substring(0, 2);
        if (!seenChapters.has(chapter) && chapterLookup[chapter]) {
          seenChapters.add(chapter);
          chapterLookup[chapter].forEach(item => {
            if (!seenHs.has(item.hs_code)) {
              seenHs.add(item.hs_code);
              matches.push(item);
            }
          });
        }
      }
    });
    
    if (matches.length > 0) {
      catData.export_data = matches;
      fs.writeFileSync(fpath, JSON.stringify(catData, null, 2), 'utf8');
      updated++;
      console.log(`  UPDATED: ${l1Dir}/${f} -> ${matches.length} HS (chapters: ${[...seenChapters].sort().join(',')})`);
    } else {
      noMatch++;
      const chapters = new Set();
      hsCodes.forEach(hs => {
        const numeric = String(hs).match(/(\d+)/);
        if (numeric) chapters.add(numeric[1].substring(0, 2));
      });
      console.log(`  NO MATCH: ${l1Dir}/${f} (chapters: ${[...chapters].sort().join(',')})`);
    }
  });
});

console.log(`\nSummary: ${updated} updated, ${skipped} skipped, ${noMatch} no match`);
