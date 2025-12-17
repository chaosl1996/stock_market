# 股票市场信息集成 - 国内数据源扩展

## 国内可用的免费股票数据API

根据搜索结果，国内常用的免费股票数据API包括：

### 1. 新浪股票接口
- **优势**：免费、国内可用、数据可靠
- **主要功能**：提供实时股价、涨跌幅、成交量等基本数据
- **示例接口**：`http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sz000001&scale=5&ma=5&datalen=1023`
- **适用范围**：A股（上证、深证）为主

### 2. 雪球股票数据
- **优势**：提供股票行情和财务数据
- **主要功能**：实时股价、财务报表、股东信息等
- **示例接口**：需通过雪球API获取
- **适用范围**：A股、港股、美股

### 3. 网易财经API
- **优势**：免费、数据全面
- **主要功能**：实时行情、历史数据、财务数据
- **适用范围**：A股、港股、美股

## 如何将集成切换到国内数据源

### 方案1：修改现有集成，支持国内数据源

1. **修改const.py**：
   - 添加国内数据源的API端点
   - 配置不同数据源的参数

2. **修改__init__.py**：
   - 添加数据源选择逻辑
   - 实现国内数据源的请求处理
   - 适配不同数据源的数据格式

3. **修改sensor.py**：
   - 适配不同数据源的数据结构
   - 确保属性映射正确

### 方案2：创建新的集成分支，专门用于国内数据源

- 创建一个新的分支，专门使用国内数据源
- 保留现有集成的结构，只修改数据获取部分
- 这样可以同时支持国内外数据源

## 新浪股票接口示例实现

以下是使用新浪股票接口的示例代码片段：

### 1. 添加新浪API配置（const.py）
```python
# 新浪股票API配置
SINA_API_BASE_URL = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php"
SINA_API_ENDPOINTS = {
    "realtime": "CN_MarketData.getKLineData",
    "quote": "CN_MarketData.getQuote"
}
```

### 2. 实现新浪API请求处理（__init__.py）
```python
async def _fetch_sina_data(self, symbol):
    """从新浪API获取数据"""
    url = f"{SINA_API_BASE_URL}/{SINA_API_ENDPOINTS['quote']}?symbol={symbol}"
    try:
        async with self.websession.get(url) as response:
            if response.status == 200:
                data = await response.json()
                # 解析新浪数据格式
                return {
                    "current_price": float(data.get("price")),
                    "change_amount": float(data.get("pricechange")),
                    "change_percent": float(data.get("changepercent")),
                    "prev_close": float(data.get("preclose")),
                    "volume": int(data.get("volume")),
                    "name": data.get("name"),
                    "code": symbol
                }
    except Exception as e:
        _LOGGER.error(f"新浪API请求失败: {str(e)}")
    return None
```

## 注意事项

1. **API调用频率**：
   - 新浪等免费API可能有调用频率限制
   - 建议设置合理的刷新间隔（如30秒-5分钟）

2. **数据格式**：
   - 不同数据源的数据格式可能不同
   - 需要适配不同数据源的数据结构

3. **API稳定性**：
   - 免费API的稳定性可能不如付费API
   - 建议添加适当的错误处理和重试机制

4. **数据更新频率**：
   - 不同数据源的更新频率可能不同
   - 新浪股票API的更新频率约为3-5秒

## 推荐配置

- **A股**：使用新浪股票API或网易财经API
- **港股/美股**：使用雪球API或继续使用雅虎金融API（如果可以访问）
- **国内用户**：优先使用新浪股票API，稳定性高，国内访问速度快

## 结论

对于国内用户来说，新浪股票API是一个不错的选择，它提供免费、稳定的股票数据，且在国内访问速度快。如果您需要将stock_market集成切换到国内数据源，建议优先考虑新浪股票API。

如果您需要帮助实现这一功能，我可以提供更详细的指导和代码实现。