import logging
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol
import aiohttp
import json
from .const import DOMAIN, PLATFORM_NAME

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
            full_code = user_input.get("full_code", "").strip()
            stock_name = user_input.get("stock_name", "").strip()
            
            if not full_code:
                errors["full_code"] = "empty_code"
            elif not stock_name:
                errors["stock_name"] = "empty_name"
            else:
                try:
                    # 解析完整代码，格式应为"市场代码.股票代码"，例如"1.000010"或"105.NDAQ"
                    parts = full_code.split('.')
                    if len(parts) != 2 or not parts[0].isdigit():
                        errors["full_code"] = "invalid_format"
                    else:
                        # 股票代码可以包含字母和数字，只需要确保不为空
                        if not parts[1].strip():
                            errors["full_code"] = "invalid_format"
                        else:
                            market_code = parts[0]
                            stock_code = parts[1]
                            
                            # 根据市场代码映射市场类型
                            market_type_map = {
                                '1': '上证',
                                '0': '深证',
                                '105': '美股',
                                '116': '港股',
                                '122': '日股',
                                '124': '英股',
                                '125': '德股'
                            }
                            market_type = market_type_map.get(market_code, "未知")
                            
                            # 生成唯一ID，包含完整的市场代码以区分不同市场的相同股票代码
                            unique_id = f"stock_{market_code}_{stock_code}"
                            
                            # 检查是否已经存在相同的配置
                            await self.async_set_unique_id(unique_id)
                            self._abort_if_unique_id_configured()
                            
                            # 创建配置条目
                            _LOGGER.info(f"创建配置条目: {unique_id}")
                            return self.async_create_entry(
                                title=f"{stock_name} ({market_code}.{stock_code})",
                                data={
                                    "stock_code": stock_code,
                                    "stock_name": stock_name,
                                    "market_type": market_type,
                                    "market_code": market_code  # 保存市场代码以便区分不同市场
                                }
                            )
                except Exception as e:
                    _LOGGER.error(f"配置验证失败: {str(e)}")
                    errors["base"] = "configuration_failed"
        
        # 构建表单结构，使用标准的vol.Schema定义
        data_schema = vol.Schema({
            vol.Required("full_code"): str,
            vol.Required("stock_name"): str
        })
        
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "full_code": "市场代码.股票代码，如1.000010（上证）、105.NDAQ（美股）\n市场代码参考：1=上证, 0=深证, 105=美股, 116=港股, 122=日股, 124=英股, 125=德股",
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
        # 不再显式设置config_entry属性，使用基类提供的属性
        pass
    
    async def async_step_init(self, user_input=None):
        """处理选项初始化步骤"""
        if user_input is not None:
            # 更新配置选项
            return self.async_create_entry(title="", data=user_input)
        
        # 使用基类提供的config_entry属性访问选项
        scan_interval = self.config_entry.options.get("scan_interval", 300)
        
        # 显示选项表单
        data_schema = vol.Schema({
            vol.Required("scan_interval", default=scan_interval): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
        })
        
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            description_placeholders={
                "scan_interval": "数据刷新间隔（秒）"
            }
        )