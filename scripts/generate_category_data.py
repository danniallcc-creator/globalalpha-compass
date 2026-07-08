#!/usr/bin/env python3
"""
Generate base JSON data files for all L2 categories from taxonomy.

Reads taxonomy.json and produces:
  - data/categories/{l1_slug}/{l2_slug}.json for each L2 category (466 files)
  - data/category_index.json as a master index for quick lookup

Idempotent: safe to re-run.
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
TAXONOMY_FILE = DATA_DIR / "taxonomy.json"
CATEGORIES_DIR = DATA_DIR / "categories"
INDEX_FILE = DATA_DIR / "category_index.json"

# ---------------------------------------------------------------------------
# L1 English name mapping  (keyed by name_cn from taxonomy)
# ---------------------------------------------------------------------------
L1_EN_MAP = {
    "个人护理及家庭清洁": "Personal Care & Household Cleaning",
    "买家物流市场": "Buyer Logistics Market",
    "五金工具": "Hardware & Tools",
    "代理采购": "Agency Procurement",
    "仪器仪表": "Instruments & Meters",
    "传动": "Power Transmission",
    "健康护理": "Health Care",
    "农业": "Agriculture",
    "办公文教用品": "Office & Education Supplies",
    "包装印刷": "Packaging & Printing",
    "化学品": "Chemicals",
    "医疗器械和用品": "Medical Devices & Supplies",
    "可再生能源": "Renewable Energy",
    "商业设备及机械": "Commercial Equipment & Machinery",
    "商务服务": "Business Services",
    "安全用品": "Safety Products",
    "安防": "Security & Protection",
    "宠物用品及食品": "Pet Supplies & Food",
    "家具": "Furniture",
    "家居园艺": "Home & Garden",
    "家用电器": "Home Appliances",
    "工业机械": "Industrial Machinery",
    "工程及建材机械": "Engineering & Building Material Machinery",
    "建材与房地产": "Building Materials & Real Estate",
    "开发与技术服务": "Development & Technical Services",
    "整车及交通工具": "Vehicles & Transportation",
    "服装及配饰": "Apparel & Accessories",
    "检验检测与认证": "Testing, Inspection & Certification",
    "橡胶与塑料制品": "Rubber & Plastics",
    "母婴&玩具": "Mother, Baby & Toys",
    "汽车用品、电子及工具设备": "Auto Accessories, Electronics & Tools",
    "汽车零配件": "Auto Parts & Accessories",
    "消费电子": "Consumer Electronics",
    "灯具照明": "Lights & Lighting",
    "物料搬运": "Material Handling",
    "环保": "Environmental Protection",
    "珠宝眼镜手表及配饰": "Jewelry, Eyewear, Watches & Accessories",
    "电子元器件、配件及通讯": "Electronic Components, Accessories & Telecom",
    "电气设备及用品": "Electrical Equipment & Supplies",
    "礼品与工艺品": "Gifts & Crafts",
    "箱包": "Luggage & Bags",
    "美妆": "Beauty & Cosmetics",
    "设计服务": "Design Services",
    "运动及娱乐": "Sports & Entertainment",
    "金属与合金": "Metals & Alloys",
    "面料及纺织原材料": "Fabrics & Textile Raw Materials",
    "鞋靴及配饰": "Footwear & Accessories",
    "食品及饮料": "Food & Beverage",
    "运动户外鞋服及装备": "Sportswear & Outdoor Apparel",
}

# ---------------------------------------------------------------------------
# HS Code mapping by L1 name_cn  (default per L1)
# ---------------------------------------------------------------------------
HS_CODE_MAP = {
    "个人护理及家庭清洁": "34xx",
    "买家物流市场": "99xx",
    "五金工具": "82xx",
    "代理采购": "99xx",
    "仪器仪表": "90xx",
    "传动": "84xx",
    "健康护理": "21xx",
    "农业": "07xx",
    "办公文教用品": "96xx",
    "包装印刷": "48xx",
    "化学品": "28xx",
    "医疗器械和用品": "90xx",
    "可再生能源": "85xx",
    "商业设备及机械": "84xx",
    "商务服务": "99xx",
    "安全用品": "63xx",
    "安防": "85xx",
    "宠物用品及食品": "23xx",
    "家具": "94xx",
    "家居园艺": "69xx",
    "家用电器": "85xx",
    "工业机械": "84xx",
    "工程及建材机械": "84xx",
    "建材与房地产": "68xx",
    "开发与技术服务": "99xx",
    "整车及交通工具": "87xx",
    "服装及配饰": "62xx",
    "检验检测与认证": "99xx",
    "橡胶与塑料制品": "39xx",
    "母婴&玩具": "95xx",
    "汽车用品、电子及工具设备": "87xx",
    "汽车零配件": "87xx",
    "消费电子": "85xx",
    "灯具照明": "94xx",
    "物料搬运": "84xx",
    "环保": "84xx",
    "珠宝眼镜手表及配饰": "71xx",
    "电子元器件、配件及通讯": "85xx",
    "电气设备及用品": "85xx",
    "礼品与工艺品": "95xx",
    "箱包": "42xx",
    "美妆": "33xx",
    "设计服务": "99xx",
    "运动及娱乐": "95xx",
    "金属与合金": "72xx",
    "面料及纺织原材料": "50xx",
    "鞋靴及配饰": "64xx",
    "食品及饮料": "16xx",
    "运动户外鞋服及装备": "65xx",
}

# ---------------------------------------------------------------------------
# L2-specific HS code overrides  (keyed by L2 cn name)
# ---------------------------------------------------------------------------
L2_HS_OVERRIDES = {
    # -- Agriculture --
    "谷物": "10xx",
    "豆类": "07xx",
    "新鲜水果": "08xx",
    "新鲜蔬菜": "07xx",
    "蘑菇与松露": "07xx",
    "冷冻产品": "07xx",
    "动物制品": "05xx",
    "木材原料": "44xx",
    "观赏植物": "06xx",
    "农用设备": "84xx",
    "工业大麻产品": "53xx",
    # -- Food & Beverage --
    "乳制品": "04xx",
    "海鲜": "03xx",
    "肉类及家禽": "02xx",
    "饮料": "22xx",
    "调味料及调味品": "09xx",
    "蜂蜜及蜂蜜制品": "04xx",
    "坚果及干果": "08xx",
    "果蔬产品": "20xx",
    "罐装食品": "20xx",
    "即食食品": "19xx",
    "焙烤食品": "19xx",
    "糖果糕点": "18xx",
    "谷物制品": "19xx",
    "零食": "20xx",
    "食品添加剂": "21xx",
    "动植物油": "15xx",
    # -- Textiles & Raw Materials --
    "面料": "52xx",
    "纱": "52xx",
    "纤维": "55xx",
    "皮革": "41xx",
    "毛皮": "43xx",
    "羽毛和羽绒": "05xx",
    "纺织配件": "84xx",
    # -- Metals & Alloys --
    "不锈钢": "73xx",
    "碳钢": "72xx",
    "合金钢": "72xx",
    "有色金属": "76xx",
    "铁和铁制品": "73xx",
    "金属丝网": "73xx",
    "金属和金属制品": "73xx",
    # -- Electronics & Components --
    "集成电路": "85xx",
    "传感器": "85xx",
    "显示屏、数码标识、光电子": "85xx",
    "通讯": "85xx",
    "电源": "85xx",
    "继电器": "85xx",
    "连接器及配件": "85xx",
    "电路板及组装": "85xx",
    # -- Vehicles --
    "乘用车": "87xx",
    "卡车": "87xx",
    "公共汽车": "87xx",
    "摩托车及脚踏车": "87xx",
    "三轮车": "87xx",
    "ATV 与 UTV": "87xx",
    "拖车": "87xx",
    "应急车辆": "87xx",
    # -- Furniture --
    "家居家具": "94xx",
    "商用家具": "94xx",
    "户外家具": "94xx",
    "家具五金": "83xx",
    "婴童家具": "94xx",
    # -- Building Materials --
    "瓷砖及配件": "69xx",
    "石材": "68xx",
    "建筑工业玻璃": "70xx",
    "木材": "44xx",
    "防水材料": "68xx",
    "隔热材料": "68xx",
    "防火材料": "68xx",
    "隔音材料": "68xx",
    "建筑板材": "68xx",
    "门、窗及其配件": "73xx",
    "天花板": "68xx",
    "浴室和厨房产品": "69xx",
    "电梯和自动扶梯": "84xx",
    "空调系统及配件": "84xx",
    # -- Hardware & Tools --
    "紧固件": "73xx",
    "阀门": "84xx",
    "泵及配件": "84xx",
    "钻头": "82xx",
    "研磨材料": "68xx",
    # -- Packaging --
    "塑料包装": "39xx",
    "纸质包装": "48xx",
    "金属包装": "73xx",
    "玻璃包装": "70xx",
    "木、竹包装": "44xx",
    # -- Chemicals --
    "农用化学品": "38xx",
    "能源": "27xx",
    "无机化学品": "28xx",
    "基本有机原料": "29xx",
    "油漆涂料": "32xx",
    "颜料和染料": "32xx",
    # -- Renewable Energy --
    "太阳能产品": "85xx",
    "太阳能应用": "85xx",
    "电池": "85xx",
    "储能系统": "85xx",
    "风力发电产品": "85xx",
    "氢能": "85xx",
    # -- Rubber & Plastics --
    "塑料制品": "39xx",
    "塑料原材料": "39xx",
    "橡胶制品": "40xx",
    "橡胶原料": "40xx",
    # -- Health Care --
    "保健食品": "21xx",
    "提取物": "13xx",
    "保健设备": "90xx",
    "按摩用品": "90xx",
    # -- Jewelry / Watches --
    "高级珠宝": "71xx",
    "时尚饰品": "71xx",
    "手表": "91xx",
    "手表零部件": "91xx",
    "眼镜": "90xx",
    "眼镜配件": "90xx",
    # -- Lighting --
    "灯泡、灯管": "85xx",
    "太阳能照明": "94xx",
    # -- Home Appliances --
    "冰箱冰柜": "84xx",
    "热水器": "84xx",
    "供暖及制冷电器": "84xx",
    "水处理设备": "84xx",
    # -- Auto Parts --
    "汽车引擎": "84xx",
    "汽车传动系统": "87xx",
    "汽车制动系统": "87xx",
    "汽车悬架系统": "87xx",
    "汽车转向系统": "87xx",
    "汽车照明系统": "85xx",
    "汽车电器系统": "85xx",
    "汽车覆盖件系统": "87xx",
    "汽车改装零件": "87xx",
    "车轮、轮胎及配件": "40xx",
    "冷却系统": "87xx",
    "空调系统": "87xx",
    "新能源汽车零部件及配件": "85xx",
    # -- Consumer Electronics --
    "计算机软硬件": "84xx",
    "手机与配件": "85xx",
    "充电器，电池和电源": "85xx",
    "相机，无人机配件": "90xx",
    "耳塞和耳机": "85xx",
    # -- Sports & Entertainment --
    "乐器": "92xx",
    "健身及塑形": "95xx",
    "垂钓": "95xx",
    "自行车": "87xx",
    "球类运动装备": "95xx",
    "露营及登山": "63xx",
    "高尔夫": "95xx",
    "冰雪运动": "95xx",
    "水上运动": "95xx",
    "游乐园设施": "95xx",
    # -- Mother, Baby & Toys --
    "婴儿服装": "62xx",
    "儿童服装": "62xx",
    "幼儿服装": "62xx",
    "童鞋": "64xx",
    "孕产用品": "62xx",
    # -- Bags --
    "女士包袋": "42xx",
    "男士包袋": "42xx",
    "背包": "42xx",
    "行李箱及旅行包": "42xx",
    "钱包和卡包": "42xx",
    # -- Safety --
    "个人防护设备": "63xx",
    "消防用品": "84xx",
    "道路安全设施": "83xx",
    # -- Pet --
    "宠物食品": "23xx",
    # -- Shoes --
    "功能鞋": "64xx",
    "女鞋": "64xx",
    "男鞋": "64xx",
    "户外用鞋": "64xx",
    # -- Sportswear & Outdoor --
    "运动户外护具及用品": "65xx",
    "运动户外鞋": "64xx",
    "运动户外箱包": "42xx",
    "运动户外服": "61xx",
    "运动户外装备": "62xx",
}

# ---------------------------------------------------------------------------
# Industry analysis templates by L1  (rich templates for key categories)
# ---------------------------------------------------------------------------
INDUSTRY_TEMPLATES = {
    "食品及饮料": {
        "culture": "Food culture varies significantly across target markets, with growing demand for halal, kosher, and organic certifications. Asian cuisines are gaining popularity globally, creating opportunities for authentic ingredients and products. Regional taste preferences (sweet, spicy, umami) shape product localization strategies.",
        "consumer": "Health-conscious consumption is driving demand for organic, low-sugar, and functional foods. Convenience foods and ready-to-eat meals are growing rapidly in urban markets. Clean label and natural ingredients are increasingly preferred. Premium imported foods gaining status appeal in emerging markets.",
        "infra": "Cold chain logistics and food-grade packaging infrastructure are critical. FDA/EU food safety standards require HACCP certification. Traceability systems and blockchain are becoming standard. Port inspection and quarantine procedures vary by country.",
        "population": "Growing middle class in emerging markets drives premium food demand. Aging populations in developed markets seek functional and fortified foods. Urbanization increases demand for convenience products. Millennial and Gen Z consumers are more adventurous eaters.",
        "social": "Food safety scandals have heightened consumer awareness. Social media influences food trends and viral products. Sustainability and ethical sourcing are increasingly important to consumers. Plant-based and alternative protein movements gaining traction.",
        "environment": "Sustainable agriculture and carbon-neutral production are becoming competitive advantages. Water usage and waste management are key concerns. Organic farming practices are increasingly valued. Deforestation-free supply chain commitments expected.",
        "opportunity": "Cross-border e-commerce enables direct-to-consumer food exports. Emerging markets offer growth potential. Functional foods and health supplements are high-growth segments. Ready-to-drink beverages and snackification trends creating new categories."
    },
    "个人护理及家庭清洁": {
        "culture": "Beauty standards and personal care routines vary by region. K-beauty and J-beauty trends influence global markets. Natural and organic ingredients are increasingly preferred across cultures. Traditional herbal ingredients gaining renewed interest in Asian markets.",
        "consumer": "Premiumization trend with consumers willing to pay more for quality. Demand for dermatologist-tested and hypoallergenic products. Subscription models gaining traction for replenishable items. Multi-functional products appeal to time-pressed consumers.",
        "infra": "GMP certification and cosmetic safety assessments required. REACH compliance for EU market. Stability testing and preservative efficacy testing are standard requirements. Product notification portals (CPNP for EU, FDA VCRP for US).",
        "population": "Aging populations drive anti-aging product demand. Younger demographics seek innovative and trendy products. Male grooming market is expanding rapidly. Family-size and bulk packaging popular in high-birth-rate markets.",
        "social": "Clean beauty movement emphasizes transparency in ingredients. Cruelty-free and vegan certifications increasingly important. Influencer marketing drives product discovery and sales. TikTok and Instagram drive viral product trends.",
        "environment": "Sustainable packaging and refillable containers gaining popularity. Microplastic bans affecting formulation. Biodegradable and eco-friendly formulations becoming standard. Concentrated formulas reducing shipping weight and carbon footprint.",
        "opportunity": "Emerging markets show strong growth potential. Private label and white-label opportunities. Cross-border e-commerce channels expanding rapidly. Probiotic and fermented ingredients trending globally."
    },
    "五金工具": {
        "culture": "DIY culture is strong in Western markets, driving demand for quality hand tools. Professional tradespeople prioritize durability and brand reputation. Regional preferences for tool types, sizes, and measurement systems (metric vs. imperial).",
        "consumer": "Professional users demand high-quality, durable tools with warranties. DIY enthusiasts seek value and versatility in multi-tools. Brand loyalty is strong in professional segments. Online reviews and YouTube demonstrations heavily influence purchasing decisions.",
        "infra": "Manufacturing hubs in China, Germany, Japan, and Taiwan. Distribution through wholesalers, big-box retailers, and e-commerce. Quality certifications like ISO, DIN, ANSI, JIS standards. Calibration and testing infrastructure important.",
        "population": "Construction booms and infrastructure projects drive demand. Renovation and remodeling markets are cyclical with housing. Urbanization increases demand for professional and consumer-grade tools.",
        "social": "Maker movement and DIY culture expanding through social media. Sustainability concerns favor repairable and long-lasting tools. Online tutorials and maker communities drive tool adoption and brand awareness.",
        "environment": "Recycled materials in tool manufacturing. Energy-efficient production processes. Sustainable packaging initiatives. Tool lending libraries and sharing economy concepts emerging.",
        "opportunity": "Smart tools with IoT integration and digital measurement. Emerging market infrastructure development driving demand. E-commerce direct-to-consumer channels reducing distribution costs. Cordless battery platform ecosystems creating brand lock-in."
    },
    "消费电子": {
        "culture": "Tech adoption rates vary by market. Early adopters in developed markets seek cutting-edge features. Price sensitivity dominates in emerging markets. Brand perception varies regionally with strong local brand preferences.",
        "consumer": "Rapid product replacement cycles drive demand. Feature differentiation is key to competitive advantage. Online reviews and specification comparisons heavily researched. Refurbished and certified pre-owned markets are growing.",
        "infra": "FCC/CE/UL certification required for market access. Supply chain complexity with component sourcing from multiple countries. E-waste regulations affecting design and end-of-life management. Fast logistics for product launches.",
        "population": "Youth demographics drive smartphone and gadget adoption. Digital nomad lifestyle creates demand for portable devices. Remote work increases demand for home office electronics and peripherals.",
        "social": "Social media influencers and tech reviewers drive product trends. Privacy and data security concerns growing among consumers. Digital wellbeing and screen time management movement emerging.",
        "environment": "Right-to-repair legislation gaining momentum globally. Conflict mineral regulations (Dodd-Frank, EU Conflict Minerals Regulation). Energy efficiency standards (Energy Star, EU Energy Label). E-waste takeback programs.",
        "opportunity": "IoT and smart home devices ecosystem expansion. AR/VR hardware development. Emerging market smartphone penetration growth. Sustainable and modular electronics design. AI-powered devices and features."
    },
    "服装及配饰": {
        "culture": "Fashion trends vary significantly by region and culture. Modest fashion growing rapidly in Muslim-majority markets. Streetwear and athleisure are global trends. Traditional and ethnic wear maintains strong demand in specific markets.",
        "consumer": "Fast fashion vs. sustainable fashion tension defining the market. Size inclusivity increasingly important. Online shopping dominant with high return rates (20-40%). Brand storytelling and values matter to younger consumers.",
        "infra": "Textile labeling requirements (fiber content, care instructions). REACH compliance for chemicals used in production. OEKO-TEX and GOTS certifications valued by retailers. Manufacturing concentrated in Asia, Bangladesh, Vietnam, Cambodia.",
        "population": "Gen Z and Millennials drive trend cycles. Plus-size market significantly underserved. Gender-neutral fashion emerging as a segment. Aging populations seek comfort, ease of dressing, and functionality.",
        "social": "Sustainability and ethical production concerns paramount. Body positivity movement reshaping sizing. Influencer and celebrity fashion influence amplified by social media. Rental, resale, and second-hand markets growing rapidly.",
        "environment": "Circular fashion and textile recycling initiatives. Water usage in cotton and dyeing processes. Microfiber pollution from synthetic fabrics. Carbon footprint transparency and Science-Based Targets expected.",
        "opportunity": "Sustainable and ethical fashion brands gaining market share. Made-to-measure and mass customization technology. Emerging market middle class growth. Athleisure and performance wear continuing expansion."
    },
    "家居园艺": {
        "culture": "Home decoration styles vary by region (Scandinavian, Mediterranean, Asian, Industrial, etc.). Gardening is a popular hobby in Western markets. Feng shui and cultural beliefs influence decor choices in Asian markets.",
        "consumer": "Home improvement spending correlated with housing market conditions. Seasonal demand for garden and outdoor products. Smart home integration increasingly desired. Pinterest and Instagram inspiration drives purchases.",
        "infra": "Product safety certifications (CPSC, CE) required. Chemical compliance for garden products (pesticides, fertilizers). Large and bulky items require efficient logistics and warehousing. Assembly and installation services valued.",
        "population": "Urbanization drives apartment-friendly and space-saving products. Homeownership rates affect spending levels. Aging populations need accessible and easy-maintenance solutions. Multi-generational households influence product needs.",
        "social": "Work-from-home trend increases home improvement spending. Instagram-worthy aesthetics drive design trends. Urban gardening and sustainability movement. Minimalism vs. maximalism design trends cyclic.",
        "environment": "Sustainable materials (bamboo, recycled plastic) and production. Water-efficient garden products and irrigation. Energy-efficient home products. Biodegradable and compostable materials preferred.",
        "opportunity": "Smart home products and IoT integration. Urban gardening and vertical farming solutions. Sustainable and eco-friendly product lines. Outdoor living spaces and garden rooms trending."
    },
    "工业机械": {
        "culture": "Industrial purchasing is relationship-driven with long sales cycles. Quality and reliability prioritized over price. After-sales service, spare parts, and technical support critical. Regional manufacturing standards and preferences.",
        "consumer": "B2B purchasing with multi-stakeholder decision processes. Total cost of ownership (TCO) considered over purchase price. Customization and engineering support often required. Service contracts and maintenance agreements important.",
        "infra": "ISO certifications required for credibility. CE marking for EU market. Installation, commissioning, and training support needed. Spare parts availability and logistics networks are competitive differentiators.",
        "population": "Infrastructure development in emerging markets drives demand. Automation replacing manual labor in developed economies. Skilled labor shortages accelerating automation adoption worldwide.",
        "social": "Industry 4.0 and smart manufacturing transformation. Sustainability and energy efficiency regulations tightening. Reskilling workforce for advanced manufacturing and collaborative robots.",
        "environment": "Energy efficiency standards and carbon reporting requirements. Emissions regulations for industrial processes. Waste reduction, recycling, and circular economy principles in machinery design.",
        "opportunity": "Industry 4.0 integration (IoT, predictive maintenance, digital twins). Emerging market industrialization. Collaborative robotics and automation. Energy-efficient and servo-driven machinery."
    },
    "建材与房地产": {
        "culture": "Building styles and materials vary by region, climate, and tradition. Local building codes and standards mandatory. Cultural preferences for certain materials (wood in Japan, stone in Europe, brick in UK). Green building certifications increasingly valued.",
        "consumer": "Construction industry cycles strongly affect demand. Quality, durability, and compliance critical for liability. Local availability and logistics costs important for heavy materials. Professional contractors vs. DIY segments differ in purchasing behavior.",
        "infra": "Building codes and standard compliance (ASTM, EN, ISO, GB). Third-party testing and certification. Local distribution networks with warehousing for bulky goods. Installation expertise and certified installer training.",
        "population": "Urbanization drives massive construction demand in developing countries. Infrastructure development in emerging markets. Renovation and energy retrofit markets dominant in developed economies.",
        "social": "Sustainable and green building movement (LEED, BREEAM, WELL). Affordable housing initiatives globally. Smart building technologies and BMS integration. Wellness-focused building design (biophilic design).",
        "environment": "Carbon footprint of building materials (embodied carbon). Recycled and bio-based materials gaining traction. Energy efficiency in buildings (Passive House, Net Zero). Construction waste reduction and deconstruction planning.",
        "opportunity": "Green building materials and certifications. Prefabricated and modular construction. Smart building technologies and IoT. Emerging market urbanization and infrastructure spending."
    },
    "医疗器械和用品": {
        "culture": "Healthcare systems vary by country (public vs. private, insurance-based). Traditional medicine integration important in some markets (TCM, Ayurveda). Quality and safety are non-negotiable. Regulatory approval processes are lengthy and costly.",
        "consumer": "B2B purchasing by hospitals, clinics, and group purchasing organizations. Home healthcare and self-monitoring growing rapidly. Insurance coverage and reimbursement affect adoption rates. Evidence-based medicine requires clinical data.",
        "infra": "FDA 510(k) clearance and CE MDR certification required. ISO 13485 quality management system mandatory. Clinical trials and regulatory submissions expensive. Distribution through specialized medical device distributors.",
        "population": "Aging populations dramatically increase healthcare demand globally. Chronic disease prevalence growing (diabetes, cardiovascular). Telemedicine and remote patient monitoring expanding rapidly.",
        "social": "Healthcare cost containment pressure from governments and payers. Patient safety initiatives and adverse event reporting. Medical device traceability requirements (UDI). Cybersecurity concerns for connected devices.",
        "environment": "Medical waste management and sharps disposal. Sustainable packaging and materials for single-use devices. Energy-efficient equipment. Reusable vs. single-use device trade-offs.",
        "opportunity": "Telemedicine and digital health platforms. Emerging market healthcare infrastructure build-out. Home healthcare and point-of-care devices. Minimally invasive surgical devices and robotics."
    },
    "汽车零配件": {
        "culture": "Car culture varies by region (American muscle/trucks, European luxury/performance, Japanese reliability/efficiency). Aftermarket customization popular in US, Japan, Middle East. Brand loyalty strong among enthusiasts.",
        "consumer": "Quality and reliability critical for safety-critical components. Price competition from aftermarket vs. OEM suppliers. Online parts lookup (VIN-based) and ordering growing. Professional installers prefer known brands.",
        "infra": "IATF 16949 quality management mandatory for OEM supply. OEM specifications and PPAP approvals required. Just-in-time delivery to assembly plants. Global supply chain with tier 1/2/3 structure.",
        "population": "Vehicle parc size (total registered vehicles) drives aftermarket demand. EV transition fundamentally affecting parts demand profiles. Aging vehicle population increases repair and replacement needs.",
        "social": "Right-to-repair legislation expanding. Vehicle customization and modification culture. Car sharing and mobility-as-a-service. Autonomous vehicle development reshaping future parts demand.",
        "environment": "Emissions regulations driving technology changes (Euro 7, China 6). EV transition eliminating ICE-specific parts. Lightweight materials for fuel efficiency. End-of-life vehicle recycling regulations (ELV Directive).",
        "opportunity": "EV components and charging infrastructure. Connected car technologies and ADAS sensors. Aftermarket growth for aging vehicle fleets. Emerging market vehicle ownership growth."
    },
    "运动及娱乐": {
        "culture": "Sports popularity varies by region (cricket in South Asia, soccer globally, basketball in US/China). Outdoor recreation culture strong in Western markets. Fitness culture increasingly global through social media.",
        "consumer": "Performance and quality important for serious athletes. Style and aesthetics matter for lifestyle and athleisure segments. Online research, reviews, and comparison influential. Seasonal demand patterns for outdoor sports.",
        "infra": "Product safety standards (CPSC, EN) required. Sport-specific certifications (FIFA, UCI, ITF, etc.). Retail distribution through specialty stores, big-box, and online. E-commerce growing rapidly for sporting goods.",
        "population": "Health and fitness consciousness growing globally. Youth sports participation and parental spending. Active aging population seeking low-impact activities. Urbanization affects activity and venue choices.",
        "social": "Social media fitness influencers and communities. Esports and competitive gaming explosive growth. Outdoor recreation boom post-pandemic. Inclusivity and accessibility in sports and fitness.",
        "environment": "Sustainable materials (recycled ocean plastics, bio-based). Leave No Trace principles for outdoor activities. Carbon-neutral sporting events and products. Water conservation in golf and snow-making.",
        "opportunity": "Home fitness and connected equipment. Outdoor recreation participation growth. Esports equipment and peripherals. Sustainable sports products. Emerging market sports participation and infrastructure."
    },
    "家用电器": {
        "culture": "Cooking traditions influence kitchen appliance preferences (wok burners in Asia, convection ovens in Europe). Laundry habits vary (top-load vs. front-load washers). Climate affects heating/cooling appliance demand.",
        "consumer": "Energy efficiency ratings heavily influence purchasing decisions. Smart features and connectivity increasingly expected. Brand trust important for major appliances. Extended warranties and after-sales service valued.",
        "infra": "Energy Star, EU Energy Label, and MEPS requirements. Safety certifications (UL, CE, CCC). Refrigerant regulations (HFC phase-down). Installation and delivery infrastructure for large appliances.",
        "population": "Urbanization drives compact and multi-function appliance demand. Aging populations need easy-to-use controls. Growing middle class in emerging markets upgrading to modern appliances.",
        "social": "Connected kitchen and smart home ecosystems. Cooking shows and social media drive specialty appliance trends. Minimalist design aesthetics. Voice control and AI assistant integration.",
        "environment": "Energy efficiency standards tightening globally. Refrigerant transitions (R290, R600a). Right-to-repair movement. Circular economy and recyclability requirements.",
        "opportunity": "Smart and connected appliances with AI features. Small kitchen appliance innovation (air fryers, multicookers). Emerging market appliance adoption. Heat pump technology expansion."
    },
    "农业": {
        "culture": "Agricultural practices deeply rooted in local traditions and climate. Dietary preferences drive crop selection. Organic and biodynamic farming gaining prestige. Traditional knowledge combined with modern technology.",
        "consumer": "Food safety and traceability increasingly demanded by consumers. Organic premium pricing accepted in developed markets. Seasonal availability less relevant with global supply chains. Plant-based protein trends affecting crop demand.",
        "infra": "Phytosanitary certification and inspection required for export. Cold chain for fresh produce. Storage and warehousing for grains and dry goods. Transportation infrastructure from farm to port.",
        "population": "Growing global population driving food production demand. Urbanization reducing agricultural labor. Aging farmer populations in developed countries. Youth migration from rural areas.",
        "social": "Farm-to-table movement and local food systems. Fair trade and ethical sourcing certifications. GMO debate and labeling requirements. Precision agriculture and AgTech innovation.",
        "environment": "Sustainable farming practices (regenerative agriculture, no-till). Water conservation and efficient irrigation. Soil health and biodiversity. Carbon sequestration in agricultural land.",
        "opportunity": "Precision agriculture and smart farming technology. High-value specialty crops for export. Organic and certified sustainable products. Agricultural technology and automation."
    },
    "化学品": {
        "culture": "Chemical industry standards and regulations vary significantly by market. Responsible care and stewardship increasingly expected. Technical expertise required for safe handling and application. Regional chemical manufacturing clusters.",
        "consumer": "B2B purchasing with technical specification requirements. Safety data sheets (SDS) mandatory. Regulatory compliance (REACH, TSCA) is a prerequisite. Long-term supply contracts common.",
        "infra": "REACH registration (EU) and TSCA compliance (US) required. GHS labeling and classification. Transport regulations (ADR, IMDG, IATA). Specialized warehousing and handling facilities.",
        "population": "Industrial development drives chemical demand. Urbanization increases construction chemical needs. Agricultural intensification requires agrochemicals. Pharmaceutical industry growth.",
        "social": "Green chemistry and sustainable alternatives movement. Chemical safety and environmental awareness growing. Worker safety and occupational health. Community right-to-know regulations.",
        "environment": "Strict emissions and discharge regulations. Persistent organic pollutant (POP) restrictions. Circular economy for chemical products. Bio-based and renewable chemical alternatives.",
        "opportunity": "Green chemistry and bio-based chemicals. Specialty chemicals for electronics and batteries. Water treatment chemicals for scarcity solutions. Advanced materials and nanomaterials."
    },
    "美妆": {
        "culture": "Beauty ideals vary dramatically by culture (skin whitening in Asia, tanning in Western markets). K-beauty multi-step routines influential globally. Clean beauty and minimalism trending. Traditional and herbal ingredients valued in many markets.",
        "consumer": "Premiumization with willingness to pay for proven results. Ingredient literacy increasing (retinol, niacinamide, hyaluronic acid). Social media and influencer reviews drive purchases. Trial sizes and discovery sets popular.",
        "infra": "Cosmetic product safety assessment required (EU CPNP, FDA). INCI ingredient labeling mandatory. Animal testing bans (EU, and expanding). GMP manufacturing facilities required for quality assurance.",
        "population": "Male grooming and skincare expanding. Gen Z driving early adoption of skincare routines. Aging populations fueling anti-aging market. Diverse beauty standards across demographic groups.",
        "social": "Inclusivity and diversity in shade ranges and marketing. Clean beauty and transparency movement. TikTok beauty trends creating viral product demand. Cruelty-free and vegan certifications important.",
        "environment": "Sustainable packaging (refillable, recyclable, PCR materials). Reef-safe sunscreen regulations. Microplastic ingredient bans. Carbon-neutral beauty brand commitments.",
        "opportunity": "Inclusive beauty products for diverse skin tones and types. Men's skincare and cosmetics. Clean and clinical beauty hybrid. Beauty tech devices and personalization."
    },
    "包装印刷": {
        "culture": "Packaging design aesthetics vary by market (minimalist in Japan, bold in US). Cultural color associations important (red/gold in China, green for eco). Luxury packaging expectations differ by region.",
        "consumer": "Unboxing experience increasingly important for e-commerce. Sustainable packaging strongly preferred by consumers. Convenience features (resealable, easy-open) valued. Clear labeling and information required.",
        "infra": "Food contact material compliance (FDA, EU 10/2011). FSC/PEFC certification for paper packaging. Recycling infrastructure and EPR schemes. Printing technology and color management standards.",
        "population": "E-commerce growth driving packaging demand. Single-serve packaging for smaller households. Convenience packaging for busy urban consumers. Aging populations need easy-to-open designs.",
        "social": "Anti-plastic sentiment and plastic-free alternatives. Brand sustainability storytelling through packaging. Social media-worthy unboxing experiences. Transparency in packaging materials and recyclability.",
        "environment": "Extended Producer Responsibility (EPR) regulations expanding. Recycled content requirements. Compostable and biodegradable materials. Lightweighting to reduce material usage and transport emissions.",
        "opportunity": "Sustainable and smart packaging solutions. Active and intelligent packaging. E-commerce optimized packaging design. Personalized and digital printing on packaging."
    },
    "整车及交通工具": {
        "culture": "Vehicle preferences vary by market (SUVs in US, compact cars in Europe/Japan, two-wheelers in SE Asia). Status symbol associated with vehicle brands. Electric vehicle adoption culturally more accepted in some markets.",
        "consumer": "Total cost of ownership (fuel, maintenance, insurance) considered. Online research and comparison extensive. Brand heritage and reliability reputation important. EV range anxiety still a barrier in some markets.",
        "infra": "Homologation and type approval required (ECE, DOT, CCC). Emissions testing and certification. Dealer networks and after-sales service infrastructure. Charging infrastructure for EVs.",
        "population": "Urbanization driving demand for compact and electric vehicles. Growing middle class in emerging markets upgrading to personal vehicles. Aging populations need accessible vehicle features.",
        "social": "EV transition and climate change awareness. Autonomous vehicle development. Mobility-as-a-service and ride-sharing. Vehicle connectivity and over-the-air updates.",
        "environment": "Emissions standards tightening (Euro 7, China 6d, EPA Tier 4). Battery recycling and second-life applications. Sustainable manufacturing. Carbon-neutral production targets.",
        "opportunity": "Electric vehicles and charging infrastructure. Connected and autonomous vehicles. Emerging market vehicle ownership growth. Micro-mobility and last-mile delivery vehicles."
    },
    "橡胶与塑料制品": {
        "culture": "Plastic usage acceptance varies by market. Anti-plastic sentiment stronger in Europe. Rubber products associated with industrial quality. Regional material preferences and standards.",
        "consumer": "B2B purchasing with specification requirements. Recycled content increasingly demanded. Quality consistency critical for manufacturing inputs. Price sensitivity for commodity grades.",
        "infra": "REACH compliance for chemical substances. FDA food contact approval where applicable. Material testing and certification. Recycling and waste management infrastructure.",
        "population": "Industrial development drives demand. Construction growth increases plastic building material usage. Packaging industry evolution. Automotive lightweighting trend.",
        "social": "Single-use plastic bans expanding globally. Circular economy and recycling initiatives. Bio-based and biodegradable alternatives. Extended Producer Responsibility legislation.",
        "environment": "Plastic pollution crisis driving regulation. Ocean plastic cleanup and recycling. Carbon footprint of petrochemical-based plastics. Bio-based and compostable alternatives development.",
        "opportunity": "Recycled and bio-based plastics. High-performance engineering plastics. Plastic alternatives and substitutes. Advanced recycling technologies (chemical recycling)."
    },
    "可再生能源": {
        "culture": "Renewable energy adoption driven by policy and economics. Solar culturally accepted in sun-rich regions. Wind energy landscape acceptance varies. Green energy branding increasingly important.",
        "consumer": "Levelized cost of energy (LCOE) drives adoption. Government incentives and feed-in tariffs important. Corporate PPA and sustainability commitments growing. Residential solar adoption increasing.",
        "infra": "IEC/UL certification for equipment. Grid connection standards and codes. Installation and maintenance workforce. Supply chain for critical minerals and materials.",
        "population": "Energy demand growth in developing countries. Urbanization driving distributed energy. Rural electrification through off-grid solar. Green job creation and workforce development.",
        "social": "Climate change urgency driving renewable adoption. Energy independence and security concerns. Community energy and cooperative models. Just transition for fossil fuel workers.",
        "environment": "Lifecycle carbon assessment of renewable technologies. Battery and panel recycling challenges. Land use and biodiversity considerations. Water usage in some renewable technologies.",
        "opportunity": "Energy storage integration and grid services. Green hydrogen production. Floating solar and offshore wind. Emerging market renewable energy deployment."
    },
    "安全用品": {
        "culture": "Safety culture maturity varies by market. Regulatory-driven demand in developed countries. Voluntary adoption increasing in emerging markets. Industry-specific safety standards and requirements.",
        "consumer": "Compliance-driven purchasing (mandatory PPE requirements). Quality and certification critical for liability protection. Comfort and usability increasingly valued. Brand trust important for safety-critical products.",
        "infra": "ANSI/ISEA, EN, and ISO standards compliance. Third-party testing and certification. Distribution through safety distributors and industrial suppliers. Training and fit-testing services.",
        "population": "Workforce size and industry mix drive demand. Construction and manufacturing employment. Aging workforce needing ergonomic solutions. Growing gig economy safety needs.",
        "social": "Worker safety awareness and rights. Vision Zero and safety culture movements. Mental health and wellness in workplace safety. Technology-enabled safety monitoring.",
        "environment": "Sustainable and recyclable PPE materials. Single-use PPE waste management. Eco-friendly safety product alternatives. Carbon footprint of safety equipment manufacturing.",
        "opportunity": "Smart PPE with IoT sensors. Emerging market safety regulation adoption. Women-specific PPE design. Sustainable and reusable safety products."
    },
    "安防": {
        "culture": "Security concerns and surveillance acceptance vary by culture. Privacy regulations (GDPR) affect deployment in Europe. Smart city initiatives driving adoption in Asia. Physical security vs. cybersecurity integration.",
        "consumer": "Risk assessment drives system specification. Integration with existing infrastructure important. Remote monitoring and mobile access expected. Cybersecurity of security systems increasingly scrutinized.",
        "infra": "ONVIF interoperability standards. EN 50131 for alarms, EN 62676 for video surveillance. Network infrastructure for IP-based systems. Professional installation and monitoring services.",
        "population": "Urbanization increases security needs. Aging populations need assisted living monitoring. Population density affects surveillance requirements. Tourism and event security demand.",
        "social": "Privacy vs. security debate ongoing. Facial recognition controversy. Community policing and neighborhood watch programs. Smart home security integration.",
        "environment": "Energy-efficient security devices. Solar-powered outdoor cameras and sensors. Sustainable manufacturing practices. E-waste from security system upgrades.",
        "opportunity": "AI-powered video analytics and threat detection. Smart city and IoT security integration. Cybersecurity convergence. Cloud-based security services and VSaaS."
    },
    "家具": {
        "culture": "Furniture styles vary by region (Scandinavian, Italian, Japanese, American). Space constraints in urban Asian apartments vs. large US homes. Cultural significance of certain furniture types (dining tables, tea tables).",
        "consumer": "Quality, durability, and comfort key factors. Online furniture purchasing growing despite touch-and-feel preference. Assembly and delivery services expected. Customization and made-to-order gaining popularity.",
        "infra": "BIFMA, EN, and ISO standards compliance. Flammability testing (California TB 117). Chemical emissions testing (CARB, GREENGUARD). Flat-pack logistics and last-mile delivery infrastructure.",
        "population": "Urbanization drives demand for compact and multi-functional furniture. Homeownership rates affect furniture spending. Aging populations need accessible and ergonomic designs. Co-living spaces need durable furnishings.",
        "social": "Work-from-home driving home office furniture demand. Instagram and Pinterest aesthetics influence. Sustainable and second-hand furniture market growing. Fast furniture backlash and quality movement.",
        "environment": "FSC-certified wood sourcing. Formaldehyde and VOC emissions regulations. Recyclable and circular furniture design. Carbon footprint of furniture manufacturing and shipping.",
        "opportunity": "Smart furniture with integrated charging and adjustability. Sustainable and circular furniture models. Home office and ergonomic solutions. Outdoor and garden furniture growth."
    },
    "礼品与工艺品": {
        "culture": "Gift-giving traditions deeply rooted in cultures worldwide. Religious and cultural significance of certain gifts. Handicraft traditions important cultural heritage. Corporate gifting customs vary by region.",
        "consumer": "Personalization and uniqueness valued. Seasonal demand peaks (holidays, festivals). Experience gifts competing with physical products. Online gift discovery and direct shipping growing.",
        "infra": "General product safety compliance required. Material composition and origin labeling. Gift packaging and presentation important. E-commerce fulfillment with gift wrapping options.",
        "population": "Aging populations with disposable income for gifts. Younger consumers seeking experiential and ethical gifts. Cultural diversity creating demand for diverse gift options.",
        "social": "Experiential and charitable giving trends. Sustainable and fair-trade gifts preferred. Social media gift guides and recommendations. Subscription box gifting model growing.",
        "environment": "Sustainable and eco-friendly gift materials. Minimal and recyclable gift packaging. Carbon-neutral shipping options. Locally made and artisan products valued.",
        "opportunity": "Personalized and custom-made gifts. Cultural and artisan handicrafts. Corporate gifting programs. Subscription and curated gift boxes."
    },
    "箱包": {
        "culture": "Bag styles and preferences vary by market. Luxury brand perception strong in Asia. Functional vs. fashion-driven purchasing differs. Travel culture influences luggage preferences.",
        "consumer": "Durability and quality critical for luggage. Brand consciousness strong for fashion bags. Online purchasing growing with virtual try-on. Warranty and repair services valued.",
        "infra": "REACH compliance for materials. Prop 65 compliance for California market. Material testing (leather, synthetic, hardware). Distribution through department stores, brand stores, and online.",
        "population": "Business travel recovery post-pandemic. Tourism growth driving luggage demand. Daily commuting needs for urban populations. Student market for backpacks and bags.",
        "social": "Sustainable and vegan leather alternatives. Minimalist and capsule wardrobe movement. Social media influencer brand collaborations. Gender-neutral bag designs.",
        "environment": "Sustainable materials (recycled nylon, vegan leather). Circular design and repairability. Carbon footprint of leather production. Recycled ocean plastic in bag manufacturing.",
        "opportunity": "Smart luggage with GPS and tracking. Sustainable and innovative materials. Direct-to-consumer brands. Functional and convertible bag designs."
    },
    "珠宝眼镜手表及配饰": {
        "culture": "Jewelry traditions vary enormously (gold in India, jade in China, diamonds in Western markets). Eyewear fashion consciousness growing. Watch culture strong in luxury segments. Religious and cultural jewelry significance.",
        "consumer": "Authentication and provenance critical for fine jewelry. Online purchasing growing for fashion jewelry. Try-on and customization expected. Insurance and appraisal services for high-value items.",
        "infra": "Precious metal hallmarking and assay. Kimberley Process for diamonds. Nickel and lead testing for fashion jewelry. Optical lab infrastructure for prescription eyewear.",
        "population": "Growing middle class driving jewelry demand. Aging populations needing reading glasses and progressive lenses. Youth fashion accessories market. Smartwatch adoption across demographics.",
        "social": "Lab-grown diamonds disrupting fine jewelry. Ethical and conflict-free sourcing demanded. Social media driving fashion jewelry trends. Celebrity and influencer watch collecting culture.",
        "environment": "Responsible mining and sourcing certifications. Recycled precious metals. Eco-friendly eyewear materials (bio-acetate, recycled). Packaging sustainability.",
        "opportunity": "Lab-grown diamonds and gemstones. Smart eyewear and AR glasses. Customizable and personalized jewelry. Sustainable luxury positioning."
    },
    "母婴&玩具": {
        "culture": "Parenting styles and product preferences vary by culture. Educational toy emphasis in East Asian markets. Safety consciousness universal for baby products. Traditional toys competing with digital entertainment.",
        "consumer": "Safety is the paramount purchasing factor. Research-intensive purchasing with reviews and certifications checked. Willingness to pay premium for quality and safety. Gift-giving for baby showers and birthdays.",
        "infra": "EN71, ASTM F963, CPSIA compliance for toys. Age grading and choking hazard warnings mandatory. Chemical testing (lead, phthalates, BPA). Textile safety for baby clothing (OEKO-TEX, CPSC).",
        "population": "Birth rates declining in developed markets but premium spending per child increasing. Growing middle class families in emerging markets. Grandparent spending on grandchildren significant.",
        "social": "Screen-free toy movement. STEM/STEAM education focus. Gender-neutral toys and marketing. Inclusive and diverse representation in toys and dolls.",
        "environment": "Sustainable toy materials (wood, recycled plastic). Toy recycling and donation programs. Minimal and recyclable packaging. Battery-free and solar-powered toys.",
        "opportunity": "STEM and educational toys. Sustainable and eco-friendly baby products. Smart and connected toys. Emerging market middle class family spending."
    },
    "面料及纺织原材料": {
        "culture": "Textile traditions deeply rooted in regions (silk in China, cotton in India, wool in Australia). Traditional weaving and dyeing techniques valued. Cultural significance of specific fabrics for ceremonies.",
        "consumer": "B2B purchasing by garment manufacturers and brands. Sustainability certifications increasingly required by buyers. Technical specifications (weight, weave, stretch) critical. Lead time and minimum order quantities important.",
        "infra": "OEKO-TEX, GOTS, BCI certifications. REACH compliance for chemical treatments. AZO dye and formaldehyde restrictions. Testing laboratories for fiber content and performance.",
        "population": "Global population growth driving textile demand. Fast fashion increasing fabric consumption. Emerging market clothing consumption rising. Performance fabric demand from active lifestyles.",
        "social": "Sustainable and recycled fiber movement. Transparency in supply chain demanded. Traditional craftsmanship preservation. Fair trade and ethical sourcing certifications.",
        "environment": "Water-intensive textile production under scrutiny. Microfiber pollution from synthetic fabrics. Chemical discharge regulations for dyeing and finishing. Circular textile economy initiatives.",
        "opportunity": "Recycled and bio-based fibers (lyocell, recycled polyester). Technical and performance textiles. Digital printing on fabric. Traceable and transparent supply chains."
    },
    "鞋靴及配饰": {
        "culture": "Footwear preferences shaped by climate and lifestyle. Athletic shoe culture strong globally. Traditional footwear important in some markets (sandals, clogs). Fashion footwear trends seasonal.",
        "consumer": "Comfort and fit critical for footwear purchases. Online purchasing growing with size recommendation tools. Brand loyalty strong in athletic segments. Wide range of price points from mass to luxury.",
        "infra": "REACH compliance for materials. Safety footwear standards (EN ISO 20345). Children's footwear safety regulations. Last and mold investment for production. Distribution through brand stores and multi-brand retailers.",
        "population": "Athletic participation driving sports shoe demand. Aging populations need comfort and orthopedic footwear. Youth sneaker culture and collecting. Growing populations in emerging markets.",
        "social": "Sneaker resale and collecting culture. Sustainable and vegan footwear movement. Social media driving footwear trends. Inclusivity in sizing (wide, narrow, plus sizes).",
        "environment": "Sustainable materials (recycled, bio-based). Shoe recycling and take-back programs. Chrome-free leather tanning. Carbon footprint of footwear manufacturing.",
        "opportunity": "Sustainable and circular footwear. Custom and 3D-printed footwear. Performance and smart footwear technology. Direct-to-consumer footwear brands."
    },
    "运动户外鞋服及装备": {
        "culture": "Sports and outdoor culture varies significantly by region. Running and fitness culture dominant in North America and Europe. Football/soccer gear demand strongest in Latin America, Europe, and Africa. Cricket equipment concentrated in South Asia and Commonwealth nations. Outdoor recreation (hiking, camping, skiing) deeply embedded in Western lifestyle.",
        "consumer": "Performance-driven purchasing with emphasis on technical specifications. Athleisure trend blurring sport and lifestyle categories. Brand loyalty strong in athletic footwear and apparel. Online purchasing dominant with extensive size/fit research. Willingness to pay premium for innovation and technology.",
        "infra": "Product safety and performance standards (CPSC, EN, ISO). Sport-specific certifications and testing. Moisture-wicking, UV protection, and thermal insulation testing. REACH compliance for textiles and footwear. Anti-doping material compliance for competitive sports.",
        "population": "Global health and fitness consciousness driving market growth. Youth sports participation and parental spending. Active aging population seeking low-impact sports gear. Urbanization creating demand for compact home fitness equipment. Growing middle class in emerging markets.",
        "social": "Social media fitness influencers driving trends. Outdoor recreation boom post-pandemic. Sustainability and recycled materials movement. Inclusivity in sports (adaptive sports, plus-size activewear). Esports and athleisure convergence.",
        "environment": "Recycled ocean plastics and bio-based materials. Sustainable manufacturing and waterless dyeing. Carbon-neutral product lines. Leave No Trace principles for outdoor gear. Circular economy and take-back programs.",
        "opportunity": "Smart sportswear with embedded sensors. Sustainable and recycled product lines. Direct-to-consumer brands. Outdoor recreation participation growth. Emerging market sports infrastructure and participation. Women-specific sports equipment."
    },
}

# ---------------------------------------------------------------------------
# Generic fallback template for L1 categories without specific templates
# ---------------------------------------------------------------------------
GENERIC_TEMPLATE = {
    "culture": "Cultural preferences and regional variations significantly influence product demand and specifications. Local customs, traditions, and regulatory environments shape market requirements. Globalization is creating convergence in some preferences while local differentiation remains a competitive advantage.",
    "consumer": "Quality, value, and reliability are key purchasing drivers across markets. Online research, reviews, and comparison heavily influence decisions. Brand reputation, certifications, and trust matter. Convenience, availability, and after-sales support affect purchasing behavior.",
    "infra": "Quality certifications and international standards compliance required for market access. Efficient logistics, distribution networks, and warehousing essential. Manufacturing capabilities, supply chain resilience, and quality control important. After-sales support, spare parts, and service networks valued by customers.",
    "population": "Demographic shifts significantly affect market demand patterns. Urbanization drives specific product needs and form factors. Age distribution influences product preferences and usage patterns. Population growth and middle-class expansion in emerging markets creates substantial opportunities.",
    "social": "Social media and online communities influence trends and purchasing decisions. Sustainability, ethical sourcing, and ESG concerns growing among consumers and B2B buyers. Lifestyle changes and work patterns affect product demand. Community recommendations and peer reviews increasingly important.",
    "environment": "Environmental regulations increasingly stringent across major markets. Sustainable materials, production processes, and packaging valued by buyers. Carbon footprint awareness and reporting requirements growing. Circular economy principles and extended producer responsibility gaining adoption.",
    "opportunity": "Emerging markets offer significant growth potential with rising demand. Digital transformation and e-commerce create new market access channels. Innovation, differentiation, and value-added services provide competitive advantages. Cross-border trade facilitation and free trade agreements expanding market reach."
}

# ---------------------------------------------------------------------------
# Compliance summary by L1  (keyed by name_cn from taxonomy)
# ---------------------------------------------------------------------------
COMPLIANCE_MAP = {
    "食品及饮料": "FDA/EU food safety regulations, HACCP certification, food labeling requirements, nutritional information, allergen declarations, organic certification if applicable.",
    "个人护理及家庭清洁": "Cosmetic safety assessment, GMP certification, REACH compliance (EU), ingredient labeling, stability testing, preservative efficacy testing.",
    "五金工具": "ISO quality standards, DIN/ANSI specifications, CE marking (EU), product liability insurance, safety testing for power tools.",
    "消费电子": "FCC (US), CE (EU), UL certification, RoHS compliance, WEEE directive, Energy Star, Bluetooth/Wi-Fi certifications.",
    "服装及配饰": "Textile fiber content labeling, care labeling, REACH (chemical compliance), OEKO-TEX certification, flammability testing for children's wear.",
    "家居园艺": "Product safety certifications (CPSC, CE), chemical compliance for garden products, furniture stability standards, electrical safety for powered equipment.",
    "工业机械": "CE marking, ISO certifications, Machinery Directive (2006/42/EC), pressure equipment directive (PED), ATEX for explosive atmospheres.",
    "建材与房地产": "Building code compliance, ASTM/EN standards, fire safety ratings, environmental certifications (LEED, BREEAM), structural testing.",
    "医疗器械和用品": "FDA 510(k) clearance, CE MDR certification, ISO 13485 quality management, clinical evaluation, post-market surveillance.",
    "汽车零配件": "IATF 16949, OEM specifications, ECE regulations, DOT standards (US), emissions compliance, PPAP documentation.",
    "运动及娱乐": "CPSC safety standards (US), EN standards (EU), sport-specific certifications, product liability insurance, age grading requirements.",
    "农业": "Phytosanitary certificates, MRL (maximum residue limits), organic certification (USDA/EU), GlobalGAP, country-of-origin labeling.",
    "化学品": "REACH registration (EU), TSCA compliance (US), GHS labeling, SDS requirements, transport regulations (ADR/IMDG/IATA).",
    "美妆": "Cosmetic safety assessment, FDA/EU cosmetic regulations, INCI ingredient labeling, animal testing bans, GMP manufacturing.",
    "灯具照明": "CE marking, UL listing, Energy Star, DLC qualification, photobiological safety (IEC 62471), EMC compliance.",
    "电气设备及用品": "CE marking, UL/CSA certification, IEC standards, EMC directive, Low Voltage Directive (2014/35/EU), RoHS compliance.",
    "家具": "BIFMA standards (US), EN standards (EU), flammability regulations (TB 117), chemical emissions testing (CARB, GREENGUARD), stability testing.",
    "包装印刷": "Food contact materials compliance (EU 10/2011), REACH, recycling and waste regulations, labeling requirements, FSC certification for paper.",
    "仪器仪表": "CE marking, ISO 17025 calibration, accuracy and precision standards, environmental testing (IP rating), EMC compliance.",
    "橡胶与塑料制品": "REACH compliance, FDA food contact (if applicable), RoHS, recycling and waste regulations, material testing and certification.",
    "金属与合金": "Material certifications (mill test certificates per EN 10204), REACH compliance, RoHS, conflict minerals reporting, quality standards (ASTM, EN, JIS).",
    "面料及纺织原材料": "OEKO-TEX certification, REACH compliance, fiber content labeling, organic certification (GOTS), AZO dye restrictions, formaldehyde limits.",
    "鞋靴及配饰": "Footwear labeling regulations, REACH compliance, safety footwear standards (EN ISO 20345), children's footwear safety, chemical testing (chromium VI, phthalates).",
    "珠宝眼镜手表及配饰": "Precious metal hallmarking, gemstone disclosure (FTC guides), nickel release testing (EN 1811), CE marking for eyewear, CPSIA for children's jewelry.",
    "箱包": "REACH compliance, Prop 65 (California), product safety testing, material composition labeling, hardware durability testing.",
    "宠物用品及食品": "AAFCO standards (pet food), FDA compliance, CE marking for pet products, safety testing, ingredient and nutritional labeling.",
    "可再生能源": "IEC standards (61215, 61730, 62109), UL certification (1741, 2703), CE marking, grid connection standards (IEEE 1547), performance certification (TUV, MCS).",
    "安防": "CE marking, UL certification, EN 50131 (alarm systems), EN 62676 (video surveillance), cybersecurity standards (IEC 62443).",
    "安全用品": "ANSI/ISEA standards, CE marking, EN ISO standards, product certification and third-party testing, quality management systems.",
    "商业设备及机械": "CE marking, UL certification, NSF certification (food service equipment), electrical safety (IEC 60335), EMC compliance.",
    "母婴&玩具": "EN71 (EU toys), ASTM F963 (US toys), CPSIA compliance, age grading and small parts testing, chemical testing (lead, phthalates), textile safety for baby clothing (OEKO-TEX).",
    "汽车用品、电子及工具设备": "ECE regulations, FCC/CE for automotive electronics, automotive EMC standards (CISPR 25), product safety testing, OEM approvals.",
    "整车及交通工具": "ECE/EEC type approval, DOT/EPA compliance (US), CCC certification (China), emissions standards (Euro 6/China 6), crash safety testing (NCAP).",
    "电子元器件、配件及通讯": "RoHS compliance, REACH, CE marking, UL recognition, IEC standards, telecom equipment approvals (FCC Part 15, RED Directive).",
    "礼品与工艺品": "General product safety (GPSD), REACH compliance, CPSIA for children's products, material composition labeling, country of origin marking.",
    "办公文教用品": "General product safety, CE marking for electrical items, chemical compliance (REACH), ergonomic standards, non-toxic art material labeling (AP/CP).",
    "传动": "ISO standards for mechanical power transmission, CE marking, bearing quality standards (ABMA/ISO), motor efficiency classes (IE1-IE4), ATEX for hazardous areas.",
    "健康护理": "FDA compliance for dietary supplements (21 CFR 111), GMP certification, health claims regulations, CE marking for health devices, product safety testing.",
    "买家物流市场": "Freight forwarding licenses, customs brokerage compliance, Incoterms knowledge, cargo insurance, trade compliance and sanctions screening.",
    "代理采购": "Business licenses, trade compliance, quality inspection standards, intellectual property protection, contractual and legal compliance.",
    "工程及建材机械": "CE marking, Machinery Directive compliance, ISO quality standards, structural steel fabrication standards (EN 1090), safety interlocks.",
    "开发与技术服务": "Software development standards (ISO 12207), data protection regulations (GDPR), intellectual property protection, industry-specific compliance (HIPAA, PCI-DSS).",
    "检验检测与认证": "ISO 17025 (testing), ISO 17020 (inspection), ISO 17065 (certification), accreditation body requirements, proficiency testing participation.",
    "物料搬运": "CE marking, OSHA compliance (US), EN standards for lifting equipment, load testing and certification, operator training requirements.",
    "环保": "Environmental management systems (ISO 14001), waste handling permits, emissions monitoring and reporting, recycling certifications, hazardous material handling.",
    "商务服务": "Professional certifications, data protection regulations (GDPR), anti-money laundering (AML) compliance, industry-specific regulatory requirements.",
    "设计服务": "Intellectual property protection, design registration and patent support, industry-specific standards compliance, client confidentiality and NDAs.",
    "家用电器": "Energy Star/EU Energy Label, safety certifications (UL/CE/CCC), refrigerant regulations (F-gas, SNAP), EMC compliance, WEEE directive.",
    "运动户外鞋服及装备": "Textile fiber content labeling, REACH compliance (EU), CPSC safety standards (US), sport-specific certifications, footwear safety standards, protective equipment testing (EN/ASTM), UV protection ratings, flame retardant testing for outdoor gear.",
}

# ---------------------------------------------------------------------------
# Keyword domain terms for richer generation
# ---------------------------------------------------------------------------
EN_DOMAIN_TERMS = {
    "personal care": ["beauty", "skincare", "wellness", "grooming"],
    "food": ["organic", "natural", "gourmet", "premium"],
    "tool": ["professional", "industrial", "heavy-duty", "precision"],
    "machine": ["industrial", "automatic", "CNC", "high-speed"],
    "electronic": ["smart", "portable", "wireless", "digital"],
    "medical": ["clinical", "diagnostic", "surgical", "disposable"],
    "auto": ["OEM", "aftermarket", "performance", "replacement"],
    "building": ["waterproof", "insulation", "structural", "fireproof"],
    "sport": ["professional", "outdoor", "fitness", "competition"],
    "home": ["modern", "compact", "multi-functional", "eco-friendly"],
    "chemical": ["industrial-grade", "high-purity", "specialty", "bulk"],
    "textile": ["organic", "recycled", "technical", "woven"],
    "packaging": ["sustainable", "custom", "food-grade", "biodegradable"],
    "toy": ["educational", "STEM", "interactive", "safe"],
    "jewelry": ["handmade", "custom", "luxury", "fashion"],
    "energy": ["renewable", "solar", "high-efficiency", "off-grid"],
}

CN_DOMAIN_TERMS = {
    "default": ["出口", "批发", "工厂", "供应商", "制造商"],
}


# ===========================================================================
# Functions
# ===========================================================================

def load_taxonomy():
    """Load taxonomy from JSON file."""
    with open(TAXONOMY_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_hs_code(l1_cn: str, l2_cn: str) -> str:
    """Get HS code prefix for a category. L2 overrides take precedence."""
    if l2_cn in L2_HS_OVERRIDES:
        return L2_HS_OVERRIDES[l2_cn]
    return HS_CODE_MAP.get(l1_cn, "99xx")


def _match_domain_terms(text: str, term_map: dict) -> list[str]:
    """Return domain terms that match the given text (case-insensitive)."""
    text_lower = text.lower()
    matched = []
    for keyword, terms in term_map.items():
        if keyword in text_lower:
            matched.extend(terms[:2])
    return matched


def generate_keywords_en(l2_en: str, l1_cn: str) -> list[str]:
    """Generate 3-5 English search keywords relevant for trade/export research."""
    name = l2_en.lower()
    keywords = [name]

    # Export / trade terms
    keywords.append(f"china {name} export")
    keywords.append(f"{name} wholesale supplier")

    # Domain-specific additions
    domain = _match_domain_terms(name, EN_DOMAIN_TERMS)
    for d in domain[:2]:
        kw = f"{name} {d}"
        if kw not in keywords:
            keywords.append(kw)

    # Fallback to ensure at least 3-5
    if len(keywords) < 4:
        keywords.append(f"{name} manufacturer")
    if len(keywords) < 5:
        keywords.append(f"china {name} trade")

    return keywords[:5]


def generate_keywords_cn(l2_cn: str, l1_cn: str) -> list[str]:
    """Generate 3-5 Chinese search keywords relevant for trade/export research."""
    keywords = [l2_cn]
    keywords.append(f"{l2_cn}出口")
    keywords.append(f"{l2_cn}批发")
    keywords.append(f"{l2_cn}供应商")
    keywords.append(f"{l2_cn}工厂")

    return keywords[:5]


def get_industry_analysis(l1_cn: str) -> dict:
    """Return industry analysis template for the L1 category."""
    return INDUSTRY_TEMPLATES.get(l1_cn, GENERIC_TEMPLATE)


def get_compliance_summary(l1_cn: str) -> str:
    """Return compliance summary for the L1 category."""
    return COMPLIANCE_MAP.get(
        l1_cn,
        "General product safety compliance, applicable quality certifications, "
        "and regional regulatory requirements must be met for target export markets."
    )


def generate_category_data(l1_slug: str, l1_cn: str, l2: dict) -> dict:
    """Generate the complete JSON structure for a single L2 category."""
    l2_slug = l2['slug']
    l2_cn = l2['cn']
    l2_en = l2['en']
    l1_en = L1_EN_MAP.get(l1_cn, l1_cn)

    return {
        "id": f"{l1_slug}--{l2_slug}",
        "name_cn": l2_cn,
        "name_en": l2_en,
        "parent_cn": l1_cn,
        "parent_en": l1_en,
        "l1_slug": l1_slug,
        "hs_codes": [get_hs_code(l1_cn, l2_cn)],
        "keywords_en": generate_keywords_en(l2_en, l1_cn),
        "keywords_cn": generate_keywords_cn(l2_cn, l1_cn),
        "export_data": None,
        "global_trends": None,
        "industry_analysis": get_industry_analysis(l1_cn),
        "compliance_summary": get_compliance_summary(l1_cn),
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "data_source": "base_generated",
    }


# ===========================================================================
# Main
# ===========================================================================

def main():
    """Generate all L2 category JSON files and the master index."""
    print("=" * 60)
    print("  GlobalAlpha Compass - Category Data Generator")
    print("=" * 60)
    print()

    # Load taxonomy
    print("Loading taxonomy from:", TAXONOMY_FILE)
    taxonomy = load_taxonomy()
    meta = taxonomy['meta']
    print(f"  L1 categories : {meta['total_l1']}")
    print(f"  L2 categories : {meta['total_l2']}")
    print(f"  L3 categories : {meta['total_l3']}")
    print()

    # Ensure output directory exists
    CATEGORIES_DIR.mkdir(parents=True, exist_ok=True)

    index_entries = []
    files_generated = 0
    l1_dirs_created = set()

    for l1 in taxonomy['categories']:
        l1_slug = l1['slug']
        l1_cn = l1['name_cn']
        l1_en = L1_EN_MAP.get(l1_cn, l1_cn)
        l2_count = len(l1['l2_categories'])

        print(f"  [{l1_cn}] ({l2_count} L2 categories)")

        # Create L1 directory
        l1_dir = CATEGORIES_DIR / l1_slug
        l1_dir.mkdir(exist_ok=True)
        l1_dirs_created.add(l1_slug)

        for l2 in l1['l2_categories']:
            l2_slug = l2['slug']

            # Generate data
            category_data = generate_category_data(l1_slug, l1_cn, l2)

            # Write individual L2 JSON file
            l2_file = l1_dir / f"{l2_slug}.json"
            with open(l2_file, 'w', encoding='utf-8') as f:
                json.dump(category_data, f, ensure_ascii=False, indent=2)
            files_generated += 1

            # Collect index entry
            index_entries.append({
                "id": category_data['id'],
                "name_cn": l2['cn'],
                "name_en": l2['en'],
                "l1_cn": l1_cn,
                "l1_en": l1_en,
                "l1_slug": l1_slug,
                "l2_slug": l2_slug,
                "l3_count": l2['l3_count'],
                "hs_code_prefix": category_data['hs_codes'][0],
                "has_detailed_data": False,
            })

    # Write master index
    print()
    print("Writing category index...")
    index_data = {"categories": index_entries}
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    # Summary statistics
    hs_codes_used = sorted(set(e['hs_code_prefix'] for e in index_entries))
    categories_with_templates = sum(
        1 for l1 in taxonomy['categories']
        if l1['name_cn'] in INDUSTRY_TEMPLATES
    )
    categories_without_templates = meta['total_l1'] - categories_with_templates

    print()
    print("=" * 60)
    print("  Generation Complete!")
    print("=" * 60)
    print(f"  L2 JSON files generated : {files_generated}")
    print(f"  L1 directories created  : {len(l1_dirs_created)}")
    print(f"  Index entries written   : {len(index_entries)}")
    print(f"  L1 with rich templates : {categories_with_templates}")
    print(f"  L1 with generic template: {categories_without_templates}")
    print(f"  Unique HS code prefixes : {len(hs_codes_used)} ({', '.join(hs_codes_used[:10])}{'...' if len(hs_codes_used) > 10 else ''})")
    print(f"  Output directory        : {CATEGORIES_DIR}")
    print(f"  Index file              : {INDEX_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
