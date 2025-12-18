import logging
from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN, DATA_SOURCE_SINA, DEFAULT_SCAN_INTERVAL, MIN_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

class StockMarketConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    
    async def async_step_user(self, user_input=None):
        if user_input:
            entry_data = {
                "stock_code": user_input["stock_code"],
                "stock_name": user_input["stock_name"],
                "data_source": DATA_SOURCE_SINA,  # 固定使用新浪数据源
                "market_type": "未知",
                "market_code": ""
            }
            return self.async_create_entry(title=user_input["stock_name"], data=entry_data)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("stock_code", description="股票代码（新浪财经格式，如sh000001、sh600519）"): str,
                vol.Required("stock_name", description="股票名称"): str
            })
        )
    
    @staticmethod
    def async_get_options_flow(config_entry):
        """获取选项流"""
        # 创建OptionsFlow实例，不需要直接传递config_entry参数
        # Home Assistant会在内部处理config_entry的设置
        return StockMarketOptionsFlow()

class StockMarketOptionsFlow(config_entries.OptionsFlow):
    """股票市场选项流"""
    
    # 不需要显式设置config_entry，基类已经提供了该属性
    
    async def async_step_init(self, user_input=None):
        """处理配置选项更新"""
        if user_input:
            # 更新配置选项
            return self.async_create_entry(title="", data=user_input)
        
        # 获取当前配置
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    "scan_interval", 
                    default=self.config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL),
                    description="数据刷新间隔（秒）"
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=86400))
            })
        )
