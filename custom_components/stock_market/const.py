# 集成域名
DOMAIN = "stock_market"

# 平台名称
PLATFORM_NAME = "stock_market"

# 传感器默认名称和图标
DEFAULT_SENSOR_NAME = "股票信息"
DEFAULT_SENSOR_ICON = "mdi:chart-line"

# 默认更新间隔配置
DEFAULT_SCAN_INTERVAL = 10800  # 默认更新间隔（秒），从2小时增加到3小时
MIN_SCAN_INTERVAL = 30  # 最小更新间隔（秒）

# 新浪股票API配置
SINA_API_BASE_URL = "https://hq.sinajs.cn"
SINA_REQUEST_TIMEOUT = 10
REQUEST_TIMEOUT = 10
MAX_LINE_SIZE = 8190 * 5

# 数据源常量
DATA_SOURCE_SINA = "sina"