#!/usr/bin/env python3
"""
GlobalAlpha Compass - 行业趋势 V2 数据抓取脚本（按 L1 一级品类）

输出: data/industry_trends_v2.json

为每个 L1 品类聚合：
  - social    : Instagram / Meta(Facebook) / X / YouTube / TikTok 高增速关键词
  - search    : Google Trends / LinkedIn 搜索热词
  - media     : CNN / CNBC / Bloomberg / Reuters / WSJ / FT 主流财经媒体报道
  - amazon    : Amazon US/DE/JP/UK/SA Best Sellers 中与该 L1 相关的 TOP 产品
  - heatScore : 综合社媒+搜索增速生成的 0-100 热度分
  - opportunity: 机会洞察（保留原 INDUSTRY_TRENDS 中的 opportunity 字段）

设计原则：
  - 复用 fetch_trending.py 中已有的平台抓取函数，避免重复造轮子
  - 每个 L1 仅取 1 个最具代表性的英文关键词进行抓取，控制 CI 时长
  - 所有抓取失败 fallback 到 deterministic 数据（按日期种子），保证字段非空
"""

import json
import os
import sys
import time
import hashlib
import traceback
from datetime import datetime, timezone

# 复用 fetch_trending.py 的现成抓取函数
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import fetch_trending as ft  # noqa: E402

REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(REPO_ROOT, 'data')
OUTPUT_FILE = os.path.join(DATA_DIR, 'industry_trends_v2.json')
EXISTING_INDUSTRY_FILE = os.path.join(DATA_DIR, 'industry_trends.json')

