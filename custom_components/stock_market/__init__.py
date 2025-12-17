import logging
import time
import asyncio
import re
from datetime import timedelta
import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import (
    DOMAIN, 
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    DATA_SOURCE_SINA,
    REQUEST_TIMEOUT,
    MAX_LINE_SIZE,
    SINA_API_BASE_URL,
    SINA_REQUEST_TIMEOUT
)

_LOGGER = logging.getLogger(__name__)

# 平台类型
PLATFORMS = ["sensor"]

async def async_setup(hass: HomeAssistant, config: dict):
    """设置集成组件"""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """设置配置条目"""
    # 创建数据更新协调器
    coordinator = StockDataCoordinator(hass, _LOGGER, entry)
    
    # 注册协调器到hass数据中
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # 立即尝试更新数据
    await coordinator.async_config_entry_first_refresh()
    
    # 设置平台（使用更新的方法）
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # 支持选项更新
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """卸载配置条目"""
    # 使用更新的方法卸载平台
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return True

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """更新配置选项"""
    # 获取现有的协调器
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # 更新协调器的刷新间隔
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    coordinator.update_interval = timedelta(seconds=scan_interval)
    
    # 触发立即更新
    await coordinator.async_refresh()

class StockDataCoordinator(DataUpdateCoordinator):
    """股票数据更新协调器，仅使用新浪财经数据源"""
    def __init__(self, hass, logger, entry):
        self.hass = hass
        self.entry = entry
        self.stock_code = entry.data.get("stock_code")
        self.stock_name = entry.data.get("stock_name")
        self.data_source = DATA_SOURCE_SINA  # 固定使用新浪数据源
        
        # 获取刷新间隔，优先使用选项中的配置，否则使用默认值
        scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        
        # 创建会话，增加max_field_size和max_line_size以避免Header过长错误
        self.websession = async_create_clientsession(
            hass, 
            max_field_size=MAX_LINE_SIZE, 
            max_line_size=MAX_LINE_SIZE
        )
        
        # 使用股票代码作为名称
        coordinator_name = f"{DOMAIN}_{self.stock_code}_{self.data_source}"
        
        super().__init__(
            hass,
            logger,
            name=coordinator_name,
            update_interval=timedelta(seconds=scan_interval),
        )
    
    async def _fetch_sina_data(self):
        """从新浪API获取数据"""
        _LOGGER.info(f"从新浪API获取股票数据: {self.stock_name}({self.stock_code})")
        
        # 直接使用用户输入的股票代码格式，例如sh000001、sz002594
        sina_symbol = self.stock_code.strip()
        
        # 构建新浪API请求URL，正确格式为http://hq.sinajs.cn/list=sh000001
        url = f"{SINA_API_BASE_URL}/list={sina_symbol}"
        _LOGGER.info(f"新浪API请求URL: {url}")
        
        try:
            async with asyncio.timeout(SINA_REQUEST_TIMEOUT):
                # 添加请求头，模拟浏览器访问
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Referer": "http://finance.sina.com.cn/",
                    "Accept-Language": "zh-CN,zh;q=0.9"
                }
                response = await self.websession.get(url, headers=headers)
                
                _LOGGER.info(f"新浪API响应状态: {response.status}")
                
                if response.status == 200:
                    # 新浪API返回的是JavaScript字符串格式，例如：var hq_str_sh000001="上证指数,3000.00,1.00,0.03,10000000,100000000";
                    # 新浪API返回的是GB2312编码，需要转换为UTF-8
                    result_bytes = await response.read()
                    result_text = result_bytes.decode('gb2312', errors='replace')
                    _LOGGER.info(f"新浪API原始响应: {result_text}")
                    
                    # 解析新浪API返回的字符串格式
                    # 格式：var hq_str_sh000001="股票名称,当前价格,昨收价,今开价,最高价,最低价,买一价,卖一价,成交量,成交额,买一量,买一价,买二量,买二价,...";
                    pattern = r'var hq_str_\w+="([^"]+)";'  # 匹配引号内的内容
                    match = re.search(pattern, result_text)
                    
                    if match:
                        stock_data_str = match.group(1)
                        stock_data_list = stock_data_str.split(',')
                        _LOGGER.info(f"新浪API解析后的数据列表: {stock_data_list}")
                        
                        if len(stock_data_list) >= 11:  # 确保有足够的数据字段
                            # 解析数据
                            name = stock_data_list[0]
                            _LOGGER.info(f"解析股票名称: {name}")
                            
                            # 确保价格字段可以转换为浮点数
                            try:
                                # 新浪API字段顺序：
                                # 0: 股票名称
                                # 1: 今开价
                                # 2: 昨收价
                                # 3: 当前价格
                                # 4: 最高价
                                # 5: 最低价
                                # 6: 买一价
                                # 7: 卖一价
                                # 8: 成交量
                                # 9: 成交额
                                open_price = float(stock_data_list[1])
                                prev_close = float(stock_data_list[2])
                                current_price = float(stock_data_list[3])  # 当前价格在索引3
                                volume = int(stock_data_list[8])  # 成交量
                                
                                _LOGGER.info(f"解析价格数据 - 当前价格: {current_price}, 昨收价: {prev_close}, 今开价: {open_price}")
                                
                                # 计算涨跌幅和涨跌额
                                change_amount = current_price - prev_close
                                change_percent = (change_amount / prev_close) * 100 if prev_close != 0 else 0
                                
                                # 构建返回数据
                                stock_data = {
                                    "current_price": current_price,
                                    "change_amount": change_amount,
                                    "change_percent": round(change_percent, 2),  # 保留两位小数
                                    "prev_close": prev_close,
                                    "open_price": open_price,
                                    "volume": volume,
                                    "name": name,
                                    "code": self.stock_code,
                                    "currency": "CNY",  # 新浪API主要针对A股，默认使用人民币
                                    "timestamp": time.time()
                                }
                                _LOGGER.info(f"最终解析后的股票数据: {stock_data}")
                                return stock_data
                            except ValueError as e:
                                _LOGGER.error(f"解析价格数据失败: {e}, 原始数据: {stock_data_list[1:4]}")
                                return None
                        else:
                            _LOGGER.error(f"新浪API返回的数据字段不足，期望至少11个字段，实际得到: {len(stock_data_list)}个字段")
                    else:
                        _LOGGER.error(f"新浪API响应格式错误，无法匹配数据，正则表达式: {pattern}")
                else:
                    _LOGGER.error(f"新浪API请求失败，状态码: {response.status}, 响应头: {dict(response.headers)}")
        except asyncio.TimeoutError:
            _LOGGER.error(f"新浪API请求超时")
        except aiohttp.ClientError as e:
            _LOGGER.error(f"新浪API请求客户端错误: {str(e)}")
        except Exception as e:
            _LOGGER.error(f"新浪API请求未知错误: {str(e)}", exc_info=True)
        
        return None
    
    async def _async_update_data(self):
        """异步更新数据 - 仅使用新浪财经API"""
        _LOGGER.debug(f"获取股票数据: {self.stock_name}({self.stock_code})，数据源: {self.data_source}")
        
        # 使用新浪API获取数据
        data = await self._fetch_sina_data()
        if data:
            return data
        else:
            raise UpdateFailed("无法从新浪API获取数据")