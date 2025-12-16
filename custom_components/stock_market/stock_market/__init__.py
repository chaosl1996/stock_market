import logging
import time
import asyncio
import random
from datetime import timedelta
from typing import Dict, Optional
import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import (
    DOMAIN, 
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL
)

_LOGGER = logging.getLogger(__name__)

# 平台类型
PLATFORMS = ["sensor"]

# 使用参考集成的API端点
BASE_URL = "https://query1.finance.yahoo.com/v7/finance/quote?symbols="

# 初始URL和crumb相关配置
INITIAL_URL = "https://finance.yahoo.com/quote/NQ%3DF/"
CONSENT_HOST = "consent.yahoo.com"
GET_CRUMB_URL = "https://query2.finance.yahoo.com/v1/test/getcrumb"

# 初始请求头
INITIAL_REQUEST_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": "Mozilla/5.0",
}

# 参考集成的User-Agent列表，用于轮换
USER_AGENTS_FOR_XHR = [
    "Mozilla/5.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
]

# 参考集成的请求头
XHR_REQUEST_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-encoding": "gzip,deflate,br,zstd",
    "accept-language": "en-US,en;q=0.9"
}

# 请求超时时间
REQUEST_TIMEOUT = 10

# 增加最大行大小，避免"Got more than 8190 bytes"错误
MAX_LINE_SIZE = 8190 * 5

# Crumb重试配置
CRUMB_RETRY_DELAY = 15
CRUMB_RETRY_DELAY_429 = 60

# 数据类：用于存储同意信息
class ConsentData:
    def __init__(self, need_consent=False, consent_content=None, consent_post_url=None, successful_consent_url=None):
        self.need_consent = need_consent
        self.consent_content = consent_content
        self.consent_post_url = consent_post_url
        self.successful_consent_url = successful_consent_url

