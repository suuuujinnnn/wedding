import csv
import json
import re
from collections import Counter
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT_FILES = [ROOT / "dc_wedding_posts.jsonl", ROOT / "kgwed_posts.jsonl"]
OUTPUT_DIR = ROOT / "reports"
OUTPUT_DIR.mkdir(exist_ok=True)

STOPWORDS = {
    "그리고", "하지만", "그래서", "이렇게", "저희", "저는", "우리", "이제", "정말",
    "너무", "같은", "같아요", "같고", "이런", "그런", "그렇", "해서", "하면",
    "있고", "있어요", "있습니다", "해서", "하니", "하니까", "또한", "혹시",
    "이번", "앞서", "때문", "정도", "제가", "저도", "이상", "아래", "이후",
    "동안", "진짜", "정말", "보고", "보니", "보면", "한번", "하게", "되어",
    "가장", "더욱", "이상", "이후", "이전", "이때", "그때", "지금", "앞으로"
}


def load_rows():
    rows = []
    for path in INPUT_FILES:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rows.append(row)
    return rows


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_for_dedup(text: str) -> str:
    text = normalize_text(text).lower()
    text = re.sub(r"[^가-힣a-z0-9]+", " ", text)
    return " ".join(text.split())


def deduplicate(rows):
    unique_rows = []
    seen_signatures = []

    for row in rows:
        title = normalize_for_dedup(row.get("title", ""))
        body = normalize_for_dedup(row.get("body", ""))
        content_hash = row.get("content_hash", "")

        signature = (row.get("source", ""), row.get("external_id", ""))
        if content_hash:
            signature = ("hash", content_hash)

        if signature in seen_signatures:
            continue

        if title:
            for existing in unique_rows:
                existing_title = normalize_for_dedup(existing.get("title", ""))
                existing_body = normalize_for_dedup(existing.get("body", ""))
                if existing.get("source") != row.get("source"):
                    continue
                if existing_title and title and existing_title == title:
                    if existing_body and body and existing_body[:200] == body[:200]:
                        seen_signatures.append(signature)
                        break
                else:
                    continue
            else:
                unique_rows.append(row)
                seen_signatures.append(signature)
                continue

        unique_rows.append(row)
        seen_signatures.append(signature)

    return unique_rows


def preview_text(text: str, length: int = 140) -> str:
    text = normalize_text(text)
    if len(text) <= length:
        return text
    return text[:length] + "..."


def tokenize(text: str):
    tokens = re.findall(r"[가-힣]+", normalize_text(text))
    return [token for token in tokens if len(token) > 1 and token not in STOPWORDS]


def write_csv(rows, path: Path):
    fieldnames = ["source", "topic", "title", "url", "external_id", "incentivized_review", "preview"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "source": row.get("source", ""),
                "topic": row.get("topic", ""),
                "title": row.get("title", ""),
                "url": row.get("url", ""),
                "external_id": row.get("external_id", ""),
                "incentivized_review": row.get("incentivized_review", False),
                "preview": preview_text(row.get("body", "")),
            })


