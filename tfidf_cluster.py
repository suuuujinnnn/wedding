import hashlib
import html
import json
import re
from pathlib import Path
from html import escape

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


ROOT = Path(__file__).resolve().parent
INPUT_FILES = {
    "dcinside": ROOT / "dc_wedding_posts.jsonl",
    "kgwed": ROOT / "kgwed_posts.jsonl",
}
OUTPUT_DIR = ROOT / "reports"
OUTPUT_DIR.mkdir(exist_ok=True)

N_CLUSTERS = 8

STOPWORDS = [
    "그리고", "하지만", "그래서", "그런데",
    "이렇게", "이런", "그런", "저는", "제가",
    "저희", "우리", "정말", "진짜", "너무",
    "그냥", "같은", "같아요", "있어요",
    "있습니다", "하는", "해서", "하면",
    "때문", "정도", "이번", "지금",
    "사람", "생각", "결혼", "결혼식",
]


def normalize_text(text: str) -> str:
    text = html.unescape(text or "")

    # URL 제거
    text = re.sub(r"https?://\S+", " ", text)

    # HTML 엔티티 잔여물 제거
    text = re.sub(r"&[a-zA-Z0-9#]+;", " ", text)
    text = re.sub(r"[^가-힣a-zA-Z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"잘못된 JSONL: {line_number}행")
    return rows


def deduplicate(rows: list[dict]) -> list[dict]:
    unique_rows = []
    seen_hashes = set()

    for row in rows:
        title = normalize_text(row.get("title", ""))
        body = normalize_text(row.get("body", ""))
        normalized = f"{title} {body}".lower()
        text_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

        if text_hash in seen_hashes:
            continue

        seen_hashes.add(text_hash)
        row["analysis_text"] = normalized
        unique_rows.append(row)

    return unique_rows


def get_cluster_keywords(model: KMeans, vectorizer: TfidfVectorizer, top_n: int = 12) -> dict[int, list[str]]:
    feature_names = vectorizer.get_feature_names_out()
    ordered_indices = model.cluster_centers_.argsort(axis=1)[:, ::-1]
    cluster_keywords = {}

    for cluster_id in range(model.n_clusters):
        cluster_keywords[cluster_id] = [
            feature_names[index]
            for index in ordered_indices[cluster_id, :top_n]
        ]

    return cluster_keywords


def write_cluster_html(dataframe: pd.DataFrame, output_path: Path, site_name: str) -> None:
    sections = []
    for cluster_id in sorted(dataframe["cluster_id"].unique()):
        cluster_rows = dataframe[dataframe["cluster_id"] == cluster_id]
        keywords = ", ".join(cluster_rows["cluster_keywords"].iloc[0].split(", ")[:8])
        examples = "<br/>".join(f"- {escape(title)}" for title in cluster_rows["title"].head(5))
        sections.append(
            f"<section><h2>Cluster {cluster_id}</h2><p>{escape(keywords)}</p><p>{examples}</p></section>"
        )

    html = f"""<!DOCTYPE html>
<html lang='ko'>
<head><meta charset='utf-8'/><title>{site_name} TF-IDF 클러스터</title></head>
<body><h1>{site_name} TF-IDF 클러스터</h1>{''.join(sections)}</body></html>"""
    output_path.write_text(html, encoding="utf-8")


def process_site(site_name: str, path: Path) -> None:
    rows = load_jsonl(path)
    rows = deduplicate(rows)

    if len(rows) < 20:
        print(f"[{site_name}] 문서 수가 적어 클러스터링을 건너뜁니다: {len(rows)}")
        return

    dataframe = pd.DataFrame(rows)
    vectorizer = TfidfVectorizer(
        token_pattern=r"(?u)\b[가-힣a-zA-Z0-9]{2,}\b",

        # 단어 하나와 두 단어 조합을 함께 사용
        # 예: 추가금 / 드레스 추가금
        ngram_range=(1, 2),

        # 최소 2개 문서에서 나온 단어만 사용
        min_df=2,

        # 전체 문서의 80% 이상에서 나온 단어 제외
        max_df=0.8,
        max_features=5000,
        stop_words=STOPWORDS,

        # 한 문서에 반복되는 단어 영향 완화
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(dataframe["analysis_text"])

    cluster_count = min(N_CLUSTERS, max(2, len(dataframe) // 15))
    model = KMeans(n_clusters=cluster_count, random_state=42, n_init=20)
    dataframe["cluster_id"] = model.fit_predict(matrix)

    cluster_keywords = get_cluster_keywords(model=model, vectorizer=vectorizer)
    dataframe["cluster_keywords"] = dataframe["cluster_id"].apply(lambda cid: ", ".join(cluster_keywords[cid]))
    dataframe["preview"] = dataframe["analysis_text"].str.slice(0, 220)

    relevant_cluster_ids = {
        cluster_id
        for cluster_id, group in dataframe.groupby("cluster_id")
        if group["keep"].fillna(False).astype(bool).any()
        and group["research_use"].isin({"core_problem", "planner_workflow"}).any()
    }

    filtered = dataframe[dataframe["cluster_id"].isin(relevant_cluster_ids)].copy()
    filtered["reclassified_issue"] = filtered.apply(
        lambda row: " / ".join(row.get("issue_labels", [])) if row.get("keep") and row.get("research_use") in {"core_problem", "planner_workflow"} else "irrelevant",
        axis=1,
    )

    output_columns = [
        "cluster_id",
        "cluster_keywords",
        "source",
        "title",
        "preview",
        "url",
        "reclassified_issue",
        "research_use",
        "analysis_tier",
    ]

    output_path = OUTPUT_DIR / f"{site_name}_tfidf_clusters.csv"
    filtered[output_columns].sort_values(["cluster_id", "title"]).to_csv(output_path, index=False, encoding="utf-8-sig")
    write_cluster_html(filtered, OUTPUT_DIR / f"{site_name}_tfidf_clusters.html", site_name)

    print(f"[{site_name}] saved {len(filtered)} relevant rows -> {output_path}")


def main() -> None:
    for site_name, path in INPUT_FILES.items():
        process_site(site_name, path)


if __name__ == "__main__":
    main()