# Crumb协调器类，用于管理crumb和cookie
class CrumbCoordinator:
    """Class to gather crumb/cookie details."""
    
    _instance = None
    """Static instance of CrumbCoordinator."""
    
    preferred_user_agent = ""
    """The preferred (last successful) user agent."""
    
    def __init__(self, hass: HomeAssistant, websession: aiohttp.ClientSession) -> None:
        """Initialize."""
        self.cookies = None
        """Cookies for requests."""
        self.crumb = None
        """Crumb for requests."""
        self._hass = hass
        self.retry_duration = CRUMB_RETRY_DELAY
        """Crumb retry request delay."""
        self._crumb_retry_count = 0
        self._websession = websession
    
    @staticmethod
    def get_static_instance(
        hass: HomeAssistant, websession: aiohttp.ClientSession
    ) -> "CrumbCoordinator":
        """Get the singleton static CrumbCoordinator instance."""
        if CrumbCoordinator._instance is None:
            CrumbCoordinator._instance = CrumbCoordinator(hass, websession)
        return CrumbCoordinator._instance
    
    def reset(self) -> None:
        """Reset crumb and cookies."""
        self.crumb = self.cookies = None
    
    async def try_get_crumb_cookies(self) -> str | None:
        """Try to get crumb and cookies for data requests."""
        
        consent_data = await self.initial_navigation(INITIAL_URL)
        if consent_data is None:  # Consent check failed
            return None
        
        if consent_data.need_consent:
            if not await self.process_consent(consent_data):
                return None
            
            data = await self.initial_navigation(consent_data.successful_consent_url)
            
            if data is None:  # Something went bad, we did get consent
                _LOGGER.error("Post consent navigation failed")
                return None
            
            if data.need_consent:
                _LOGGER.error("Yahoo reported needing consent even after we got it once")
                return None
        
        if self.cookies_missing():
            _LOGGER.warning(
                "Attempting to get crumb but have no cookies, the operation might fail"
            )
        
        await self.try_crumb_page()
        return self.crumb
    
    async def initial_navigation(self, url: str) -> ConsentData | None:
        """Navigate to base page. This determines if consent is needed."""
        
        _LOGGER.debug("Navigating to base page %s", url)
        
        try:
            async with self._websession.get(
                url,
                headers=INITIAL_REQUEST_HEADERS,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                _LOGGER.debug("Response %d, URL: %s", response.status, response.url)
                
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to navigate to %s, status=%d, reason=%s",
                        url,
                        response.status,
                        response.reason,
                    )
                    return None
                
                # This request will return cookies only if consent is not needed
                if response.cookies:
                    self.cookies = response.cookies
                
                # Check if consent is needed
                if hasattr(response.url, 'host') and response.url.host.lower() == CONSENT_HOST:
                    _LOGGER.info("Consent page %s detected", response.url)
                    
                    return ConsentData(
                        need_consent=True,
                        consent_content=await response.text(),
                        consent_post_url=response.url,
                    )
                
                _LOGGER.debug("No consent needed, have cookies=%s", bool(self.cookies))
                
        except (aiohttp.ClientError, asyncio.TimeoutError) as ex:
            _LOGGER.error("Timed out accessing initial url. %s", ex)
        except Exception as ex:  # noqa: BLE001
            _LOGGER.error("Unexpected error accessing initial url. %s", ex)
        
        return ConsentData()
    
    async def process_consent(self, consent_data: ConsentData) -> bool:
        """Process GDPR consent."""
        
        form_data = self.build_consent_form_data(consent_data.consent_content)
        _LOGGER.debug("Posting consent")
        
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._websession.post(
                    consent_data.consent_post_url,
                    data=form_data,
                    headers=INITIAL_REQUEST_HEADERS,
                )
                
                # Sample responses
                # 302 https://guce.yahoo.com/copyConsent?sessionId=3_cc-session_0d6c4281-76f7-44ce-8783-6db9d4f39c40&lang=nb-NO
                # 302 https://finance.yahoo.com/?guccounter=1
                # 200
                
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to post consent %d, reason=%s",
                        response.status,
                        response.reason,
                    )
                    return False
                
                if response.cookies:
                    self.cookies = response.cookies
                
                consent_data.successful_consent_url = response.url
                
                _LOGGER.debug(
                    "After consent processing, have cookies=%s", bool(self.cookies)
                )
                return True
        
        except TimeoutError as ex:
            _LOGGER.error("Timed out processing consent. %s", ex)
        except aiohttp.ClientError as ex:
            _LOGGER.error("Error accessing consent url. %s", ex)
        
        return False
    
    def cookies_missing(self) -> bool:
        """Check if we don't have any cookies."""
        return self.cookies is None or len(self.cookies) == 0
    
    async def try_crumb_page(self) -> str | None:
        """Try to get crumb from the end point."""
        
        _LOGGER.info("Accessing crumb page")
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        last_status = 0
        
        for user_agent in USER_AGENTS_FOR_XHR:
            headers = {**XHR_REQUEST_HEADERS, "user-agent": user_agent}
            
            async with self._websession.get(
                GET_CRUMB_URL, headers=headers, timeout=timeout, cookies=self.cookies
            ) as response:
                last_status = response.status
                
                if last_status == 200:
                    self.preferred_user_agent = user_agent
                    
                    self.crumb = await response.text()
                    if not self.crumb:
                        _LOGGER.error("No crumb reported")
                    
                    _LOGGER.info("Crumb page reported %s", self.crumb)
                    self._crumb_retry_count = 0
                    return self.crumb
                
                # Try next user-agent for 429, stop trying for any other failures
                if last_status == 429:
                    _LOGGER.info(
                        "Crumb request responded with status 429 for '%s', re-trying with different agent",
                        user_agent,
                    )
                else:
                    _LOGGER.error(
                        "Crumb request responded with status=%d, reason=%s",
                        last_status,
                        response.reason,
                    )
                    break
        
        self._crumb_retry_count += 1
        
        if last_status == 429:
            # Ideally we would want to use the seconds passed back in the header
            # for 429 but there seems to be no such value.
            self.retry_duration = CRUMB_RETRY_DELAY_429
        else:
            self.retry_duration = CRUMB_RETRY_DELAY
        
        _LOGGER.info(
            "Crumb failure, will retry after %d seconds",
            self.retry_duration,
        )
        
        return None
    
    def build_consent_form_data(self, content: str) -> dict[str, str]:
        """Build consent form data from response content."""
        import re
        pattern = r'<input.*?type="hidden".*?name="(.*?)".*?value="(.*?)".*?>'
        matches = re.findall(pattern, content)
        basic_data = {"reject": "reject"}  # From "Reject" submit button
        additional_data = dict(matches)
        return {**basic_data, **additional_data}

async def async_setup(hass: HomeAssistant, config: dict):
    """设置集成组件"""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """设置配置条目"""
    # 创建数据更新协调器
    coordinator = YahooFinanceDataCoordinator(hass, _LOGGER, entry)
    
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

