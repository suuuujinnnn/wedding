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
    "그리고",
    "그런데",
    "그냥",
    "그러면",
    "그래서",
    "너무",
    "정말",
    "진짜",
    "이제",
    "이번",
    "저는",
    "제가",
    "저희",
    "우리",
    "거의",
    "아주",
    "조금",
    "때문",
    "후기",
    "사진",
    "영상",
    "느낌",
    "생각",
    "추천",
    "문의",
    "상담",
    "계약",
    "결혼",
    "웨딩",
    "예식",
    "신부",
    "신랑",
    "플래너",
    "스드메",
}

SITE_LABELS = {
    "dcinside": "디시인사이드",
    "kgwed": "결직웨딩",
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
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_for_dedup(text: str) -> str:
    text = normalize_text(text).lower()
    text = re.sub(r"[^0-9a-z가-힣]+", " ", text)
    return " ".join(text.split())


def deduplicate(rows):
    unique_rows = []
    seen_signatures = set()

    for row in rows:
        title = normalize_for_dedup(row.get("title", ""))
        body = normalize_for_dedup(row.get("body", ""))
        content_hash = row.get("content_hash", "")

        signature = ("source", row.get("source", ""), row.get("external_id", ""))
        if content_hash:
            signature = ("hash", content_hash)
        elif title or body:
            signature = ("text", row.get("source", ""), title, body[:300])

        if signature in seen_signatures:
            continue

        seen_signatures.add(signature)
        unique_rows.append(row)

    return unique_rows


def preview_text(text: str, length: int = 180) -> str:
    text = normalize_text(text)
    if len(text) <= length:
        return text
    return text[:length] + "..."


def tokenize(text: str):
    tokens = re.findall(r"[0-9A-Za-z가-힣]{2,}", normalize_text(text))
    return [token for token in tokens if token not in STOPWORDS]


def join_values(value):
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value if item)
    return str(value or "")


def write_csv(rows, path: Path):
    fieldnames = [
        "source",
        "research_use",
        "analysis_tier",
        "service_categories",
        "issue_labels",
        "price_mentions",
        "direct_experience",
        "is_repost",
        "title",
        "evidence",
        "url",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "source": row.get("source", ""),
                    "research_use": row.get("research_use", ""),
                    "analysis_tier": row.get("analysis_tier", ""),
                    "service_categories": join_values(row.get("service_categories", [])),
                    "issue_labels": join_values(row.get("issue_labels", [])),
                    "price_mentions": join_values(row.get("price_mentions", [])),
                    "direct_experience": row.get("direct_experience", False),
                    "is_repost": row.get("is_repost", False),
                    "title": row.get("title", ""),
                    "evidence": " / ".join(row.get("evidence_sentences", [])),
                    "url": row.get("url", ""),
                }
            )


def group_by_issue(rows):
    grouped = {}
    for row in rows:
        for issue in row.get("issue_labels", []):
            grouped.setdefault(issue, []).append(row)
    return grouped


def build_summary_cards(rows):
    source_counts = Counter(row.get("source", "unknown") for row in rows)
    research_use_counts = Counter(row.get("research_use", "exclude") for row in rows)
    tier_counts = Counter(row.get("analysis_tier", "unknown") for row in rows)

    cards = [
        ("총 항목", len(rows)),
    ]

    for source_name, count in sorted(source_counts.items()):
        cards.append((SITE_LABELS.get(source_name, source_name), count))
    for name, count in sorted(research_use_counts.items()):
        cards.append((name, count))
    for tier, count in sorted(tier_counts.items()):
        cards.append((f"등급 {tier}", count))

    return cards


def render_cards(cards):
    return "".join(
        f"<div class='card'><h3>{escape(str(label))}</h3><p>{count}</p></div>"
        for label, count in cards
    )


def render_table(rows):
    if not rows:
        return "<p class='empty-state'>표시할 항목이 없습니다.</p>"

    table_rows = []
    for row in rows:
        url = row.get("url", "")
        title = escape(row.get("title", ""))
        evidence = escape(preview_text(" / ".join(row.get("evidence_sentences", []))))
        table_rows.append(
            "<tr>"
            f"<td>{escape(row.get('source', ''))}</td>"
            f"<td>{escape(row.get('research_use', ''))}</td>"
            f"<td>{escape(row.get('analysis_tier', ''))}</td>"
            f"<td>{escape(join_values(row.get('service_categories', [])))}</td>"
            f"<td>{escape(join_values(row.get('issue_labels', [])))}</td>"
            f"<td>{escape(join_values(row.get('price_mentions', [])))}</td>"
            f"<td>{'예' if row.get('direct_experience') else '아니오'}</td>"
            f"<td>{'예' if row.get('is_repost') else '아니오'}</td>"
            f"<td class='title-cell'><a href='{escape(url)}' target='_blank' rel='noreferrer'>{title}</a></td>"
            f"<td>{evidence}</td>"
            "</tr>"
        )

    return f"""
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>출처</th>
            <th>연구용도</th>
            <th>등급</th>
            <th>서비스</th>
            <th>이슈</th>
            <th>가격</th>
            <th>직접 경험</th>
            <th>재게시</th>
            <th>제목</th>
            <th>근거</th>
          </tr>
        </thead>
        <tbody>
          {''.join(table_rows)}
        </tbody>
      </table>
    </div>
    """


