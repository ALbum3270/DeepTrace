import logging
from typing import Optional
try:
    from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext
except ImportError:
    Playwright = None
    Browser = None
    BrowserContext = None

logger = logging.getLogger(__name__)

class PlaywrightSessionManager:
    _instance = None
    _playwright: Optional["Playwright"] = None
    _browser: Optional["Browser"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PlaywrightSessionManager, cls).__new__(cls)
        return cls._instance

    async def start(self, headless: bool = True):
        if not self._playwright:
            self._playwright = await async_playwright().start()
        
        if not self._browser:
            try:
                self._browser = await self._playwright.chromium.launch(headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage"])
                logger.info("Playwright browser launched")
            except Exception as e:
                logger.error(f"Failed to launch browser: {e}")
                raise

    async def get_context(self, **kwargs) -> BrowserContext:
        if not self._browser:
            await self.start()
        return await self._browser.new_context(**kwargs)

    async def stop(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Playwright session stopped")

# Global instance
browser_manager = PlaywrightSessionManager()
