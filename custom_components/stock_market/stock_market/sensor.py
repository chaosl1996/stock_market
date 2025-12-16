from datetime import datetime
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import (
    DOMAIN, 
    DEFAULT_SENSOR_NAME, 
    DEFAULT_SENSOR_ICON
)

class StockMarketSensor(CoordinatorEntity, SensorEntity):
    """股票市场传感器"""
    _attr_has_entity_name = True
    _attr_icon = DEFAULT_SENSOR_ICON
    _attr_device_class = "monetary"
    _attr_state_class = "measurement"

    def __init__(self, coordinator, config_entry):
        """初始化传感器"""
        super().__init__(coordinator)
        # 使用市场类型和股票代码生成唯一ID，以区分同一代码但不同市场类型的股票
        stock_code = config_entry.data.get('stock_code')
        market_type = config_entry.data.get('market_type')
        self._attr_unique_id = f"{DOMAIN}_{market_type}_{stock_code}"
        self.stock_code = stock_code
        self.stock_name = config_entry.data.get('stock_name')
        
        # 设置实体名称为股票名称（将在API数据更新后自动显示实际名称）
        self._attr_name = self.stock_name
        
        # 初始单位为空，将根据API返回的货币类型设置
        self._attr_unit_of_measurement = ""

    @property
    def state(self):
        """返回传感器状态（当前价格）"""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("current_price")
    
    def _handle_coordinator_update(self) -> None:
        """当协调器数据更新时调用此方法"""
        # 当API返回新数据时，更新实体名称为最新的股票名称
        if self.coordinator.data:
            if self.coordinator.data.get("name"):
                self._attr_name = self.coordinator.data.get("name")
            # 设置单位为货币符号（从API数据中获取）
            if self.coordinator.data.get("currency"):
                self._attr_unit_of_measurement = self.coordinator.data.get("currency")
        # 调用父类方法通知状态更新
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self):
        """返回额外的状态属性"""
        if self.coordinator.data is None:
            return {}
        
        # 获取原始数据
        data = self.coordinator.data
        
        # 构建额外属性，使用Home Assistant标准单位属性
        attributes = {
            "stock_name": data.get("name", self.stock_name),
            "stock_code": data.get("code", self.stock_code),
            "change_percent": data.get("change_percent"),
            "change_amount": data.get("change_amount"),
            "prev_close": data.get("prev_close"),
            "volume": data.get("volume"),
            "regular_market_volume": data.get("regularMarketVolume"),
            "market_cap": data.get("marketCap"),
            "average_volume": data.get("averageVolume"),
            "market_state": data.get("marketState"),
            "quote_type": data.get("quoteType"),
            "currency": data.get("currency")
        }
        
        # 转换timestamp为可读的时间日期格式
        timestamp = data.get("timestamp")
        if timestamp:
            attributes["timestamp"] = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        
        # 过滤掉值为None的属性
        attributes = {k: v for k, v in attributes.items() if v is not None}
        
        return attributes

    @property
    def device_info(self):
        """返回设备信息"""
        return {
            "identifiers": {(DOMAIN, f"{self.stock_code}")},
            "name": self.stock_name,
            "manufacturer": "Yahoo Finance",
            "model": "股票数据",
            "sw_version": "1.0"
        }

async def async_setup_entry(hass, config_entry, async_add_entities):
    """设置传感器平台"""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([StockMarketSensor(coordinator, config_entry)])