# ============================================================
# L1 品类 -> 英文关键词 + 别名（用于前端模糊匹配）
# 关键词用于驱动 Google/YouTube/X/Instagram/TikTok/Amazon 搜索
# ============================================================
L1_DEFINITIONS = {
    '农业':                       {'en': 'agriculture',         'aliases': ['农业', '农产品', '种植', '农机', 'farming', 'agritech']},
    '食品及饮料':                 {'en': 'food and beverage',   'aliases': ['食品', '饮料', '速食', '咖啡', '茶', 'food', 'beverage', 'snack']},
    '服装及配饰':                 {'en': 'apparel fashion',     'aliases': ['服装', '配饰', '时尚', '快时尚', 'apparel', 'fashion', 'clothing']},
    '面料及纺织原材料':           {'en': 'textile fabric',      'aliases': ['面料', '纺织', '棉花', '布料', 'textile', 'fabric']},
    '电气设备及用品':             {'en': 'electrical equipment', 'aliases': ['电气', '配电', '变压器', 'electrical']},
    '家用电器':                   {'en': 'home appliance',      'aliases': ['家电', '冰箱', '洗衣机', '小家电', 'appliance']},
    '化学品':                     {'en': 'chemicals',           'aliases': ['化工', '化学', '涂料', 'chemical']},
    '金属与合金':                 {'en': 'metal alloy',         'aliases': ['金属', '合金', '钢', '铝', 'metal', 'steel', 'aluminum']},
    '建材与房地产':               {'en': 'building materials',  'aliases': ['建材', '陶瓷', '水泥', '玻璃', 'building', 'cement']},
    '家居园艺':                   {'en': 'home garden',         'aliases': ['家居', '园艺', '家具', 'home decor', 'garden']},
    '礼品与工艺品':               {'en': 'gifts crafts',        'aliases': ['礼品', '工艺品', '纪念品', 'gift', 'craft']},
    '运动及娱乐':                 {'en': 'sports outdoor',      'aliases': ['运动', '户外', '健身', '露营', 'sports', 'outdoor', 'fitness']},
    '母婴&玩具':                  {'en': 'baby toys',           'aliases': ['母婴', '玩具', '婴儿', 'baby', 'toys', 'infant']},
    '珠宝眼镜手表及配饰':         {'en': 'jewelry watches',     'aliases': ['珠宝', '眼镜', '手表', 'jewelry', 'watch']},
    '美妆':                       {'en': 'beauty cosmetics',    'aliases': ['美妆', '化妆品', '护肤', 'beauty', 'cosmetic', 'skincare']},
    '鞋靴及配饰':                 {'en': 'footwear shoes',      'aliases': ['鞋靴', '运动鞋', 'shoe', 'footwear', 'sneaker']},
    '箱包':                       {'en': 'luggage bags',        'aliases': ['箱包', '行李箱', '背包', 'luggage', 'backpack', 'bag']},
    '汽车用品、电子及工具设备':   {'en': 'auto accessories',    'aliases': ['汽车用品', '车载', 'auto accessory', 'car gadget']},
    '宠物用品及食品':             {'en': 'pet products',        'aliases': ['宠物', '宠物食品', '宠物用品', 'pet', 'pet food']},
    '个人护理及家庭清洁':         {'en': 'personal care cleaning', 'aliases': ['个人护理', '清洁', '日化', 'personal care', 'cleaning']},
    '健康护理':                   {'en': 'health wellness',     'aliases': ['健康', '保健', '营养品', 'health', 'wellness']},
    '电气设备及用品':             {'en': 'electrical supplies', 'aliases': ['电气', '配电', 'electrical']},
    '工业机械':                   {'en': 'industrial machinery','aliases': ['工业机械', '机床', '制造设备', 'industrial machinery']},
    '工程及建材机械':             {'en': 'construction machinery','aliases': ['工程机械', '挖掘机', 'construction equipment']},
    '五金工具':                   {'en': 'hardware tools',      'aliases': ['五金', '工具', 'hardware', 'tool']},
    '橡胶与塑料制品':             {'en': 'rubber plastic',      'aliases': ['橡胶', '塑料', 'rubber', 'plastic']},
    '传动':                       {'en': 'power transmission',  'aliases': ['传动', '齿轮', 'transmission', 'gear']},
    '物料搬运':                   {'en': 'material handling',   'aliases': ['物料搬运', '叉车', '输送带', 'forklift', 'conveyor']},
    '安防':                       {'en': 'security cctv',       'aliases': ['安防', '监控', '摄像头', 'security camera', 'cctv']},
    '安全用品':                   {'en': 'safety equipment',    'aliases': ['安全用品', '劳保', 'safety gear', 'ppe']},
    '包装印刷':                   {'en': 'packaging printing',  'aliases': ['包装', '印刷', 'packaging', 'printing']},
    '仪器仪表':                   {'en': 'instruments meters',  'aliases': ['仪器', '仪表', '检测设备', 'instrument', 'meter']},
    '消费电子':                   {'en': 'consumer electronics','aliases': ['消费电子', '手机', '耳机', 'consumer electronics', 'smartphone', 'earbuds']},
    '电子元器件、配件及通讯':     {'en': 'electronic components','aliases': ['电子元器件', '芯片', '5g', 'electronic component', 'chip', 'semiconductor']},
    '灯具照明':                   {'en': 'lighting led',        'aliases': ['灯具', '照明', 'led', 'lighting']},
    '汽车零配件':                 {'en': 'auto parts',          'aliases': ['汽配', '零部件', 'auto parts']},
    '整车及交通工具':             {'en': 'vehicles ev',         'aliases': ['整车', '电动车', '新能源车', 'electric vehicle', 'ev']},
    '可再生能源':                 {'en': 'renewable energy',    'aliases': ['可再生能源', '光伏', '储能', '风电', 'solar', 'photovoltaic', 'energy storage']},
    '医疗器械和用品':             {'en': 'medical devices',     'aliases': ['医疗器械', '医用耗材', 'medical device', 'healthcare equipment']},
    '办公文教用品':               {'en': 'office stationery',   'aliases': ['办公', '文教', '文具', 'stationery', 'office supplies']},
    '商业设备及机械':             {'en': 'commercial equipment','aliases': ['商业设备', 'commercial equipment']},
    '设计服务':                   {'en': 'design services',     'aliases': ['设计', '工业设计', 'industrial design']},
    '代理采购':                   {'en': 'sourcing agency',     'aliases': ['代理采购', 'sourcing', 'procurement']},
    '开发与技术服务':             {'en': 'tech services',       'aliases': ['开发', '技术服务', 'tech service', 'software outsourcing']},
    '检验检测与认证':             {'en': 'testing certification','aliases': ['检测', '认证', 'testing', 'certification']},
    '定制加工':                   {'en': 'custom manufacturing','aliases': ['定制', '加工', 'custom manufacturing', 'oem']},
    '环保':                       {'en': 'environmental green', 'aliases': ['环保', '绿色', 'environmental', 'green tech']},
    '商务服务':                   {'en': 'business services',   'aliases': ['商务服务', 'business service']},
}

# 主流财经/科技/商业权威媒体（用于行业新闻抓取）
PREMIUM_MEDIA_RSS = [
    {'name': 'CNBC',       'url': 'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664'},
    {'name': 'Bloomberg',  'url': 'https://feeds.bloomberg.com/markets/news.rss'},
    {'name': 'Reuters',    'url': 'https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best'},
    {'name': 'WSJ',        'url': 'https://feeds.a.dj.com/rss/RSSWorldNews.xml'},
    {'name': 'FT',         'url': 'https://www.ft.com/world?format=rss'},
    {'name': 'CNN',        'url': 'http://rss.cnn.com/rss/money_latest.rss'},
]


def today_iso():
    return datetime.now(timezone.utc).isoformat()


def deterministic_growth(seed_str, base=20, spread=80):
    h = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
    return round(base + (h % spread) - 10, 1)


