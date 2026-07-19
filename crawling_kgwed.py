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

DISCOVERY_KEYWORDS = [
    "후기", "리뷰", "이용후기", "실제후기", "고객후기",
    "가격", "비용", "견적", "추가금", "계약",
    "환불", "취소", "상담", "업체", "서비스",
]

TOPIC_KEYWORDS = {
    "price_transparency": ["가격", "비용", "견적", "추가금", "투명"],
    "conflict": ["갈등", "분쟁", "불만", "스트레스", "싸움"],
    "planner_contract": ["플래너", "계약", "상담", "예약", "일정"],
    "service_review": ["서비스", "업체", "후기", "평가", "추천"],
    "refund": ["환불", "취소", "보상", "환불요청"],
}


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

    response = session.get(url, timeout=20, verify=False)

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


def normalize_text(text: str) -> str:
    return " ".join(text.replace("\n", " ").split()).lower()


def relevant_title(title: str) -> bool:
    normalized = title.replace(" ", "")
    if not normalized:
        return False
    if any(keyword.replace(" ", "") in normalized for keyword in DISCOVERY_KEYWORDS):
        return True
    lowered = normalized.lower()
    return any(token in lowered for token in ["후기", "review", "리뷰"])


def classify_topic(title: str, body: str) -> str:
    text = normalize_text(f"{title} {body}")
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return topic
    return "general"


def get_kgwed_article_links(max_pages: int = 5) -> list[str]:
    links = set()

    for review_url in [KGWED_REVIEW_URL, f"{KGWED_BASE_URL}/%ed%9b%84%ea%b8%b0/"]:
        soup = fetch_soup(review_url)
        if soup is None:
            continue

        for anchor in soup.select('a[href]'):
            href = anchor.get("href", "")
            title = clean_text(anchor)
            if not href:
                continue
            if "후기" in title or "리뷰" in title or "review" in href.lower():
                resolved = urljoin(review_url, href)
                if resolved.startswith(KGWED_BASE_URL) and resolved != review_url:
                    links.add(resolved)

        if links:
            break

    return sorted(links)


def parse_kgwed_article(url: str) -> dict | None:
    soup = fetch_soup(url)

    if soup is None:
        return None

    title_node = soup.select_one(
        "h1, .entry-title, .post-title, .title, .wp-block-post-title"
    )
    body_node = soup.select_one(
        "article, .entry-content, .post-content, .content, .post"
    )

    title = clean_text(title_node)
    body = clean_text(body_node)

    if not title or len(body) < 30:
        return None

    if title.startswith("Re:"):
        return None

    uid = parse_qs(urlparse(url).query).get("uid", [""])[0]

    return {
        "source": "kgwed",
        "source_type": "vendor",
        "external_id": uid or url,
        "url": url,
        "title": title,
        "body": body,
        "topic": classify_topic(title, body),
        "content_hash": content_hash(title + body),
        "incentivized_review": True,
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