class YahooFinanceDataCoordinator(DataUpdateCoordinator):
    """雅虎金融数据更新协调器"""
    def __init__(self, hass, logger, entry):
        self.hass = hass
        self.entry = entry
        self.stock_code = entry.data.get("stock_code")
        self.stock_name = entry.data.get("stock_name")
        self.preferred_user_agent = None
        
        # 创建会话，增加max_field_size和max_line_size以避免Header过长错误
        self.websession = async_create_clientsession(
            hass, 
            max_field_size=MAX_LINE_SIZE, 
            max_line_size=MAX_LINE_SIZE
        )
        
        # 获取CrumbCoordinator实例
        self._cc = CrumbCoordinator.get_static_instance(hass, self.websession)
        
        # 使用股票代码作为名称
        coordinator_name = f"{DOMAIN}_{self.stock_code}"
        
        super().__init__(
            hass,
            logger,
            name=coordinator_name,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        
    async def _fetch_json(self, url, user_agent):
        """使用指定的User-Agent获取JSON数据"""
        headers = {**XHR_REQUEST_HEADERS, "user-agent": user_agent}
        _LOGGER.debug(f"使用User-Agent: {user_agent} 请求数据: {url}")
        
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self.websession.get(
                    url, 
                    headers=headers, 
                    cookies=self._cc.cookies
                )
                
                if response.status == 200:
                    result_json = await response.json()
                    _LOGGER.debug(f"成功获取数据")
                    return [result_json, response.status]
                
                _LOGGER.warning(f"请求失败，状态码: {response.status}")
                return [None, response.status]
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.warning(f"网络请求错误: {str(e)}")
            return [None, None]
    
    async def _async_update_data(self):
        """异步更新数据 - 使用雅虎金融API"""
        _LOGGER.debug(f"获取股票数据: {self.stock_name}({self.stock_code})")
        
        # 首先获取crumb和cookie
        crumb = await self._cc.try_get_crumb_cookies()
        if not crumb:
            _LOGGER.warning("无法获取crumb，将在稍后重试")
            raise UpdateFailed("无法获取认证信息")
        
        # 构建API请求URL，包含crumb
        yahoo_symbol = self.stock_code.strip()
        url = f"{BASE_URL}{yahoo_symbol}&crumb={crumb}"
        
        # 尝试使用多个User-Agent
        user_agents = USER_AGENTS_FOR_XHR.copy()
        preferred_user_agent = self._cc.preferred_user_agent
        
        if preferred_user_agent:
            # 如果有首选User-Agent，先使用它
            _LOGGER.info(f"使用首选User-Agent: {preferred_user_agent}")
            [result_json, status] = await self._fetch_json(url, preferred_user_agent)
            
            if status == 200:
                # 解析数据
                if result_json and "quoteResponse" in result_json:
                    quote_response = result_json["quoteResponse"]
                    if "result" in quote_response and quote_response["result"]:
                        stock_data = quote_response["result"][0]
                        
                        # 构建返回数据
                        return {
                            "current_price": stock_data.get("regularMarketPrice"),
                            "change_amount": stock_data.get("regularMarketChange"),
                            "change_percent": stock_data.get("regularMarketChangePercent"),
                            "prev_close": stock_data.get("regularMarketPreviousClose"),
                            "volume": stock_data.get("regularMarketVolume"),
                            "market_cap": stock_data.get("marketCap"),
                            "currency": stock_data.get("currency"),
                            "name": stock_data.get("shortName", self.stock_name),
                            "code": yahoo_symbol,
                            "timestamp": time.time(),
                            "quote_type": stock_data.get("quoteType"),
                            "market_state": stock_data.get("marketState")
                        }
            
            if status == 429:
                _LOGGER.info(f"首选User-Agent遇到429错误，尝试其他User-Agent")
            elif status in [401, 403]:
                # 如果遇到认证错误，重置crumb并尝试其他User-Agent
                _LOGGER.warning(f"认证错误，重置crumb")
                self._cc.reset()
        
        # 尝试其他User-Agent
        for user_agent in user_agents:
            # 跳过已尝试的首选User-Agent
            if preferred_user_agent == user_agent:
                continue
            
            [result_json, status] = await self._fetch_json(url, user_agent)
            
            if status == 200:
                # 解析数据
                if result_json and "quoteResponse" in result_json:
                    quote_response = result_json["quoteResponse"]
                    if "result" in quote_response and quote_response["result"]:
                        stock_data = quote_response["result"][0]
                        
                        # 构建返回数据
                        return {
                            "current_price": stock_data.get("regularMarketPrice"),
                            "change_amount": stock_data.get("regularMarketChange"),
                            "change_percent": stock_data.get("regularMarketChangePercent"),
                            "prev_close": stock_data.get("regularMarketPreviousClose"),
                            "volume": stock_data.get("regularMarketVolume"),
                            "market_cap": stock_data.get("marketCap"),
                            "currency": stock_data.get("currency"),
                            "name": stock_data.get("shortName", self.stock_name),
                            "code": yahoo_symbol,
                            "timestamp": time.time(),
                            "quote_type": stock_data.get("quoteType"),
                            "market_state": stock_data.get("marketState")
                        }
            
            # 只在429错误时尝试下一个User-Agent
            if status != 429:
                break
            
            _LOGGER.warning(f"使用User-Agent {user_agent} 遇到429错误，尝试下一个User-Agent")
        
        raise UpdateFailed("无法获取数据，所有User-Agent都失败")