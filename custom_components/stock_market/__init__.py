import asyncio
import logging
from datetime import datetime, timedelta, time
import aiohttp
import json
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import (
    DOMAIN, 
    API_BASE_URL, 
    DEFAULT_FIELDS, 
    STOCK_PREFIXES, 
    FIELD_MAPPING,
    MARKET_TRADING_HOURS,
    DEFAULT_SCAN_INTERVAL_TRADE,
    DEFAULT_SCAN_INTERVAL_NON_TRADE
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
    coordinator = StockDataUpdateCoordinator(hass, _LOGGER, entry)
    
    # 注册协调器到hass数据中
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # 立即尝试更新数据
    await coordinator.async_config_entry_first_refresh()
    
    # 设置平台（使用更新的方法）
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # 支持选项更新
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """卸载配置条目"""
    # 使用更新的方法卸载平台
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """重新加载配置条目"""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

class StockDataUpdateCoordinator(DataUpdateCoordinator):
    """股票数据更新协调器"""
    def __init__(self, hass, logger, entry):
        self.hass = hass
        self.entry = entry
        self.stock_code = entry.data.get("stock_code")
        self.stock_name = entry.data.get("stock_name")
        self.market_type = entry.data.get("market_type")
        self.market_code = entry.data.get("market_code")  # 直接从配置中获取市场代码
        
        # 获取交易时间段和非交易时间段的更新间隔
        self.scan_interval_trade = entry.options.get("scan_interval_trade", DEFAULT_SCAN_INTERVAL_TRADE)
        self.scan_interval_non_trade = entry.options.get("scan_interval_non_trade", DEFAULT_SCAN_INTERVAL_NON_TRADE)
        
        # 使用市场代码和股票代码组合作为名称，确保不同市场的相同股票代码不会冲突
        coordinator_name = f"{DOMAIN}_{self.market_code}_{self.stock_code}"
        
        # 初始使用非交易时间段的更新间隔
        initial_interval = self._get_current_scan_interval()
        
        super().__init__(
            hass,
            logger,
            name=coordinator_name,
            update_interval=timedelta(seconds=initial_interval),
        )
        
        # 存储上一次的更新间隔，用于检测变化
        self._last_used_interval = initial_interval
    
    def _is_trading_hours(self):
        """判断当前是否处于交易时间段内"""
        # 获取当前时间（北京时间）
        now = datetime.now().time()
        today = datetime.now().weekday()
        
        # 检查是否为周末（不同市场可能有不同的交易日历，这里简化处理）
        if today >= 5:  # 0=周一, 1=周二, ..., 4=周五, 5=周六, 6=周日
            return False
        
        # 获取该市场的交易时间段配置
        trading_hours = MARKET_TRADING_HOURS.get(self.market_type, [])
        
        # 检查是否在任何一个交易时间段内
        for start_time_str, end_time_str in trading_hours:
            # 解析时间字符串为time对象
            start_time = time.fromisoformat(start_time_str)
            end_time = time.fromisoformat(end_time_str)
            
            # 处理跨午夜的情况（如美股）
            if start_time > end_time:
                # 如果当前时间在开始时间到23:59或00:00到结束时间之间，则处于交易时间
                if now >= start_time or now <= end_time:
                    return True
            else:
                # 正常的时间段判断
                if start_time <= now <= end_time:
                    return True
        
        return False
        
    def _get_current_scan_interval(self):
        """根据当前是否处于交易时间段返回相应的更新间隔"""
        if self._is_trading_hours():
            return self.scan_interval_trade
        else:
            return self.scan_interval_non_trade
            
    async def _async_update_data(self):
        """异步更新数据"""
        try:
            # 检查并调整更新间隔
            current_interval = self._get_current_scan_interval()
            if current_interval != self._last_used_interval:
                self.update_interval = timedelta(seconds=current_interval)
                self._last_used_interval = current_interval
                _LOGGER.debug(f"调整更新间隔: {current_interval}秒, 交易时间: {self._is_trading_hours()}")
                
            # 直接使用保存的市场代码构建完整股票代码，避免映射错误
            full_code = f"{self.market_code}.{self.stock_code}"
            
            # 构建API请求URL
            url = f"{API_BASE_URL}?fltt=2&fields={DEFAULT_FIELDS}&secids={full_code}"
            
            _LOGGER.debug(f"获取股票数据: {self.stock_name}({self.stock_code}), 市场类型: {self.market_type}, 完整代码: {full_code}, URL: {url}")
            
            # 发送请求获取数据
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"请求失败，状态码: {response.status}")
                    
                    # 解析响应数据
                    # 先获取文本内容，然后手动解析为JSON（处理text/plain类型响应）
                    text_content = await response.text()
                    try:
                        data = json.loads(text_content)
                    except json.JSONDecodeError as e:
                        raise UpdateFailed(f"解析JSON数据失败: {str(e)}")
                    
                    # 检查数据是否有效
                    if data.get("rc") != 0:
                        error_code = data.get("rc")
                        market_specific_error = f"{self.market_type}市场的股票数据获取失败。请注意，不同市场可能需要特定的API支持。\n" \
                                              f"股票代码: {self.stock_code}\n" \
                                              f"完整代码: {full_code}\n" \
                                              f"请检查股票代码是否正确或尝试其他市场类型。"
                        
                        raise UpdateFailed(f"API返回错误 (代码: {error_code}): {market_specific_error}")
                    
                    # 提取股票数据
                    stock_data = data.get("data", {}).get("diff", [])
                    if not stock_data:
                        raise UpdateFailed(f"未找到股票数据: {self.stock_code}")
                    
                    # 将API返回的字段映射为有意义的名称
                    mapped_data = self._map_stock_data(stock_data[0])
                    
                    # 添加元数据
                    mapped_data["timestamp"] = datetime.now().isoformat()
                    
                    _LOGGER.debug(f"成功获取股票数据: {mapped_data}")
                    
                    return mapped_data
        except Exception as e:
            _LOGGER.error(f"获取股票数据失败: {str(e)}")
            raise UpdateFailed(f"获取股票数据失败: {str(e)}")
    
    def _map_stock_data(self, raw_data):
        """将原始数据映射为有意义的字段名称"""
        mapped_data = {}
        
        for key, value in raw_data.items():
            # 使用映射表转换字段名
            field_name = FIELD_MAPPING.get(key, key)
            mapped_data[field_name] = value
        
        # 确保股票名称和代码正确
        if "name" not in mapped_data or not mapped_data["name"]:
            mapped_data["name"] = self.stock_name
        if "code" not in mapped_data or not mapped_data["code"]:
            mapped_data["code"] = self.stock_code
        
        return mapped_data