def render_issue_sections(rows):
    grouped = group_by_issue(rows)
    if not grouped:
        return "<p class='empty-state'>표시할 이슈가 없습니다.</p>"

    sections = []
    for issue, group in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        direct_count = sum(1 for row in group if row.get("direct_experience"))
        repost_count = sum(1 for row in group if row.get("is_repost"))
        price_mentions = sorted({item for row in group for item in row.get("price_mentions", [])})
        source_counts = Counter(row.get("source", "unknown") for row in group)
        evidence_items = []
        for row in group[:4]:
            evidence_items.extend(row.get("evidence_sentences", []))

        sections.append(
            "<section class='cluster'>"
            f"<div class='cluster-head'><h3>{escape(issue)}</h3><span>{len(group)}건</span></div>"
            f"<p class='meta'>직접 경험 {direct_count}건 · 재게시 {repost_count}건 · 출처 {escape(', '.join(f'{SITE_LABELS.get(src, src)} {count}' for src, count in sorted(source_counts.items())))} </p>"
            f"<p class='meta'>언급된 가격: {escape(', '.join(price_mentions) if price_mentions else '없음')}</p>"
            f"<ul>{''.join(f'<li>{escape(item)}</li>' for item in evidence_items[:5])}</ul>"
            "<div class='link-row'>"
            + "".join(
                f"<a class='chip-link' href='{escape(row.get('url', ''))}' target='_blank' rel='noreferrer'>원문 {idx}</a>"
                for idx, row in enumerate(group[:3], 1)
            )
            + "</div>"
            "</section>"
        )

    return "".join(sections)


def render_keyword_bars(rows, limit: int = 40):
    counter = Counter()
    for row in rows:
        counter.update(tokenize(" ".join(row.get("evidence_sentences", []))))

    if not counter:
        return "<p class='empty-state'>표시할 키워드가 없습니다.</p>"

    max_count = max(counter.values())
    items = []
    for keyword, count in counter.most_common(limit):
        width = int(count / max_count * 100)
        items.append(
            "<div class='keyword-row'>"
            f"<div class='keyword-label'>{escape(keyword)} <span>({count})</span></div>"
            f"<div class='bar'><div class='fill' style='width:{width}%'></div></div>"
            "</div>"
        )

    return "<div class='keyword-list'>" + "".join(items) + "</div>"