def write_html(rows, path: Path):
    source_counts = Counter(row.get("source", "unknown") for row in rows)
    topic_counts = Counter(row.get("topic", "general") for row in rows)

    summary_cards = []
    for name, count in source_counts.items():
        summary_cards.append(f"<div class='card'><h3>{escape(name)}</h3><p>{count}</p></div>")
    for name, count in topic_counts.items():
        summary_cards.append(f"<div class='card'><h3>{escape(name)}</h3><p>{count}</p></div>")

    rows_html = []
    for row in rows:
        title = escape(row.get("title", ""))
        preview = escape(preview_text(row.get("body", "")))
        url = row.get("url", "")
        source = escape(row.get("source", ""))
        topic = escape(row.get("topic", ""))
        rows_html.append(
            f"<tr><td>{source}</td><td>{topic}</td><td><a href='{escape(url)}' target='_blank'>{title}</a></td><td>{preview}</td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang='ko'>
<head>
  <meta charset='utf-8' />
  <title>웨딩 크롤링 결과 요약</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #222; }}
    h1 {{ margin-bottom: 8px; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 20px 0; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px 16px; min-width: 120px; }}
    .links {{ margin-bottom: 16px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f7f7f7; }}
    a {{ color: #1a73e8; text-decoration: none; }}
  </style>
</head>
<body>
  <h1>웨딩 크롤링 결과 요약</h1>
  <p>총 {len(rows)}건의 항목을 정리했습니다.</p>
  <div class='links'>
    <a href='topic_clusters.html'>주제별 클러스터링 보기</a> |
    <a href='keyword_frequency.html'>키워드 빈도 보기</a>
  </div>
  <div class='summary'>
    {''.join(summary_cards)}
  </div>
  <table>
    <thead>
      <tr><th>출처</th><th>주제</th><th>제목</th><th>미리보기</th></tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def write_topic_clusters(rows, path: Path):
    grouped = {}
    for row in rows:
        topic = row.get("topic", "general")
        grouped.setdefault(topic, []).append(row)

    sections = []
    for topic, group in sorted(grouped.items()):
        token_counter = Counter()
        for row in group:
            token_counter.update(tokenize(f"{row.get('title', '')} {row.get('body', '')}"))
        top_keywords = token_counter.most_common(8)
        examples = [escape(row.get("title", "")) for row in group[:5]]
        sections.append(
            "<section class='cluster'>"
            f"<h2>{escape(topic)}</h2>"
            f"<p>건수: {len(group)} | 대표키워드: {', '.join(f'{k}({c})' for k, c in top_keywords)}</p>"
            f"<ul><li>{'</li><li>'.join(examples)}</li></ul>"
            "</section>"
        )

    html = f"""<!DOCTYPE html>
<html lang='ko'>
<head>
  <meta charset='utf-8' />
  <title>주제별 클러스터링</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #222; }}
    .cluster {{ border: 1px solid #ddd; border-radius: 8px; padding: 14px; margin-bottom: 14px; }}
    ul {{ padding-left: 18px; }}
    a {{ color: #1a73e8; text-decoration: none; }}
  </style>
</head>
<body>
  <h1>주제별 클러스터링</h1>
  <p><a href='wedding_crawling_summary.html'>요약 보기</a></p>
  {''.join(sections)}
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def write_keyword_frequency(rows, path: Path):
    counter = Counter()
    for row in rows:
        counter.update(tokenize(f"{row.get('title', '')} {row.get('body', '')}"))

    max_count = max(counter.values()) if counter else 1
    items = []
    for keyword, count in counter.most_common(40):
        width = int(count / max_count * 100)
        items.append(
            f"<div class='row'><div class='label'>{escape(keyword)} ({count})</div><div class='bar'><div class='fill' style='width:{width}%'></div></div></div>"
        )

    html = f"""<!DOCTYPE html>
<html lang='ko'>
<head>
  <meta charset='utf-8' />
  <title>키워드 빈도</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #222; }}
    .row {{ margin-bottom: 10px; }}
    .label {{ margin-bottom: 4px; font-weight: 600; }}
    .bar {{ height: 12px; background: #eee; border-radius: 6px; overflow: hidden; }}
    .fill {{ height: 100%; background: #1a73e8; }}
    a {{ color: #1a73e8; text-decoration: none; }}
  </style>
</head>
<body>
  <h1>키워드 빈도</h1>
  <p><a href='wedding_crawling_summary.html'>요약 보기</a></p>
  {''.join(items)}
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def main():
    rows = load_rows()
    rows = deduplicate(rows)
    rows = sorted(rows, key=lambda r: (r.get("source", ""), r.get("title", "")))

    write_csv(rows, OUTPUT_DIR / "wedding_crawling_summary.csv")
    write_html(rows, OUTPUT_DIR / "wedding_crawling_summary.html")
    write_topic_clusters(rows, OUTPUT_DIR / "topic_clusters.html")
    write_keyword_frequency(rows, OUTPUT_DIR / "keyword_frequency.html")

    print(f"Saved {len(rows)} rows to reports")
    print(f"CSV: {OUTPUT_DIR / 'wedding_crawling_summary.csv'}")
    print(f"HTML: {OUTPUT_DIR / 'wedding_crawling_summary.html'}")
    print(f"Clusters: {OUTPUT_DIR / 'topic_clusters.html'}")
    print(f"Keywords: {OUTPUT_DIR / 'keyword_frequency.html'}")


if __name__ == "__main__":
    main()
