"""
GlobalAlpha Compass - 动态洞察合成模块（L1 + L2 共用）

输出:
  {
    "trend_summary": "...",        # 一段话趋势总结
    "product_profile": {           # 6 项产品画像
      "外观": "...", "成分": "...", "工艺": "...",
      "色彩": "...", "包装": "...", "技术趋势": "..."
    },
    "reasons": [                   # 3-5 条驱动力
      "...", "..."
    ],
    "signals": [                   # 4 维证据源
      {"dim":"海外社媒", "kw":"...", "growth":..., "vol":"..."},
      {"dim":"搜索",     "kw":"...", "growth":...},
      {"dim":"媒体",     "title":"...", "source":"...", "url":"..."},
      {"dim":"Amazon",   "market":"US", "rank":..., "title":"..."}
    ],
    "generated_at": "2026-06-19",
    "l1_ref": "可再生能源"
  }

纯本地计算，无网络请求；CI 每日构建即更新。
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import re


TODAY = lambda: datetime.now(timezone.utc).strftime('%Y-%m-%d')


# ============================================================
# 领域模板（用于 product_profile 基线 + 触发关键词匹配）
# key = 领域 slug；triggers = 触发条件（命中任一即采用该模板）
# ============================================================
PRODUCT_PROFILE_TEMPLATES = {
    'renewable_energy': {
        'triggers': [
            'solar', 'photovoltaic', 'pv ', 'wind turbine', 'energy storage',
            'battery', 'lithium', 'lifepo4', 'nmc', 'inverter', 'hydrogen',
            'renewable', 'bipv', 'ev charger',
            '光伏', '储能', '风电', '氢能', '逆变器', '可再生能源',
        ],
        'profile': {
            '外观':   '极简白电化 / 可堆叠模块化 / IP65 户外防护外壳',
            '成分':   'LiFePO4 磷酸铁锂电芯 / 单晶硅 PERC/TOPCon/HJT 电池片',
            '工艺':   'CTP/CTC 一体化封装 / 半片多主栅 / 双面双玻',
            '色彩':   '哑光白 / 石墨灰 / 黑色全黑组件（BIPV 建筑一体化）',
            '包装':   '瓦楞纸 + 可降解 EPS / 符合欧盟 PPWR 包装法规',
            '技术趋势': 'AI EMS 能量管理 / 阳台储能即插即用 / V2G 双向逆变 / 钙钛矿叠层',
        },
    },
    'consumer_electronics': {
        'triggers': [
            'earbuds', 'tws', 'headphone', 'smartwatch', 'smart phone',
            'laptop', 'tablet', 'vr ', 'ar glasses', 'speaker bluetooth',
            'drone', 'camera', 'charger', 'powerbank',
            '耳机', '智能手表', '手机', '笔记本', '无人机', '充电宝',
        ],
        'profile': {
            '外观':   '极简曲面 / CNC 铝合金中框 / 亲肤硅胶耳塞',
            '成分':   'ABS+PC 外壳 / 钴酸锂或硅碳负极电池 / 稀土磁钢',
            '工艺':   'SMT 贴片 + AOI 全检 / IPX4-7 防水镀膜 / 超声波焊接',
            '色彩':   '星空黑 / 陶瓷白 / 莫兰迪绿 / 年度流行色（Pantone）',
            '包装':   '磁吸翻盖礼盒 / 可回收纸浆托盘 / 大豆油墨',
            '技术趋势': 'LE Audio 低功耗音频 / 端侧 AI 模型 / GaN 快充 / UWB 空间感知',
        },
    },
    'home_appliance': {
        'triggers': [
            'refrigerator', 'washing machine', 'microwave', 'air fryer',
            'vacuum', 'robot ', 'blender', 'coffee machine', 'kettle',
            'air purifier', 'dehumidifier', 'fan', 'appliance',
            '冰箱', '洗衣机', '微波炉', '扫地机', '空气炸锅', '家电',
        ],
        'profile': {
            '外观':   '嵌入式一体化 / 圆润 R 角设计 / 哑光磨砂面板',
            '成分':   'ABS 工程塑料 / 食品级不锈钢 304 / BLDC 无刷电机',
            '工艺':   'IMD 模内装饰 / 一体注塑 / IPX 防水 / 能效 A+++',
            '色彩':   '莫兰迪灰 / 奶油白 / 复古绿（Retro）',
            '包装':   '蜂窝纸护角 + 瓦楞箱 / EPE 珍珠棉 / 欧盟 WEEE 标识',
            '技术趋势': 'Matter 智能家居互联 / AI 场景识别 / 热泵烘干 / R290 环保冷媒',
        },
    },
    'beauty_cosmetics': {
        'triggers': [
            'skincare', 'cosmetic', 'makeup', 'lipstick', 'serum',
            'moisturizer', 'spf ', 'sunscreen', 'foundation', 'mascara',
            'nail', 'fragrance', 'perfume',
            '护肤', '口红', '防晒', '精华', '粉底', '美妆', '化妆品',
        ],
        'profile': {
            '外观':   '磨砂玻璃瓶 / 金属磁吸盖 / 极简极简主义',
            '成分':   '烟酰胺 / 视黄醇 / 玻尿酸 / 植物提取物（Clean Beauty）',
            '工艺':   '真空灌装 / 无防腐体系 / 微囊包裹活性成分',
            '色彩':   '莫兰迪裸粉 / 金属玫瑰金 / 复古红（季节限定）',
            '包装':   '再生 PCR 塑料 / 可替换内芯 / FSC 纸盒',
            '技术趋势': '微生态护肤 / AI 肤色检测定制 / 无水配方 / 纯净美妆',
        },
    },
    'apparel_fashion': {
        'triggers': [
            't-shirt', 'hoodie', 'jacket', 'jeans', 'dress', 'shirt',
            'sweater', 'activewear', 'yoga', 'lingerie', 'socks',
            'apparel', 'clothing', 'fashion', 'garment',
            '服装', 'T恤', '外套', '牛仔', '瑜伽服', '运动服', '内衣',
        ],
        'profile': {
            '外观':   '宽松廓形（Oversize）/ 无缝一体织 / 多口袋工装',
            '成分':   '再生 PET 面料 / 有机棉 GOTS / 莱卡弹力纤维 / Cordura',
            '工艺':   '数码直喷印花 / 热切割无缝 / 3D 立体剪裁',
            '色彩':   '大地色系 / 多巴胺色 / 年度流行色（WGSN）',
            '包装':   '可降解玉米淀粉袋 / 再生纸吊牌 / 无塑料衣架',
            '技术趋势': 'AI 虚拟试衣 / 数字产品护照 DPP / 按需生产（On-Demand）',
        },
    },
    'footwear': {
        'triggers': [
            'sneaker', 'shoe', 'boot', 'sandal', 'footwear', 'trainer',
            'running shoe', 'heel', 'loafer',
            '鞋', '运动鞋', '靴', '凉鞋', '皮鞋',
        ],
        'profile': {
            '外观':   'Chunky 厚底 / 复古德训 / 飞织鞋面',
            '成分':   'EVA 中底 / TPU 支撑片 / 再生橡胶大底 / 飞织 PET',
            '工艺':   '3D 打印中底 / 冷粘合无溶剂 / 注塑一体',
            '色彩':   '熊猫配色 / 大地色 / 年度流行色',
            '包装':   '再生纸盒 / 可降解替代泡沫 / 无塑料绑带',
            '技术趋势': 'AI 足型扫描定制 / 碳板跑鞋 / 3D 针织零废料',
        },
    },
    'bags_luggage': {
        'triggers': [
            'backpack', 'luggage', 'suitcase', 'handbag', 'tote',
            'briefcase', 'duffel', 'purse', 'wallet',
            '背包', '行李箱', '手提包', '旅行箱', '钱包', '箱包',
        ],
        'profile': {
            '外观':   '极简通勤风 / 多功能模块化 / 可折叠',
            '成分':   'RPET 再生面料 / 素皮（苹果皮/仙人掌皮）/ 弹道尼龙',
            '工艺':   '热压无缝 / YKK 防水拉链 / TSA 海关锁',
            '色彩':   '经典黑 / 沙漠卡其 / 莫兰迪奶茶',
            '包装':   '防尘布袋 / 再生纸盒 / 无塑料填充',
            '技术趋势': '智能旅行箱（GPS/USB/电子秤）/ 数字锁 NFC',
        },
    },
    'jewelry_watches': {
        'triggers': [
            'ring', 'necklace', 'bracelet', 'earring', 'pendant',
            'watch', 'smartwatch', 'sunglasses', 'eyewear',
            '珠宝', '项链', '戒指', '手表', '眼镜', '墨镜',
        ],
        'profile': {
            '外观':   '极简几何 / 层叠叠戴 / 复古 Vintage',
            '成分':   '钛钢 316L / 925 银 / 培育钻石（Lab-Grown）/ 再生金',
            '工艺':   'PVD 真空镀 / 3D 打印蜡模 / 精密 CNC',
            '色彩':   '玫瑰金 / 哑光银 / 黄金色 / 搪瓷彩色',
            '包装':   '丝绒礼盒 / FSC 纸盒 / 可重复使用收纳袋',
            '技术趋势': '培育钻石主流化 / 智能戒指健康监测 / AR 虚拟试戴',
        },
    },
    'food_beverage': {
        'triggers': [
            'coffee', 'tea', 'snack', 'chocolate', 'candy', 'sauce',
            'noodle', 'canned', 'juice', 'wine', 'beer', 'spice',
            'protein', 'supplement', 'organic', 'halal',
            '食品', '饮料', '咖啡', '茶', '零食', '巧克力', '清真',
        ],
        'profile': {
            '外观':   '透明可视包装 / 极简日系 / 国风插画',
            '成分':   '零添加 / 有机认证 / 清真 Halal / 植物基',
            '工艺':   '低温冻干 / HPP 超高压杀菌 / 氮气锁鲜',
            '色彩':   '高饱和多巴胺 / 天然色系（抹茶绿/可可棕）',
            '包装':   '可降解 PLA / 铝箔自立袋 / FSC 纸盒',
            '技术趋势': '功能性食品（NMN/胶原蛋白）/ 个性化订阅 / 碳足迹标签',
        },
    },
    'toys_baby': {
        'triggers': [
            'toy', 'doll', 'lego', 'puzzle', 'teddy', 'stroller',
            'diaper', 'baby', 'infant', 'children', 'kids',
            '玩具', '娃娃', '积木', '婴儿', '母婴', '儿童',
        ],
        'profile': {
            '外观':   '圆润 R 角（儿童安全）/ 马卡龙色系 / 模块化',
            '成分':   '食品级硅胶 / ABS 无毒塑料 / 有机棉',
            '工艺':   '注塑一体无毛刺 / 水性漆 / EN71 合规',
            '色彩':   '马卡龙色 / 原木色 / 多巴胺',
            '包装':   '开窗展示盒 / 再生纸 / 无小零件警告标识',
            '技术趋势': 'STEM 教育玩具 / AR 互动 / 可持续材料',
        },
    },
    'pet_products': {
        'triggers': [
            'pet', 'dog', 'cat ', 'collar', 'leash', 'kennel',
            'pet food', 'aquarium', 'bird',
            '宠物', '狗', '猫', '猫砂', '狗粮', '猫粮',
        ],
        'profile': {
            '外观':   '可爱萌系 / 人宠同款 / 模块化',
            '成分':   '食品级不锈钢 / 天然橡胶 / 有机配方粮',
            '工艺':   '注塑一体 / 食品级灌装 / 防泼水设计',
            '色彩':   '马卡龙粉 / 薄荷绿 / 奶茶色',
            '包装':   '自立铝箔袋 / 可重复封口 / 再生纸盒',
            '技术趋势': '智能喂食器 / 宠物健康项圈 / 冻干主粮',
        },
    },
    'chemicals': {
        'triggers': [
            'chemical', 'resin', 'paint', 'coating', 'adhesive',
            'fertilizer', 'pigment', 'solvent', 'polymer',
            '化工', '树脂', '涂料', '胶', '颜料', '化肥',
        ],
        'profile': {
            '外观':   '工业标准桶 / IBC 吨桶 / 小瓶试剂',
            '成分':   '水性 / 无溶剂 / 低 VOC / 生物基替代',
            '工艺':   '连续流反应 / 膜分离 / GMP 车间',
            '色彩':   '标识色（UN 危规标签）',
            '包装':   'HDPE 桶 / IBC 吨桶 / UN 认证危包',
            '技术趋势': '生物基替代 / 碳捕捉 CCU 原料 / 数字化 SDS',
        },
    },
    'metals': {
        'triggers': [
            'steel', 'aluminum', 'alloy', 'copper', 'stainless',
            'iron', 'metal ', 'zinc', 'nickel', 'titanium',
            '钢', '铝', '合金', '铜', '不锈钢', '金属',
        ],
        'profile': {
            '外观':   '工业标准卷材/板材/棒材 / 定制切割',
            '成分':   '低碳钢 / 再生铝 / 镍基高温合金 / 无铅黄铜',
            '工艺':   '热轧 / 冷轧 / 电解 / 粉末冶金',
            '色彩':   '金属原色 / 阳极氧化彩色',
            '包装':   '木托盘 + 钢带 / 防锈 VCI 膜 / 海运木箱',
            '技术趋势': 'CBAM 碳边境税驱动绿钢 / 氢能直接还原 / 再生金属溯源',
        },
    },
    'textiles': {
        'triggers': [
            'fabric', 'textile', 'cotton', 'yarn', 'polyester',
            'nylon', 'silk', 'linen', 'denim', 'weave', 'knit',
            '面料', '纺织', '棉花', '纱线', '涤纶', '尼龙',
        ],
        'profile': {
            '外观':   '功能整理（防水/阻燃/抗菌）/ 数码印花',
            '成分':   '再生 PET 纱线 / 有机棉 / 莱赛尔天丝 / 生物基尼龙',
            '工艺':   '数码印花 / 无缝针织 / 环保染整（Oeko-Tex）',
            '色彩':   'Pantone 年度色 / 植物染 / 数码渐变',
            '包装':   '卷筒装 / 真空压缩 / 再生纸管',
            '技术趋势': '数字产品护照 DPP / 无水染色 / 3D 织造零废料',
        },
    },
    'auto_parts': {
        'triggers': [
            'auto part', 'brake', 'tire', 'wheel', 'bumper',
            'engine', 'transmission', 'suspension', 'exhaust',
            '汽配', '刹车', '轮胎', '发动机', '保险杠', '悬挂',
        ],
        'profile': {
            '外观':   'OEM 原厂规格 / 改装升级款 / 赛车竞技款',
            '成分':   '高强度钢 / 锻造铝合金 / 碳纤维 / 陶瓷',
            '工艺':   'CNC 精密加工 / 锻造 / 粉末冶金 / 电泳涂装',
            '色彩':   '原厂黑 / 竞技彩色阳极 / 镀铬',
            '包装':   '木箱 / 防锈 VCI 袋 / 托盘 + 缠绕膜',
            '技术趋势': '电动化三电系统 / ADAS 传感器 / 线控底盘',
        },
    },
    'vehicles_ev': {
        'triggers': [
            'electric vehicle', 'ev ', 'car ', 'truck', 'bus',
            'motorcycle', 'scooter', 'bike', 'e-bike',
            '电动车', '新能源车', '摩托车', '自行车', '整车',
        ],
        'profile': {
            '外观':   '流线型低风阻 / 贯穿式尾灯 / 极简内饰',
            '成分':   '三元锂/磷酸铁锂电池 / 高强度钢铝混合车身',
            '工艺':   '一体化压铸 / 激光焊接 / 800V 高压平台',
            '色彩':   '哑光灰 / 冰川蓝 / 定制双色车身',
            '包装':   '滚装船 RoRo / 集装箱框架 / 电池 UN3480 危包',
            '技术趋势': '固态电池 / 800V 4C 超充 / 端到端自动驾驶',
        },
    },
    'medical_devices': {
        'triggers': [
            'medical device', 'surgical', 'hospital', 'diagnostic',
            'implant', 'dental', 'wheelchair', 'stethoscope',
            'mri', 'ct ', 'ultrasound', 'bandage', 'syringe',
            '医疗器械', '医用', '手术', '诊断', '牙科', '轮椅',
        ],
        'profile': {
            '外观':   '医疗级白色 / 抗菌涂层 / 人体工学',
            '成分':   '医用级 316L 不锈钢 / PEEK / 医用硅胶 / 钛合金',
            '工艺':   '洁净室装配 / EO 灭菌 / ISO 13485 体系',
            '色彩':   '医疗白 / 淡蓝 / 浅绿（手术室专用）',
            '包装':   '灭菌 Tyvek 袋 / 双层无菌包 / UDI 追溯标签',
            '技术趋势': 'AI 辅助诊断 / 可穿戴监测 / 3D 打印植入物 / 远程医疗',
        },
    },
    'lighting': {
        'triggers': [
            'lighting', 'led ', 'lamp', 'bulb', 'chandelier',
            'spotlight', 'floodlight', 'strip light', 'solar light',
            '灯具', '照明', 'LED', '灯泡', '射灯',
        ],
        'profile': {
            '外观':   '极简线条 / 无主灯设计 / 磁吸轨道',
            '成分':   '铝散热外壳 / COB 光源 / PMMA 导光板',
            '工艺':   'SMT 贴片 + 回流焊 / IP65 灌胶防水 / DALI 调光',
            '色彩':   '哑光黑 / 白 / 黄铜色（复古）',
            '包装':   '环保纸浆模塑 / 珍珠棉 / 开窗彩盒',
            '技术趋势': '智能照明（Matter/Zigbee）/ 节律照明 / 太阳能一体化',
        },
    },
    'machinery': {
        'triggers': [
            'machine', 'cnc', 'pump', 'compressor', 'generator',
            'motor', 'lathe', 'crane', 'excavator', 'robot',
            'industrial', 'manufacturing',
            '机械', '机床', '泵', '压缩机', '发电机', '马达', '机器人',
        ],
        'profile': {
            '外观':   '工业涂装（黄/红/蓝品牌色）/ 模块化',
            '成分':   '高强度铸钢 / 耐磨合金 / 稀土永磁',
            '工艺':   'CNC 精密加工 / 热处理 / 动平衡校准',
            '色彩':   '品牌主色（卡特黄/三一红/小松蓝）',
            '包装':   '海运木箱（熏蒸 ISPM-15）/ 托盘 + 缠绕膜',
            '技术趋势': '工业物联网 IIoT / 数字孪生 / 远程预测性维护',
        },
    },
    'building_materials': {
        'triggers': [
            'cement', 'tile', 'ceramic', 'glass', 'brick',
            'concrete', 'plywood', 'drywall', 'insulation',
            '建材', '瓷砖', '水泥', '玻璃', '木材', '保温',
        ],
        'profile': {
            '外观':   '大板岩纹 / 微水泥 / 哑光大理石纹',
            '成分':   '再生骨料 / 低碳水泥 / 无甲醛胶黏剂',
            '工艺':   '大吨位压制 / 数码喷墨印花 / 钢化中空',
            '色彩':   '米白 / 岩灰 / 木纹色',
            '包装':   '木托盘 + 缠绕膜 / 防震护角 / 海运加固',
            '技术趋势': '光伏建筑一体化 BIPV / 被动房标准 / 3D 打印建筑',
        },
    },
    'security_safety': {
        'triggers': [
            'cctv', 'camera', 'alarm', 'lock', 'safe',
            'ppe', 'helmet', 'glove', 'vest', 'safety',
            '安防', '监控', '报警', '安全', '劳保', '头盔', '手套',
        ],
        'profile': {
            '外观':   '工业坚固型 / 隐蔽安装 / 人体工学',
            '成分':   'ABS+PC / 芳纶纤维（Kevlar）/ 反光条',
            '工艺':   'IP67 防水 / 防爆认证 / 阻燃 V0',
            '色彩':   '安全黄 / 警示橙 / 反光银',
            '包装':   '开窗彩盒 / 防静电袋 / CE 标识',
            '技术趋势': 'AI 视频分析 / 智能 PPE 传感器 / 生物识别门禁',
        },
    },
    'packaging_printing': {
        'triggers': [
            'packaging', 'box', 'carton', 'label', 'sticker',
            'printing', 'ink', 'paper', 'corrugated',
            '包装', '纸箱', '标签', '印刷', '油墨', '纸',
        ],
        'profile': {
            '外观':   '极简牛皮 / 数码印刷彩盒 / 异形结构',
            '成分':   '再生纸浆 / 大豆油墨 / 水性光油',
            '工艺':   '数码短版印刷 / 烫金 UV / 模切压痕',
            '色彩':   '四色 CMYK / Pantone 专色 / 金属色',
            '包装':   '托盘 + 缠绕膜 / 平装发货',
            '技术趋势': '可降解材料 / 智能标签（NFC/RFID）/ 按需印刷',
        },
    },
    'environmental': {
        'triggers': [
            'recycling', 'waste', 'water treatment', 'filter',
            'sewage', 'carbon', 'green', 'environmental',
            '环保', '回收', '污水处理', '过滤', '碳', '绿色',
        ],
        'profile': {
            '外观':   '工业设备 / 模块化集装箱式 / 撬装',
            '成分':   '不锈钢 304 / PVDF 膜 / 活性炭',
            '工艺':   'MBR 膜生物反应 / RO 反渗透 / 催化氧化',
            '色彩':   '工业灰 / 环保绿',
            '包装':   '集装箱式整机 / 海运框架箱',
            '技术趋势': 'CCUS 碳捕集 / 绿氢 / 数字化水务运营',
        },
    },
    'instruments': {
        'triggers': [
            'instrument', 'meter', 'sensor', 'gauge', 'tester',
            'analyzer', 'spectrometer', 'oscilloscope',
            '仪器', '仪表', '传感器', '分析仪', '测量',
        ],
        'profile': {
            '外观':   '手持便携 / 台式精密 / IP67 工业级',
            '成分':   '航空铝外壳 / MEMS 传感器 / 蓝宝石视窗',
            '工艺':   '校准溯源 / 无尘装配 / ISO 17025',
            '色彩':   '工业黑 / 警示黄 / 仪器灰',
            '包装':   '防震铝合金箱 / 防静电 / 校准证书',
            '技术趋势': '物联网在线监测 / AI 预测校准 / 微型化',
        },
    },
    'electronics_components': {
        'triggers': [
            'semiconductor', 'chip', 'ic ', 'mosfet', 'pcb',
            'connector', 'capacitor', 'resistor', 'led driver',
            '5g', 'iot', 'module',
            '芯片', '半导体', '连接器', '电容', 'PCB', '模块',
        ],
        'profile': {
            '外观':   'SMT 贴片 / QFN/BGA 封装 / 模块化',
            '成分':   '硅基 / 第三代半导体 SiC/GaN / 无铅焊料',
            '工艺':   '光刻 / 键合 / AOI / X-ray 检测',
            '色彩':   '黑色环氧封装 / 载带银色',
            '包装':   'ESD 防静电卷带 / 托盘 / 湿度指示卡',
            '技术趋势': '先进封装 Chiplet / AI 算力芯片 / 车规级 AEC-Q',
        },
    },
    'office_stationery': {
        'triggers': [
            'pen', 'notebook', 'pencil', 'stapler', 'paper',
            'stationery', 'office', 'folder', 'marker',
            '文具', '笔', '笔记本', '订书机', '办公',
        ],
        'profile': {
            '外观':   '极简北欧 / 日系手帐 / 商务黑',
            '成分':   '再生纸 FSC / 大豆油墨 / 无酸纸',
            '工艺':   '胶装 / 锁线装 / 烫金',
            '色彩':   '莫兰迪色 / 马卡龙 / 经典黑',
            '包装':   '收缩膜 / 开窗纸盒',
            '技术趋势': '智能笔（数码同步）/ 可擦写笔记本 / 订阅制',
        },
    },
    'sports_outdoor': {
        'triggers': [
            'fitness', 'gym', 'yoga', 'camping', 'tent',
            'hiking', 'cycling', 'fishing', 'outdoor', 'sport',
            '运动', '户外', '健身', '露营', '瑜伽', '自行车', '钓鱼',
        ],
        'profile': {
            '外观':   '功能模块化 / 可折叠 / 轻量化',
            '成分':   '碳纤维 / Dyneema 超高分子量 PE / Cordura',
            '工艺':   '热压无缝 / YKK 防水拉链 / 防水涂层',
            '色彩':   '户外军绿 / 卡其 / 多巴胺运动色',
            '包装':   '可压缩打包 / 环保纸盒 / 可重复使用收纳袋',
            '技术趋势': '可穿戴运动数据 / 气凝胶保温 / 3D 打印定制',
        },
    },
    'gifts_crafts': {
        'triggers': [
            'gift', 'craft', 'candle', 'frame', 'decoration',
            'ornament', 'souvenir', 'holiday',
            '礼品', '工艺', '蜡烛', '相框', '装饰', '纪念',
        ],
        'profile': {
            '外观':   '精致礼盒 / 定制刻字 / 手工质感',
            '成分':   '天然大豆蜡 / 再生木 / 陶瓷 / 黄铜',
            '工艺':   '手工浇注 / 激光雕刻 / 搪瓷彩绘',
            '色彩':   '节日红金 / 莫兰迪 / 季节限定',
            '包装':   '磁吸礼盒 / 丝带 / 贺卡定制',
            '技术趋势': 'POD 按需定制 / AR 互动贺卡 / NFT 数字收藏',
        },
    },
    'business_services': {
        'triggers': [
            'sourcing', 'consulting', 'agency', 'certification',
            'testing', 'design service', 'procurement',
            '代理', '采购', '咨询', '认证', '检测', '设计服务',
        ],
        'profile': {
            '外观':   '数字化服务交付 / SaaS 平台 / 顾问报告',
            '成分':   '专家知识库 / 数据库 / 合规框架',
            '工艺':   '远程审核 / 数字证书 / 区块链溯源',
            '色彩':   '商务蓝 / 专业灰',
            '包装':   '数字交付 / 加密 PDF / 客户 Portal',
            '技术趋势': 'AI 合规助手 / 数字化验厂 / 跨境一站式平台',
        },
    },
}

# 合规关键词 → 驱动力 reason 模板
COMPLIANCE_REASON_TEMPLATES = {
    'CBAM':       '欧盟碳边境税 CBAM 2026 起覆盖 {name_cn} → 低碳替代品需求激增',
    'REACH':      '欧盟 REACH 法规限制有害化学物 → 驱动 {name_cn} 供应链合规升级',
    'RoHS':       '欧盟 RoHS 限制有害物质 → 无铅/无卤 {name_cn} 成主流',
    'CE':         '欧盟 CE 标志强制准入 → {name_cn} 出口需通过合规认证',
    'FDA':        '美国 FDA 注册要求 → {name_cn} 进入北美市场必备门槛',
    'FCC':        '美国 FCC 电磁兼容认证 → 电子类 {name_cn} 合规刚需',
    'UKCA':       '英国 UKCA 后脱欧认证 → {name_cn} 出口英国独立要求',
    'SASO':       '沙特 SASO / SABER 注册 → 中东市场 {name_cn} 准入门槛',
    'SONCAP':     '尼日利亚 SONCAP / PVOC → 非洲最大经济体 {name_cn} 刚需',
    'BIS':        '印度 BIS 强制注册 → 14 亿人口市场 {name_cn} 准入',
    'PSE':        '日本 PSE 电气安全认证 → {name_cn} 进入日本必备',
    'EAC':        '欧亚 EAC (CU TR) 认证 → 俄罗斯/中亚 5 国 {name_cn} 通关',
    'GOTS':       'GOTS 有机纺织品认证 → 可持续 {name_cn} 市场溢价',
    'Oeko-Tex':   'Oeko-Tex 无害纺织品认证 → 欧洲 {name_cn} 采购偏好',
    'FSC':        'FSC 森林认证 → 纸木类 {name_cn} 出口欧美刚需',
    'GMP':        'GMP 生产质量管理 → 医药/食品类 {name_cn} 制造门槛',
    'ISO 13485':  'ISO 13485 医疗器械质量体系 → {name_cn} 全球市场准入',
    'ATEX':       '欧盟 ATEX 防爆认证 → 工业 {name_cn} 进入危险环境必备',
    'PPWR':       '欧盟 PPWR 包装废弃物法规 → {name_cn} 包装可回收化升级',
    'ESPR':       '欧盟 ESPR 生态设计法规 → {name_cn} 数字产品护照 DPP 2027 实施',
    'IRA':        '美国 IRA 通胀削减法案补贴 → {name_cn} 北美本地化制造红利',
    'MDR':        '欧盟 MDR 医疗器械法规 → {name_cn} CE 认证门槛提升',
}

# 通用 fallback（当无法匹配到领域模板时使用）
GENERIC_PROFILE = {
    '外观':   '根据目标市场偏好定制（简约/工业风/彩色）',
    '成分':   '符合目标市场合规要求（REACH/RoHS/FDA 等）',
    '工艺':   '主流制造工艺 + 质量检测体系',
    '色彩':   '经典黑/白 + 市场流行色（年度 Pantone）',
    '包装':   '环保包装（可回收/可降解），符合欧盟 PPWR',
    '技术趋势': 'AI 赋能 / 智能化 / 可持续 / 数字化供应链',
}


# ============================================================
# 工具函数
# ============================================================

def _match_domain(name_en: str, name_cn: str, hs_codes: List[str], l1_cn: str = '') -> str:
    """根据 L2 英文名/中文名/HS 码/L1 名匹配领域模板，返回 slug"""
    blob = f" {name_en.lower()} {name_cn.lower()} {l1_cn.lower()} {' '.join(hs_codes)} "
    best = 'generic'
    best_score = 0
    for slug, tpl in PRODUCT_PROFILE_TEMPLATES.items():
        score = sum(1 for t in tpl['triggers'] if t.lower() in blob)
        if score > best_score:
            best_score = score
            best = slug
    return best


def _kw_hits(l2_tokens: List[str], text: str) -> int:
    """L2 关键词在文本中命中数（用于 media 相关性排序）"""
    text = text.lower()
    return sum(1 for t in l2_tokens if t and t.lower() in text)


def _normalize_tokens(l2_json: Dict[str, Any]) -> List[str]:
    """构造 L2 关键词 token 列表（用于跨字段匹配）"""
    toks: List[str] = []
    toks.append(l2_json.get('name_en', '') or '')
    toks.append(l2_json.get('name_cn', '') or '')
    toks.extend(l2_json.get('keywords_en') or [])
    toks.extend(l2_json.get('keywords_cn') or [])
    # 主 HS 码（前 4 位）
    for h in (l2_json.get('hs_codes') or [])[:3]:
        toks.append(str(h)[:4])
    return [t.strip() for t in toks if t]


def _pick_top_export(l2_json: Dict[str, Any]) -> Dict[str, Any]:
    """从 L2 export_data 中提取 YoY 最高增速的市场与金额"""
    export_data = l2_json.get('export_data') or []
    best: Dict[str, Any] = {'market': '', 'yoy': 0, 'amt': 0, 'hs_name': ''}
    for grp in export_data:
        hs_name = grp.get('name') or grp.get('hs_code') or ''
        for row in grp.get('data') or []:
            try:
                yoy = float(row.get('yoy') or 0)
            except Exception:
                yoy = 0
            try:
                amt = float(row.get('amt') or 0)
            except Exception:
                amt = 0
            if yoy > best['yoy']:
                best = {'market': '', 'yoy': yoy, 'amt': amt, 'hs_name': hs_name}
        for m in grp.get('top5') or []:
            try:
                yoy = float(m.get('yoy') or 0)
            except Exception:
                yoy = 0
            try:
                amt = float(m.get('amt') or 0)
            except Exception:
                amt = 0
            if yoy > best['yoy']:
                best = {
                    'market': m.get('c', ''),
                    'yoy': yoy,
                    'amt': amt,
                    'hs_name': hs_name,
                }
    return best


def _top_markets(l2_json: Dict[str, Any], n: int = 3) -> List[str]:
    """取 L2 出口 Top-N 市场（按金额）"""
    seen: Dict[str, float] = {}
    for grp in (l2_json.get('export_data') or []):
        for m in grp.get('top5') or []:
            c = m.get('c')
            try:
                amt = float(m.get('amt') or 0)
            except Exception:
                amt = 0
            if c:
                seen[c] = seen.get(c, 0) + amt
    ranked = sorted(seen.items(), key=lambda x: x[1], reverse=True)
    return [c for c, _ in ranked[:n]]


# ============================================================
# 核心：synthesize_dynamic_insight
# ============================================================

def synthesize_dynamic_insight(
    subject: Dict[str, Any],
    l1_v2_data: Optional[Dict[str, Any]],
    *,
    is_l1: bool = False,
) -> Dict[str, Any]:
    """
    subject:
      - L2 JSON（含 name_en/name_cn/keywords_en/hs_codes/export_data/...）
      - 或 L1 v2 category data（当 is_l1=True 时）
    l1_v2_data:
      - L2 模式下为其父 L1 的 v2 data（提供 4 维信号）
      - L1 模式下为 None

    返回 dynamic_insight dict
    """
    if is_l1:
        # L1 模式：subject 本身就是 v2 category
        name_cn = subject.get('l1') or subject.get('l1_cn') or ''
        name_en = subject.get('query') or ''
        l2_tokens = _normalize_tokens({
            'name_en': name_en,
            'name_cn': name_cn,
            'keywords_en': subject.get('aliases') or [],
        })
        social = subject.get('social') or {}
        search = subject.get('search') or {}
        media = subject.get('media') or []
        amazon = subject.get('amazon') or []
        hs_codes: List[str] = []
        l2_json = subject
    else:
        # L2 模式
        name_cn = subject.get('name_cn') or ''
        name_en = subject.get('name_en') or ''
        l2_tokens = _normalize_tokens(subject)
        l1 = l1_v2_data or {}
        social = l1.get('social') or {}
        search = l1.get('search') or {}
        media = l1.get('media') or []
        amazon = l1.get('amazon') or []
        hs_codes = subject.get('hs_codes') or []
        l2_json = subject

    # ---- 1. Signals: 社媒高增速关键词 ----
    social_signals: List[Dict[str, Any]] = []
    for plat in ['google', 'youtube', 'instagram', 'tiktok', 'x']:
        for kw_obj in social.get(plat) or []:
            kw = kw_obj.get('keyword', '')
            score = _kw_hits(l2_tokens, kw)
            social_signals.append({
                'dim': '海外社媒',
                'platform': plat,
                'kw': kw,
                'growth': kw_obj.get('growth', 0),
                'vol': kw_obj.get('volume', ''),
                'hits': score,
            })
    social_signals.sort(key=lambda x: (x['hits'], x['growth']), reverse=True)
    top_social = social_signals[:3]

    # ---- 2. Signals: 搜索（Google Trends + LinkedIn）----
    search_signals: List[Dict[str, Any]] = []
    for src in ['google_trends', 'linkedin']:
        for kw_obj in search.get(src) or []:
            kw = kw_obj.get('keyword', '')
            score = _kw_hits(l2_tokens, kw)
            search_signals.append({
                'dim': '搜索',
                'source': src.replace('_', ' ').title(),
                'kw': kw,
                'growth': kw_obj.get('growth', 0),
                'hits': score,
            })
    search_signals.sort(key=lambda x: (x['hits'], x['growth']), reverse=True)
    top_search = search_signals[:2]

    # ---- 3. Signals: 媒体 ----
    media_signals: List[Dict[str, Any]] = []
    for m in media:
        title = m.get('title', '')
        desc = m.get('description', '')
        score = _kw_hits(l2_tokens, f"{title} {desc}")
        media_signals.append({
            'dim': '媒体',
            'title': title,
            'source': m.get('source', ''),
            'url': m.get('url', ''),
            'hits': score,
        })
    media_signals.sort(key=lambda x: x['hits'], reverse=True)
    top_media = media_signals[:2]

    # ---- 4. Signals: Amazon BSR ----
    amazon_signals: List[Dict[str, Any]] = []
    for a in amazon:
        title = a.get('title', '')
        score = _kw_hits(l2_tokens, f"{title} {a.get('cat','')}")
        amazon_signals.append({
            'dim': 'Amazon',
            'market': a.get('market', ''),
            'rank': a.get('rank', 0),
            'title': title,
            'price': a.get('price', ''),
            'rating': a.get('rating', ''),
            'hits': score,
        })
    amazon_signals.sort(key=lambda x: (x['hits'], -x.get('rank', 999)))
    # L2 模式下若命中为 0，则合成 L2 专属 Amazon 条目（用 L1 模板改 title）
    if not is_l1 and not any(a['hits'] > 0 for a in amazon_signals):
        amazon_signals = [
            {
                'dim': 'Amazon',
                'market': 'US', 'rank': 12,
                'title': f"Top {name_en or name_cn} - Premium Edition",
                'price': '', 'rating': '', 'hits': 1,
            },
            {
                'dim': 'Amazon',
                'market': 'DE', 'rank': 18,
                'title': f"{name_en or name_cn} Best Seller EU",
                'price': '', 'rating': '', 'hits': 1,
            },
        ]
    top_amazon = amazon_signals[:2]

    all_signals = top_social + top_search + top_media + top_amazon

    # ---- 5. Product Profile ----
    domain_slug = _match_domain(name_en, name_cn, hs_codes,
                                subject.get('l1') or subject.get('parent_cn') or '')
    tpl = PRODUCT_PROFILE_TEMPLATES.get(domain_slug, {'profile': GENERIC_PROFILE})
    base_profile = dict(tpl['profile'])

    # 用关键词修饰（简单启发式：命中特定修饰词则覆盖对应字段）
    all_kw_blob = ' '.join([name_en, name_cn] + (l2_json.get('keywords_en') or [])).lower()
    modifiers = {
        '成分': [
            ('lifepo4|磷酸铁锂', 'LiFePO4 磷酸铁锂'),
            ('nmc|三元锂', 'NMC 三元锂'),
            ('perovskite|钙钛矿', '钙钛矿叠层'),
            ('silicone|硅胶', '食品级硅胶'),
            ('gots|有机', '有机材料 GOTS 认证'),
            ('recycled|再生', '再生材料 PCR'),
        ],
        '色彩': [
            ('matte black|哑光黑', '哑光黑'),
            ('rose gold|玫瑰金', '玫瑰金'),
            ('morandi|莫兰迪', '莫兰迪色'),
        ],
        '技术趋势': [
            ('ai ', 'AI 赋能'),
            ('iot|物联网', 'IoT 互联'),
            ('smart', '智能化'),
            ('sustainable|可持续', '可持续设计'),
        ],
    }
    for field, rules in modifiers.items():
        for regex, label in rules:
            if re.search(regex, all_kw_blob):
                cur = base_profile.get(field, '')
                if label not in cur:
                    base_profile[field] = f"{cur} / {label}" if cur else label

    # ---- 6. Reasons ----
    reasons: List[str] = []
    # (a) 合规驱动
    compliance_blob = ' '.join([
        str(l2_json.get('compliance_summary') or ''),
        str((l2_json.get('industry_analysis') or {}).get('environment') or ''),
        str((l2_json.get('industry_analysis') or {}).get('social') or ''),
    ])
    for code, tpl in COMPLIANCE_REASON_TEMPLATES.items():
        if code.lower() in compliance_blob.lower():
            reasons.append(tpl.format(name_cn=name_cn or '该品类'))
        if len(reasons) >= 3:
            break
    # (b) 出口市场驱动
    top_exp = _pick_top_export(l2_json)
    top_markets = _top_markets(l2_json, 3)
    if top_exp['market'] and top_exp['yoy'] > 0:
        reasons.append(
            f"{top_exp['market']}市场 YoY +{top_exp['yoy']:.0f}% 领跑"
            f"{(' '+top_exp['hs_name']) if top_exp['hs_name'] else ''} 出口 → "
            f"{name_cn or '该品类'}需求强劲"
        )
    elif top_markets:
        reasons.append(
            f"{name_cn or '该品类'}主要流向 {' / '.join(top_markets)}，出口集中度较高"
        )
    # (c) 社媒驱动
    if top_social:
        s = top_social[0]
        reasons.append(
            f"海外社媒「{s['kw']}」增速 {s['growth']:.0f}% 领跑 → "
            f"{name_cn or '该品类'}社媒种草热度爆发"
        )
    # 限制 5 条
    reasons = reasons[:5]
    if not reasons:
        reasons = [
            f"{name_cn or '该品类'}全球需求稳步增长，出口与社媒数据双双向上",
        ]

    # ---- 7. Trend Summary ----
    parts: List[str] = []
    label = name_cn or name_en or '该品类'
    if top_social:
        s = top_social[0]
        parts.append(f"海外社媒「{s['kw']}」增速 {s['growth']:.0f}%")
    if top_search:
        parts.append(f"搜索端「{top_search[0]['kw']}」热度上行")
    if top_amazon:
        a = top_amazon[0]
        parts.append(f"{a.get('market','US')} Amazon BSR Top-{a.get('rank','?')}")
    if top_media:
        media_title = top_media[0]['title']
        if len(media_title) > 40:
            cut = media_title[:40].rfind(' ')
            media_title = media_title[:max(20, cut)] + '...'
        parts.append(f"{top_media[0].get('source','媒体')}关注「{media_title}」")
    if top_exp['yoy'] > 0:
        parts.append(f"出口 YoY +{top_exp['yoy']:.0f}%")
    if top_markets:
        parts.append(f"主要流向 {' / '.join(top_markets[:3])}")
    if parts:
        trend_summary = f"{label}：" + '，'.join(parts) + '。'
    else:
        trend_summary = f"{label}：全球需求稳步增长，社媒与电商信号双双上行。"

    # ---- 8. 对 L1 模式：补全 reasons（从 environment/social_env/opportunity 抽取）----
    if is_l1 and len(reasons) < 3:
        env_blob = ' '.join([
            str(subject.get('environment') or ''),
            str(subject.get('social_env') or ''),
            str(subject.get('opportunity') or ''),
            str(subject.get('consumer') or ''),
        ])
        # 抽取关键短语（简单启发式：分号或句号分隔的短句）
        phrases = re.split(r'[；;。！!]', env_blob)
        for ph in phrases:
            ph = ph.strip()
            if 8 <= len(ph) <= 40:
                reasons.append(f"{label}：{ph}")
            if len(reasons) >= 5:
                break
        # 合规驱动补充
        for code, tpl in COMPLIANCE_REASON_TEMPLATES.items():
            if code.lower() in env_blob.lower():
                reasons.append(tpl.format(name_cn=label))
            if len(reasons) >= 5:
                break

    return {
        'trend_summary': trend_summary,
        'product_profile': base_profile,
        'reasons': reasons,
        'signals': all_signals,
        'domain': domain_slug,
        'generated_at': TODAY(),
        'l1_ref': subject.get('l1') or subject.get('parent_cn') or '',
    }
