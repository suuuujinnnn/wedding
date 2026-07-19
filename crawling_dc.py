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

DC_LIST_URL = "https://gall.dcinside.com/board/lists/"
DC_GALLERY_ID = "wedding"

DISCOVERY_KEYWORDS = [
    "가격", "비용", "견적", "추가금", "추가 비용", "추가비용",
    "환불", "취소", "계약", "상담", "플래너", "후기", "리뷰",
    "불만", "사기", "실패", "실망", "비싸", "예산"
]

CONTEXT_KEYWORDS = [
    "웨딩", "결혼", "결혼식", "예식", "예식장", "스드메", "업체",
    "신혼", "혼수", "촬영", "드레스", "메이크업", "플래너"
]

EXCLUDE_TERMS = [
    "청소업체직원", "연애상담", "노괴", "도축제도",
    "이혼", "부동산계약", "전세계약", "혼인취소"
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
        return False


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
    text = normalize_text(title)
    if not text:
        return False
    if any(term in text for term in EXCLUDE_TERMS):
        return False

    has_context = any(term in text for term in CONTEXT_KEYWORDS)
    has_target = any(term in text for term in DISCOVERY_KEYWORDS)
    return has_context and has_target


def relevant_article(title: str, body: str) -> bool:
    text = normalize_text(f"{title} {body}")
    if not text:
        return False
    if any(term in text for term in EXCLUDE_TERMS):
        return False

    has_context = any(term in text for term in CONTEXT_KEYWORDS)
    has_target = any(term in text for term in DISCOVERY_KEYWORDS)
    return has_context and has_target


def classify_topic(title: str, body: str) -> str:
    text = normalize_text(f"{title} {body}")
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return topic
    return "general"


def get_dc_article_links(max_pages: int = 30) -> list[str]:
    results = {}

    for page in range(1, max_pages + 1):
        url = f"{DC_LIST_URL}?id={DC_GALLERY_ID}&page={page}"
        soup = fetch_soup(url)

        if soup is None:
            break

        for anchor in soup.select('a[href*="/board/view/"][href*="id=wedding"]'):
            title = clean_text(anchor)
            href = urljoin(url, anchor.get("href", ""))
            post_no = parse_qs(urlparse(href).query).get("no", [""])[0]

            if not post_no:
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

    title_node = soup.select_one("span.title_subject, .view_content_wrap .title_subject")
    body_node = soup.select_one(".writing_view_box .write_div, .writing_view_box")

    title = clean_text(title_node)
    body = clean_text(body_node)

    if not title or len(body) < 20:
        return None

    if not relevant_article(title, body):
        return None

    post_no = parse_qs(urlparse(url).query).get("no", [""])[0]

    return {
        "source": "dcinside",
        "source_type": "community",
        "external_id": post_no,
        "url": url,
        "title": title,
        "body": body,
        "topic": classify_topic(title, body),
        "content_hash": content_hash(title + body),
        "incentivized_review": False,
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
    rows = collect_dc_articles()
    save_jsonl("dc_wedding_posts.jsonl", rows)
    print(f"Saved {len(rows)} DC Inside articles")