import hashlib
import json
import random
import re
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

KGWED_BASE_URL = "https://kgwed.com"
KGWED_REVIEW_URL = f"{KGWED_BASE_URL}/%ED%9B%84%EA%B8%B0/"
KGWED_LIST_URL = f"{KGWED_BASE_URL}/index.php"


def robots_allowed(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    rp = robotparser.RobotFileParser()
    rp.set_url(robots_url)

    try:
        rp.read()
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        print(f"[ROBOTS CHECK FAILED, CONTINUING] {robots_url}")
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


def get_kgwed_article_links(max_pages: int = 5) -> list[str]:
    links = {}

    for page in range(1, max_pages + 1):
        url = (
            f"{KGWED_REVIEW_URL}"
            f"?mod=list&pageid={page}"
        )

        soup = fetch_soup(url)

        if soup is None:
            break

        for anchor in soup.select(
            'a[href*="mod=document"][href*="uid="]'
        ):
            href = urljoin(
                KGWED_REVIEW_URL,
                anchor.get("href", ""),
            )

            uid = parse_qs(
                urlparse(href).query
            ).get("uid", [""])[0]

            if not uid:
                continue

            links[uid] = (
                f"{KGWED_REVIEW_URL}"
                f"?mod=document&uid={uid}"
            )

    return list(links.values())


def parse_kgwed_article(url: str) -> dict | None:
    soup = fetch_soup(url)

    if soup is None:
        return None

    document = soup.select_one(
        ".kboard-document-wrap"
    )

    if document is None:
        print(f"[KBOARD DOCUMENT NOT FOUND] {url}")
        return None

    title_node = document.select_one(
        ".kboard-title h1, "
        ".kboard-title"
    )

    body_node = document.select_one(
        ".kboard-content .content-view, "
        ".content-view"
    )

    if title_node is None or body_node is None:
        print(f"[CONTENT SELECTOR FAILED] {url}")
        return None

    title = clean_text(title_node)
    body = clean_text(body_node)

    if not title or len(body) < 30:
        return None

    if title.strip().startswith("Re:"):
        return None

    if re.match(r"^Re:", body.strip()):
        return None

    if "상품권 증정 이벤트" in title:
        return None

    if "상품권 증정 이벤트" in body[:200]:
        return None

    uid = parse_qs(
        urlparse(url).query
    ).get("uid", [""])[0]

    analysis = analyze_post(
        title=title,
        body=body,
        source="kgwed",
    )

    return {
        "source": "kgwed",
        "source_type": "vendor_review_board",
        "external_id": uid,
        "url": url,
        "content_hash": content_hash(
            analysis["title"]
            + analysis["body_clean"]
        ),
        "incentivized_review": None,
        "incentive_program_present": True,
        "source_bias": "vendor_operated_review_board",
        **analysis,
    }


def collect_kgwed_articles(max_pages: int = 5, max_articles: int = 50) -> list[dict]:
    article_urls = get_kgwed_article_links(max_pages=max_pages)
    articles = []

    for url in article_urls[:max_articles]:
        article = parse_kgwed_article(url)
        if article is not None:
            articles.append(article)

    return articles


def save_jsonl(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    rows = collect_kgwed_articles()
    save_jsonl("kgwed_posts.jsonl", rows)
    print(f"Saved {len(rows)} KGWED articles")
