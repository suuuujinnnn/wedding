import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "reports"
OUTPUT_DIR.mkdir(exist_ok=True)

STOPWORDS = {
    "그리고", "하지만", "그래서", "이렇게", "저희", "저는", "우리", "이제", "정말",
    "너무", "같은", "같아요", "같고", "이런", "그런", "그렇", "해서", "하면",
    "있고", "있어요", "있습니다", "하니", "하니까", "또한", "혹시", "이번", "앞서",
    "때문", "정도", "제가", "저도", "이상", "아래", "이후", "동안", "진짜", "보고",
    "보니", "보면", "한번", "하게", "되어", "가장", "더욱", "이때", "그때", "지금"
}

TOPIC_KEYWORDS = {
    "price_transparency": ["가격", "비용", "견적", "추가금", "투명", "가성비"],
    "refund": ["환불", "취소", "보상", "환불요청"],
    "planner_contract": ["플래너", "계약", "상담", "예약", "일정"],
}


def load_rows():
    rows = []
    for path in [ROOT / "dc_wedding_posts.jsonl", ROOT / "kgwed_posts.jsonl"]:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def tokenize(text: str):
    tokens = re.findall(r"[가-힣]+", normalize_text(text))
    return [token for token in tokens if len(token) > 1 and token not in STOPWORDS]


def extract_focus_rows(rows, focus_terms):
    selected = []
    for row in rows:
        text = f"{row.get('title','')} {row.get('body','')}"
        if any(term in text for term in focus_terms):
            selected.append(row)
    return selected


def write_top_keywords(rows, path: Path):
    counter = Counter()
    for row in rows:
        counter.update(tokenize(f"{row.get('title','')} {row.get('body','')}"))

    top10 = counter.most_common(10)
    lines = ["가장 자주 나온 키워드 TOP 10", ""]
    for idx, (word, count) in enumerate(top10, 1):
        lines.append(f"{idx}. {word} ({count})")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_focus_report(rows, path: Path):
    lines = ["가격/추가금/환불 관련 주제 추출", ""]
    for row in rows[:30]:
        title = (row.get("title") or "").strip()
        body = (row.get("body") or "")
        preview = normalize_text(body)[:180]
        lines.append(f"- {title}")
        lines.append(f"  {preview}...")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_instagram_recommendations(rows, path: Path):
    suggestions = []
    focus_rows = extract_focus_rows(rows, ["가격", "추가금", "환불", "비용", "견적", "취소"])
    if focus_rows:
        suggestions.append("1. 가격 투명성에 대한 불편을 다룬 게시물")
        suggestions.append("   - 핵심 포인트: '같은 서비스인데 왜 가격 차이가 나는가?'")
        suggestions.append("   - 추천 문구: '웨딩 준비 중 가장 혼란스러운 건 가격과 추가금입니다.'")
        suggestions.append("")
        suggestions.append("2. 환불·취소 불안에 대한 게시물")
        suggestions.append("   - 핵심 포인트: 계약 후 변경이나 취소 시 비용이 얼마나 불안한지")
        suggestions.append("   - 추천 문구: '결혼 준비는 예산이 크기 때문에 환불 규정이 더 중요합니다.'")
        suggestions.append("")
        suggestions.append("3. 플래너/상담 과정의 불편을 다룬 게시물")
        suggestions.append("   - 핵심 포인트: 상담 과정에서 정보가 충분하지 않거나 압박을 느끼는 경험")
        suggestions.append("   - 추천 문구: '웨딩플래너 상담이 오히려 더 복잡해지는 이유는 무엇일까요?'")
    else:
        suggestions.append("수집된 데이터가 충분하지 않아, 가격/환불/상담 관련 예시 제안만 작성합니다.")

    path.write_text("\n".join(suggestions) + "\n", encoding="utf-8")


if __name__ == "__main__":
    rows = load_rows()
    write_top_keywords(rows, OUTPUT_DIR / "top_keywords.txt")
    focus_rows = extract_focus_rows(rows, ["가격", "추가금", "환불", "비용", "견적", "취소"])
    write_focus_report(focus_rows, OUTPUT_DIR / "focus_topics.txt")
    write_instagram_recommendations(rows, OUTPUT_DIR / "instagram_recommendations.txt")
    print("Generated top_keywords.txt, focus_topics.txt, instagram_recommendations.txt")
