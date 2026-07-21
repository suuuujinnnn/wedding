import hashlib
import json
import random
import time
from urllib import robotparser
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from quality_rules import analyze_post


USER_AGENT = (
    "WeddingMarketResearchBot/0.1 "
    "(research purpose; contact: asd123@gmail.com)"
)

session = requests.Session()
session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept-Language": "ko-KR,ko;q=0.9",
})

retry = Retry(
    total=2,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)

session.mount("https://", HTTPAdapter(max_retries=retry))

DC_LIST_URL = "https://gall.dcinside.com/board/lists/"
DC_GALLERY_ID = "wedding"


def robots_allowed(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    rp = robotparser.RobotFileParser()
    rp.set_url(robots_url)

    try:
        rp.read()
        return rp.can_fetch(USER_AGENT, url)
    except Exception as exc:
        print(f"[ROBOTS CHECK FAILED, CONTINUING] {robots_url} ({exc.__class__.__name__})")
        return True


def fetch_soup(url: str) -> BeautifulSoup | None:
    if not robots_allowed(url):
        print(f"[ROBOTS BLOCKED OR UNAVAILABLE] {url}")
        return None

    time.sleep(random.uniform(3, 6))

    response = session.get(url, timeout=20)

    if response.status_code in {403, 429}:
        print(f"[ACCESS BLOCKED] {response.status_code}: {url}")
        return None

    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def clean_text(node) -> str:
    if node is None:
        return ""

    for removable in node.select(
        "script, style, iframe, form, nav, footer, .advertisement"
    ):
        removable.decompose()

    return " ".join(node.get_text(" ", strip=True).split())


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def relevant_title(title: str) -> bool:
    return bool(title.strip())


def get_dc_article_links(max_pages: int = 30) -> list[str]:
    results = {}

    for page in range(1, max_pages + 1):
        url = f"{DC_LIST_URL}?id={DC_GALLERY_ID}&page={page}"
        soup = fetch_soup(url)

        if soup is None:
            break

        for anchor in soup.select('a[href*="/board/view/"]'):
            title = clean_text(anchor)
            href = urljoin(url, anchor.get("href", ""))
            parsed_href = urlparse(href)
            query = parse_qs(parsed_href.query)
            post_no = query.get("no", [""])[0]
            gallery_id = query.get("id", [DC_GALLERY_ID])[0]

            if not post_no or gallery_id != DC_GALLERY_ID:
                continue

            if relevant_title(title):
                canonical_url = (
                    "https://gall.dcinside.com/board/view/"
                    f"?id={DC_GALLERY_ID}&no={post_no}"
                )
                results[post_no] = canonical_url

    return list(results.values())


def parse_dc_article(url: str) -> dict | None:
    soup = fetch_soup(url)

    if soup is None:
        return None

    title_node = soup.select_one(
        "span.title_subject, h3.title_subject, .view_content_wrap .title_subject, "
        ".view_title, .title_area, .title_subject"
    )
    body_node = soup.select_one(
        ".writing_view_box .write_div, .writing_view_box, .view_content_wrap .view_content, "
        ".view_content_wrap, .write_div, .view_content, .con_box, .article_viewbox"
    )

    title = clean_text(title_node)
    body = clean_text(body_node)

    if not title:
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title is not None:
            title = (og_title.get("content") or "").strip()

    if not body:
        og_description = soup.select_one('meta[property="og:description"]')
        if og_description is not None:
            body = (og_description.get("content") or "").strip()

    if not body:
        body = clean_text(soup)

    if not title or len(body) < 8:
        return None

    html_excerpt = ""
    if body_node is not None:
        html_excerpt = str(body_node)[:12000]

    analysis = analyze_post(
        title=title,
        body=body,
        source="dcinside",
    )

    post_no = parse_qs(
        urlparse(url).query
    ).get("no", [""])[0]

    return {
        "source": "dcinside",
        "source_type": "community",
        "external_id": post_no,
        "url": url,
        "html_excerpt": html_excerpt,
        "content_hash": content_hash(
            analysis["title"]
            + analysis["body_clean"]
        ),
        "incentivized_review": False,
        **analysis,
    }


def collect_dc_articles(max_pages: int = 20, max_articles: int = 100) -> list[dict]:
    article_urls = get_dc_article_links(max_pages=max_pages)
    articles = []

    for url in article_urls[:max_articles]:
        article = parse_dc_article(url)
        if article is not None:
            articles.append(article)

    return articles


def save_jsonl(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    rows = collect_dc_articles(
        max_pages=300,
        max_articles=1500,
    )
    save_jsonl("dc_wedding_posts.jsonl", rows)
    print(f"Saved {len(rows)} DC Inside articles")