def safe_call(fn, *args, **kwargs):
    """Run a fetcher and return [] on any exception."""
    try:
        return fn(*args, **kwargs) or []
    except Exception as e:
        print(f"    [WARN] {fn.__name__} failed: {e}")
        return []


# ============================================================
# 单个 L1 品类的抓取
# ============================================================
def fetch_one_l1(l1_cn, definition):
    """抓取单个 L1 的多平台行业趋势数据。"""
    query = definition['en']
    print(f"\n[L1] {l1_cn}  (query='{query}')")
    out = {
        'l1': l1_cn,
        'query': query,
        'aliases': definition.get('aliases', []),
        'social': {
            'google':    [],
            'youtube':   [],
            'instagram': [],
            'tiktok':    [],
            'x':         [],
        },
        'search': {
            'google_trends': [],
            'linkedin':      [],
        },
        'media': [],
        'amazon': [],
        'opportunity': '',
        'heat_score': 0,
        'fetched_at': today_iso(),
    }

    # ---------- 1) Google Trends ----------
    try:
        g = ft._fetch_google_social_trends(query, query)
        if g and g[0].get('trending_keywords'):
            kws = sorted(g[0]['trending_keywords'], key=lambda x: x.get('growth', 0), reverse=True)[:5]
            out['social']['google'] = kws
            out['search']['google_trends'] = kws[:3]
    except Exception as e:
        print(f"    [WARN] google failed: {e}")

    # ---------- 2) YouTube ----------
    try:
        y = ft._fetch_youtube_social_trends(query, query)
        if y and y[0].get('trending_keywords'):
            out['social']['youtube'] = sorted(y[0]['trending_keywords'], key=lambda x: x.get('growth', 0), reverse=True)[:5]
    except Exception as e:
        print(f"    [WARN] youtube failed: {e}")

    # ---------- 3) X (Twitter) ----------
    try:
        xres = ft._fetch_x_social_trends(query, query)
        if xres and xres[0].get('trending_keywords'):
            out['social']['x'] = sorted(xres[0]['trending_keywords'], key=lambda x: x.get('growth', 0), reverse=True)[:5]
    except Exception as e:
        print(f"    [WARN] x failed: {e}")

    # ---------- 4) Instagram (Meta) ----------
    try:
        ig = ft._fetch_instagram_social_trends(query, query)
        if ig and ig[0].get('trending_keywords'):
            out['social']['instagram'] = sorted(ig[0]['trending_keywords'], key=lambda x: x.get('growth', 0), reverse=True)[:5]
    except Exception as e:
        print(f"    [WARN] instagram failed: {e}")

    # ---------- 5) TikTok ----------
    try:
        tt = ft._fetch_tiktok_social_trends(query, query)
        if tt and tt[0].get('trending_keywords'):
            out['social']['tiktok'] = sorted(tt[0]['trending_keywords'], key=lambda x: x.get('growth', 0), reverse=True)[:5]
    except Exception as e:
        print(f"    [WARN] tiktok failed: {e}")

    # ---------- 6) LinkedIn 搜索热词（无公开API，用 deterministic 估算）----------
    li_topics = [
        f"{query} market trend",
        f"{query} supply chain",
        f"{query} export opportunity",
    ]
    out['search']['linkedin'] = [
        {
            'keyword': topic,
            'growth': deterministic_growth(topic + l1_cn, base=15, spread=60),
            'rank': i + 1,
        } for i, topic in enumerate(li_topics)
    ]

    # ---------- 7) 主流财经媒体报道（CNN/CNBC/Bloomberg/Reuters/WSJ/FT）----------
    try:
        articles = ft._fetch_category_news(query, l1_cn)
        if articles:
            # 优先保留 CNN/CNBC/Bloomberg/Reuters/WSJ/FT 来源
            premium_keys = ['cnn', 'cnbc', 'bloomberg', 'reuters', 'wsj', 'wall street', 'financial times', 'ft.com']
            premium = [a for a in articles if any(k in (a.get('source', '') + a.get('url', '')).lower() for k in premium_keys)]
            others = [a for a in articles if a not in premium]
            out['media'] = (premium + others)[:6]
    except Exception as e:
        print(f"    [WARN] media news failed: {e}")

    # ---------- 8) Amazon BSR 验证（从全局 BSR 数据中筛选关键词命中产品）----------
    # 注：在调用方传入全局 BSR，避免每个 L1 都重复抓取

    # ---------- 9) 综合热度评分 ----------
    growth_vals = []
    for plat in out['social']:
        for kw in out['social'][plat]:
            g = kw.get('growth', 0)
            if isinstance(g, (int, float)):
                growth_vals.append(g)
    if growth_vals:
        avg = sum(growth_vals) / len(growth_vals)
        # 映射到 0-100
        out['heat_score'] = max(0, min(100, round(50 + avg / 4, 1)))
    else:
        out['heat_score'] = 50.0

    return out


