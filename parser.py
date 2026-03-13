from bs4 import BeautifulSoup


def parse_html(html: str) -> dict:
    """Parse HTML and return {title, text} with script/style removed and entities decoded."""
    soup = BeautifulSoup(html, 'html.parser')

    # Remove script and style elements entirely (including their content)
    for tag in soup.find_all(['script', 'style']):
        tag.decompose()

    # Extract title
    title_tag = soup.find('title')
    title = title_tag.get_text(strip=True) if title_tag else ''

    # Extract plain text (BS4 auto-decodes HTML entities like &amp; &lt; &#39; etc.)
    text = soup.get_text(separator=' ')

    return {'title': title, 'text': text}