def render_page(title: str, rows, body, subtitle: str = ""):
    summary_cards = render_cards(build_summary_cards(rows))
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --surface: #ffffff;
      --surface-alt: #f8faff;
      --text: #172033;
      --muted: #667085;
      --line: #dde4f0;
      --accent: #3657d6;
      --accent-2: #8b5cf6;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", Arial, sans-serif;
      background: linear-gradient(180deg, #f8faff 0%, var(--bg) 100%);
      color: var(--text);
    }}
    .page {{
      max-width: 1480px;
      margin: 0 auto;
      padding: 28px 20px 40px;
    }}
    header {{
      margin-bottom: 18px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 30px;
      letter-spacing: -0.02em;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin: 22px 0;
    }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px 16px;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.05);
    }}
    .card h3 {{
      margin: 0 0 8px;
      font-size: 13px;
      color: var(--muted);
      font-weight: 600;
    }}
    .card p {{
      margin: 0;
      font-size: 24px;
      line-height: 1;
      font-weight: 800;
      color: var(--text);
    }}
    section {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      margin-bottom: 18px;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.05);
    }}
    section h2 {{
      margin: 0 0 14px;
      font-size: 20px;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 14px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 1180px;
      background: white;
    }}
    thead th {{
      position: sticky;
      top: 0;
      background: #edf2ff;
      z-index: 1;
    }}
    th, td {{
      border-bottom: 1px solid #e7ebf3;
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
      line-height: 1.5;
    }}
    tbody tr:nth-child(even) {{
      background: #fbfcff;
    }}
    .title-cell {{
      min-width: 280px;
    }}
    .title-cell a {{
      color: var(--accent);
      font-weight: 600;
      text-decoration: none;
    }}
    .title-cell a:hover {{
      text-decoration: underline;
    }}
    .empty-state {{
      margin: 0;
      color: var(--muted);
    }}
    .cluster {{
      background: var(--surface-alt);
      border: 1px solid #e4e9f7;
      border-radius: 16px;
      padding: 16px;
      margin-bottom: 14px;
    }}
    .cluster-head {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
    }}
    .cluster-head h3 {{
      margin: 0;
      font-size: 18px;
    }}
    .cluster-head span {{
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }}
    .meta {{
      margin: 0 0 8px;
      color: var(--muted);
      font-size: 14px;
    }}
    ul {{
      margin: 10px 0 12px;
      padding-left: 18px;
    }}
    li {{
      margin-bottom: 6px;
      line-height: 1.5;
    }}
    .link-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .chip-link {{
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      background: white;
      border: 1px solid var(--line);
      color: var(--accent);
      text-decoration: none;
      font-size: 13px;
      font-weight: 600;
    }}
    .keyword-list {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 12px 16px;
    }}
    .keyword-row {{
      padding: 12px 14px;
      border: 1px solid #e7ebf3;
      border-radius: 14px;
      background: #fcfdff;
    }}
    .keyword-label {{
      margin-bottom: 8px;
      font-weight: 700;
      color: var(--text);
    }}
    .keyword-label span {{
      color: var(--muted);
      font-weight: 600;
    }}
    .bar {{
      height: 10px;
      background: #e8edf5;
      border-radius: 999px;
      overflow: hidden;
    }}
    .fill {{
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--accent-2), var(--accent));
    }}
    a {{
      color: var(--accent);
    }}
    @media (max-width: 800px) {{
      .page {{
        padding: 18px 12px 30px;
      }}
      h1 {{
        font-size: 24px;
      }}
      section {{
        padding: 14px;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <header>
      <h1>{escape(title)}</h1>
      {f'<p class="subtitle">{escape(subtitle)}</p>' if subtitle else ''}
    </header>
    <div class="summary">{summary_cards}</div>
    {body}
  </div>
</body>
</html>
"""
    return html


def write_html(rows, path: Path, title: str):
    body = (
        "<section><h2>요약 테이블</h2>"
        f"{render_table(rows)}"
        "</section>"
        "<section><h2>이슈 그룹</h2>"
        f"{render_issue_sections(rows)}"
        "</section>"
        "<section><h2>키워드 빈도</h2>"
        f"{render_keyword_bars(rows)}"
        "</section>"
    )
    path.write_text(render_page(title, rows, body, subtitle=f"총 {len(rows)}건의 항목을 정리했습니다."), encoding="utf-8")


def write_issue_groups(rows, path: Path):
    body = (
        "<section><h2>이슈 그룹</h2>"
        f"{render_issue_sections(rows)}"
        "</section>"
    )
    path.write_text(render_page("이슈 그룹", rows, body, subtitle="이슈별로 사례와 근거를 묶어 봤습니다."), encoding="utf-8")


def write_keyword_frequency(rows, path: Path):
    body = (
        "<section><h2>키워드 빈도</h2>"
        f"{render_keyword_bars(rows)}"
        "</section>"
    )
    path.write_text(render_page("근거 문장 키워드", rows, body, subtitle="근거 문장에서 반복되는 표현을 정리했습니다."), encoding="utf-8")


def build_site_reports(rows, output_dir: Path):
    for source_name, display_name in SITE_LABELS.items():
        site_rows = [row for row in rows if row.get("source") == source_name]
        if not site_rows:
            continue
        write_csv(site_rows, output_dir / f"{source_name}_summary.csv")
        write_html(site_rows, output_dir / f"{source_name}_summary.html", f"{display_name} 웨딩 문제 요약")


def main():
    rows = deduplicate(load_rows())

    valid_rows = [row for row in rows if row.get("keep") is True]
    core_rows = [
        row
        for row in valid_rows
        if row.get("research_use") in {"core_problem", "planner_workflow"}
    ]

    core_rows = sorted(
        core_rows,
        key=lambda row: (
            row.get("source", ""),
            row.get("research_use", ""),
            row.get("title", ""),
        ),
    )

    write_csv(core_rows, OUTPUT_DIR / "wedding_crawling_summary.csv")
    write_html(core_rows, OUTPUT_DIR / "wedding_crawling_summary.html", "웨딩 문제 요약")
    write_issue_groups(core_rows, OUTPUT_DIR / "issue_groups.html")
    write_keyword_frequency(core_rows, OUTPUT_DIR / "keyword_frequency.html")

    build_site_reports(valid_rows, OUTPUT_DIR)

    print(f"Saved {len(core_rows)} rows to reports")
    print(f"CSV: {OUTPUT_DIR / 'wedding_crawling_summary.csv'}")
    print(f"HTML: {OUTPUT_DIR / 'wedding_crawling_summary.html'}")
    print("Site-specific reports: dcinside_summary.csv, kgwed_summary.csv")


if __name__ == "__main__":
    main()