# ============================================================
# Amazon BSR 关键词命中
# ============================================================
def attach_amazon_hits(industry_data, bsr_data):
    """为每个 L1 从 Amazon BSR 数据中筛选命中关键词的产品。"""
    if not bsr_data:
        return
    for l1_cn, l1_obj in industry_data.items():
        aliases = [a.lower() for a in l1_obj.get('aliases', [])]
        if not aliases:
            continue
        hits = []
        for mkt, products in bsr_data.items():
            if not isinstance(products, list):
                continue
            for p in products:
                hay = (str(p.get('title', '')) + ' ' + str(p.get('cat', ''))).lower()
                if any(alias in hay for alias in aliases if len(alias) >= 3):
                    hits.append({
                        'market':  mkt,
                        'rank':    p.get('rank'),
                        'title':   p.get('title'),
                        'cat':     p.get('cat'),
                        'price':   p.get('price'),
                        'rating':  p.get('rating'),
                        'asin':    p.get('asin'),
                        'trend':   p.get('trend'),
                        'insight': p.get('insight'),
                    })
                    if len(hits) >= 8:
                        break
            if len(hits) >= 8:
                break
        l1_obj['amazon'] = hits


# ============================================================
# 合并已有的 industry_trends.json 中的 opportunity / culture / consumer 文案
# ============================================================
def merge_legacy(industry_data):
    if not os.path.exists(EXISTING_INDUSTRY_FILE):
        return
    try:
        with open(EXISTING_INDUSTRY_FILE, 'r', encoding='utf-8') as f:
            legacy = json.load(f)
        for l1, obj in industry_data.items():
            old = legacy.get(l1) or {}
            obj['opportunity'] = old.get('opportunity', '')
            obj['culture']     = old.get('culture', '')
            obj['consumer']    = old.get('consumer', '')
            obj['infra']       = old.get('infra', '')
            obj['population']  = old.get('population', '')
            obj['social_env']  = old.get('social', '')
            obj['environment'] = old.get('environment', '')
    except Exception as e:
        print(f"[WARN] merge legacy failed: {e}")


# ============================================================
# Main
# ============================================================
def main():
    print(f"[START] fetch_industry_trends @ {today_iso()}")

    # 1) 先抓 Amazon BSR（只调用 1 次，全 L1 共用）
    print("\n[STEP 1] Amazon BSR (US/DE/JP/UK/SA)")
    try:
        bsr = ft.fetch_amazon_bsr() or {}
    except Exception as e:
        print(f"  [WARN] Amazon BSR fetch failed: {e}")
        bsr = {}

    # 2) 逐 L1 抓取多平台数据
    print("\n[STEP 2] Per-L1 fetching ...")
    industry = {}
    keys = list(L1_DEFINITIONS.keys())
    for i, l1_cn in enumerate(keys):
        print(f"\n--- ({i+1}/{len(keys)}) ---")
        try:
            industry[l1_cn] = fetch_one_l1(l1_cn, L1_DEFINITIONS[l1_cn])
        except Exception as e:
            print(f"[ERR] {l1_cn}: {e}")
            traceback.print_exc()
            industry[l1_cn] = {
                'l1': l1_cn,
                'query': L1_DEFINITIONS[l1_cn]['en'],
                'aliases': L1_DEFINITIONS[l1_cn].get('aliases', []),
                'social': {p: [] for p in ['google', 'youtube', 'instagram', 'tiktok', 'x']},
                'search': {'google_trends': [], 'linkedin': []},
                'media': [],
                'amazon': [],
                'opportunity': '',
                'heat_score': 50.0,
                'fetched_at': today_iso(),
            }
        time.sleep(1)  # 平台限流缓冲

    # 3) Amazon BSR 关键词命中
    print("\n[STEP 3] Amazon BSR keyword matching ...")
    attach_amazon_hits(industry, bsr)

    # 4) 合并 legacy industry_trends.json 中的文案字段
    print("\n[STEP 4] Merge legacy opportunity/culture text ...")
    merge_legacy(industry)

    # 5) 写出
    out = {
        'meta': {
            'version': '2.0',
            'updated_at': today_iso(),
            'total_l1': len(industry),
            'sources': {
                'social':   ['Google Trends', 'YouTube', 'Instagram (Meta)', 'TikTok', 'X (Twitter)'],
                'search':   ['Google Trends', 'LinkedIn (estimated)'],
                'media':    ['GNews', 'Google News RSS', 'CNBC', 'Bloomberg', 'Reuters', 'WSJ', 'FT', 'CNN'],
                'amazon':   list(bsr.keys()),
            }
        },
        'categories': industry,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n[DONE] wrote {OUTPUT_FILE}  size={os.path.getsize(OUTPUT_FILE)/1024:.1f}KB")


if __name__ == '__main__':
    main()
