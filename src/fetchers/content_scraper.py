"""
Content Scraper: 用于抓取网页正文内容。
"""
import asyncio
import httpx
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any
import logging

# 配置日志
logger = logging.getLogger(__name__)

class ContentScraper:
    """网页内容抓取器"""
    
    def __init__(self, max_concurrent: int = 3, timeout: int = 10):
        self.max_concurrent = max_concurrent
        self.semaphore = None
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    async def scrape(self, url: str) -> Dict[str, Optional[str]]:
        """
        抓取指定 URL 的内容。
        
        Returns:
            Dict containing:
            - main_text: 提取的正文
            - raw_comments_html: (预留) 评论区 HTML
            - error: 错误信息（如果有）
        """
        # Always create semaphore in the current event loop to avoid "attached to a different loop" errors
        try:
            loop = asyncio.get_running_loop()
            if self.semaphore is None or getattr(self.semaphore, '_loop', None) != loop:
                self.semaphore = asyncio.Semaphore(self.max_concurrent)
        except RuntimeError:
            # No running loop, create semaphore lazily
            if self.semaphore is None:
                self.semaphore = asyncio.Semaphore(self.max_concurrent)
            
        async with self.semaphore:
            try:
                async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
                    response = await client.get(url, headers=self.headers, timeout=self.timeout)
                    response.raise_for_status()
                    
                    html = response.text
                    main_text = self._extract_main_text(html)
                    
                    return {
                        "main_text": main_text,
                        "raw_comments_html": None,  # 预留
                        "error": None
                    }
            except Exception as e:
                error_msg = str(e)
                # 对于常见的 HTTP 错误，使用简短的警告
                if "403" in error_msg or "404" in error_msg:
                    logger.warning(f"[ContentScraper] Skipped {url} (Access Denied/Not Found)")
                else:
                    logger.warning(f"[ContentScraper] Failed to scrape {url}: {error_msg[:100]}")
                
                return {
                    "main_text": None,
                    "raw_comments_html": None,
                    "error": str(e)
                }

    def _extract_main_text(self, html: str) -> str:
        """
        使用启发式规则提取正文。
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # 移除无关元素
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                tag.decompose()
            
            # 策略 1: 优先查找 <article>
            article = soup.find("article")
            if article:
                text = self._get_text_from_element(article)
                if len(text) > 100:  # 只有当内容足够长时才采纳
                    return text
            
            # 策略 2: 查找 <main>
            main = soup.find("main")
            if main:
                text = self._get_text_from_element(main)
                if len(text) > 100:
                    return text
            
            # 策略 3: 查找常见的正文容器 ID/Class
            content_selectors = [
                "#content", ".content", ".article", ".post-content", 
                ".entry-content", ".main-content", "#main"
            ]
            for selector in content_selectors:
                element = soup.select_one(selector)
                if element:
                    text = self._get_text_from_element(element)
                    if len(text) > 100:
                        return text
            
            # 策略 4: 保底 - 提取 body 中所有 <p>
            body = soup.find("body")
            if body:
                return self._get_text_from_element(body)
                
            return ""
            
        except Exception as e:
            logger.error(f"Text extraction error: {e}")
            return ""

    def _get_text_from_element(self, element) -> str:
        """从元素中提取并清洗文本"""
        paragraphs = []
        for p in element.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'li']):
            text = p.get_text(strip=True)
            # 过滤过短的段落（可能是导航或版权信息），除非是标题
            if len(text) > 10 or p.name.startswith('h'):
                paragraphs.append(text)
        
        # 如果没有找到 p 标签，直接取整个文本
        if not paragraphs:
            return element.get_text(strip=True)
            
        return "\n\n".join(paragraphs)
