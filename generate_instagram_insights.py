import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "reports"
OUTPUT_DIR.mkdir(exist_ok=True)


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


def write_instagram_recommendations(rows, path: Path):
    content_candidates = [
        row for row in rows
        if row.get("keep")
        and row.get("analysis_tier") == "A"
        and row.get("research_use") == "core_problem"
        and row.get("evidence_sentences")
    ]

    lines = ["인스타그램 콘텐츠 후보", ""]
    if not content_candidates:
        lines.append("현재 조건을 만족하는 후보 사례가 없습니다.")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    for idx, row in enumerate(content_candidates[:10], 1):
        lines.append(f"{idx}. {row.get('title', '')}")
        lines.append(f"   - 이슈 유형: {', '.join(row.get('issue_labels', []))}")
        lines.append(f"   - 직접 경험 사례 수: {'예' if row.get('direct_experience') else '아니오'}")
        lines.append(f"   - 출처: {row.get('source', '')}")
        lines.append(f"   - 가격 언급: {', '.join(row.get('price_mentions', []))}")
        lines.append(f"   - 대표 근거: {row.get('evidence_sentences', [''])[0]}")
        lines.append(f"   - 재게시물 제외 여부: {'재게시물' if row.get('is_repost') else '정상'}")
        lines.append(f"   - 보상성 후기 여부: {row.get('incentivized_review')}")
        lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    print("Instagram insights generation is temporarily disabled. Use --generate to enable it.")
