import logging
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol
import aiohttp
import json
from .const import DOMAIN, PLATFORM_NAME, DEFAULT_SCAN_INTERVAL, MIN_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

class StockMarketConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """处理股票市场集成的配置流程"""
    VERSION = 1
    
    def __init__(self):
        """初始化配置流程"""
        pass
    
    async def async_step_user(self, user_input=None):
        """配置流程的初始步骤 - 显示配置表单"""
        _LOGGER.info("进入配置表单步骤")
        errors = {}
        
        if user_input is not None:
            stock_symbol = user_input.get("stock_symbol", "").strip()
            stock_name = user_input.get("stock_name", "").strip()
            
            if not stock_symbol:
                errors["stock_symbol"] = "empty_symbol"
            elif not stock_name:
                errors["stock_name"] = "empty_name"
            else:
                try:
                    # 生成唯一ID，使用完整的股票符号
                    unique_id = f"stock_{stock_symbol.lower().replace('.', '_')}"
                    
                    # 检查是否已经存在相同的配置
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    
                    # 解析市场类型（可选）
                    if '.' in stock_symbol:
                        market_code = stock_symbol.split('.')[-1].lower()
                        market_type_map = {
                            'ss': '上证',
                            'sz': '深证',
                            'hk': '港股',
                            'us': '美股'
                        }
                        market_type = market_type_map.get(market_code, "未知")
                    else:
                        market_type = "未知"
                    
                    # 创建配置条目
                    _LOGGER.info(f"创建配置条目: {unique_id}")
                    return self.async_create_entry(
                        title=f"{stock_name} ({stock_symbol})",
                        data={
                            "stock_code": stock_symbol,  # 直接使用完整的股票符号
                            "stock_name": stock_name,
                            "market_type": market_type,
                            "market_code": ""  # 市场代码不再使用，留空
                        }
                    )
                except Exception as e:
                    _LOGGER.error(f"配置验证失败: {str(e)}")
                    errors["base"] = "configuration_failed"
        
        # 构建表单结构，使用标准的vol.Schema定义
        data_schema = vol.Schema({
            vol.Required("stock_symbol"): str,
            vol.Required("stock_name"): str
        })
        
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "stock_symbol": "完整的雅虎金融股票符号，如000001.SS、AAPL.US、0700.HK",
                "stock_name": "股票名称，用于显示"
            }
        )
    
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """获取选项流程"""
        return StockMarketOptionsFlow(config_entry)

class StockMarketOptionsFlow(config_entries.OptionsFlow):
    """处理股票市场集成的选项流程"""
    
    def __init__(self, config_entry):
        """初始化选项流程"""
        pass
    
    async def async_step_init(self, user_input=None):
        """处理选项初始化步骤"""
        if user_input is not None:
            # 更新配置选项
            return self.async_create_entry(title="", data=user_input)
        
        # 使用基类提供的config_entry属性访问选项
        scan_interval = self.config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        
        # 显示选项表单
        data_schema = vol.Schema({
            vol.Required("scan_interval", default=scan_interval): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=86400)),
        })
        
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            description_placeholders={
                "scan_interval": "数据刷新间隔（秒）",
            }
        )