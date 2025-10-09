# 集成域名
DOMAIN = "stock_market"

# 平台名称
PLATFORM_NAME = "stock_market"

# API基础URL和参数
API_BASE_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
DEFAULT_FIELDS = "f12,f13,f19,f14,f139,f148,f2,f4,f1,f125,f18,f3,f152,f5,f30,f31,f32,f6,f8,f7,f10,f22,f9,f112,f100,f88,f153"

# 搜索API配置
SEARCH_API_URL = "https://searchapi.eastmoney.com/api/suggest/get"
SEARCH_FIELDS = "11,12,13,14,15,16,17"

# 股票代码前缀映射
STOCK_PREFIXES = {
    # 国内市场
    "上证": "1.",
    "深证": "0.",
    "科创": "1.",
    "中小板": "0.",
    "创业板": "0.",
    # 国外市场
    "美股": "105.",
    "港股": "116.",
    "日股": "122.",
    "英股": "124.",
    "德股": "125."
}

# 市场类型与证券类型映射
MARKET_SECURITY_TYPE = {
    "上证": "1",
    "深证": "0",
    "科创": "1",
    "中小板": "0",
    "创业板": "0",
    "美股": "105",
    "港股": "116",
    "日股": "122",
    "英股": "124",
    "德股": "125"
}

# 字段映射表（将API返回的f1, f2等字段映射到有意义的名称）
FIELD_MAPPING = {
    "f1": "type",
    "f2": "current_price",  # 当前价格
    "f3": "change_percent",  # 涨跌幅（百分比）
    "f4": "change_amount",  # 涨跌额
    "f5": "volume",  # 成交量
    "f6": "turnover",  # 成交额
    "f7": "amplitude",  # 振幅
    "f8": "turnover_rate",  # 换手率
    "f9": "unknown1",
    "f10": "unknown2",
    "f12": "code",  # 股票代码
    "f13": "market_type",  # 市场类型
    "f14": "name",  # 股票名称
    "f18": "prev_close",  # 昨收价
    "f19": "unknown3",
    "f22": "unknown4",
    "f30": "unknown5",
    "f31": "unknown6",
    "f32": "unknown7",
    "f88": "unknown8",
    "f100": "unknown9",
    "f112": "unknown10",
    "f125": "unknown11",
    "f139": "unknown12",
    "f148": "unknown13",
    "f152": "unknown14",
    "f153": "unknown15"
}

# 传感器默认名称和图标
DEFAULT_SENSOR_NAME = "股票信息"
DEFAULT_SENSOR_ICON = "mdi:chart-line"

# 实体状态属性单位
UNIT_CURRENT_PRICE = "元"
UNIT_CHANGE_AMOUNT = "元"
UNIT_VOLUME = "手"
UNIT_TURNOVER = "亿"
UNIT_TURNOVER_RATE = "%"
UNIT_AMPLITUDE = "%"