import pytest
from src.fetchers.content_scraper import ContentScraper

@pytest.mark.asyncio
async def test_extract_main_text():
    scraper = ContentScraper()
    
    # Case 1: Article tag
    html1 = """
    <html>
        <body>
            <nav>Menu</nav>
            <article>
                <h1>Title</h1>
                <p>This is the main content of the article. It should be extracted.</p>
                <p>More content here to make it long enough.</p>
                <p>Even more content to pass the length check.</p>
                <p>Even more content to pass the length check.</p>
                <p>Even more content to pass the length check.</p>
            </article>
            <footer>Copyright</footer>
        </body>
    </html>
    """
    text1 = scraper._extract_main_text(html1)
    assert "This is the main content" in text1
    assert "Menu" not in text1
    assert "Copyright" not in text1

    # Case 2: Main tag
    html2 = """
    <html>
        <body>
            <main>
                <p>Main content here. This is a fallback to main tag.</p>
                <p>Adding some length to ensure it passes the filter.</p>
                <p>Adding some length to ensure it passes the filter.</p>
                <p>Adding some length to ensure it passes the filter.</p>
            </main>
        </body>
    </html>
    """
    text2 = scraper._extract_main_text(html2)
    assert "Main content here" in text2

    # Case 3: Content ID
    html3 = """
    <html>
        <body>
            <div id="content">
                <p>Content inside div id=content.</p>
                <p>Adding some length to ensure it passes the filter.</p>
                <p>Adding some length to ensure it passes the filter.</p>
                <p>Adding some length to ensure it passes the filter.</p>
            </div>
        </body>
    </html>
    """
    text3 = scraper._extract_main_text(html3)
    assert "Content inside div" in text3
