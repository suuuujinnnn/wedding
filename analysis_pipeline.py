from __future__ import annotations

import argparse
import warnings
from pathlib import Path

from wedding_analysis import (
    LABEL_FIELDS,
    REVIEW_FIELDS,
    build_final_topics,
    build_label_template,
    discover_input_files,
    ensure_mapping,
    ensure_search_mapping,
    extract_phrases,
    generate_cooccurrence,
    generate_kwic,
    import_naver,
    load_documents,
    merge_search_volume,
    read_csv,
    write_csv,
    write_run_metadata,
)


ROOT = Path(__file__).resolve().parent


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="정제된 웨딩 게시글의 n-gram, KWIC, 동시출현, 검색량 결합 분석"
    )
    result.add_argument(
        "command",
        choices=("phrases", "kwic", "cooccurrence", "merge-search-volume", "all"),
    )
    result.add_argument("--input", type=Path, help="JSONL 파일 또는 JSONL 디렉터리")
    result.add_argument("--output-dir", type=Path, default=ROOT / "reports")
    result.add_argument("--source", help="특정 source 값만 분석")
    result.add_argument("--min-document-frequency", type=int, default=5)
    result.add_argument("--cluster-min-documents", type=int, default=3)
    result.add_argument("--cooccurrence-min-documents", type=int, default=3)
    result.add_argument("--max-candidates", type=int, default=500)
    result.add_argument("--kwic-sample-count", type=int, default=5)
    result.add_argument("--random-seed", type=int, default=42)
    result.add_argument("--canonical-mapping", type=Path)
    result.add_argument("--naver-keyword-file", type=Path)
    result.add_argument("--search-mapping", type=Path)
    result.add_argument("--community-high-threshold", type=float)
    result.add_argument("--search-high-threshold", type=float)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    mapping_path = args.canonical_mapping or output / "canonical_phrase_mapping.csv"
    search_mapping_path = args.search_mapping or output / "naver_keyword_mapping.csv"
    phrase_path = output / "interest_phrases.csv"
    kwic_path = output / "kwic_review.csv"
    cooccurrence_path = output / "cooccurrence.csv"
    merged_path = output / "community_naver_merged.csv"
    final_path = output / "final_interest_topics.csv"

    captured: list[str] = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        files = discover_input_files(args.input, ROOT)
        if not files:
            raise FileNotFoundError("분석할 JSONL 파일이 없습니다.")
        documents, stats = load_documents(files, args.source)
        if not documents:
            raise ValueError("현재 관련도 규칙을 통과한 정제 게시글이 없습니다.")
        if len(documents) < 20:
            warnings.warn(f"유효 문서가 {len(documents)}건뿐이므로 결과 해석에 주의하세요.")

        phrase_rows = extract_phrases(
            documents, args.min_document_frequency, args.max_candidates,
            args.cluster_min_documents,
        )
        if args.command == "phrases" or (
            args.command != "all" and not phrase_path.exists()
        ):
            write_csv(phrase_path, phrase_rows)
        elif args.command != "all":
            phrase_rows = read_csv(phrase_path)
        mapping_rows = ensure_mapping(mapping_path, phrase_rows)
        search_mapping_rows = ensure_search_mapping(search_mapping_path, mapping_rows)

        if args.command in {"kwic", "all"}:
            prior_kwic = read_csv(kwic_path)
            review_by_key = {
                (row.get("normalized_phrase"), row.get("document_id"), row.get("context")): row
                for row in prior_kwic
            }
            kwic_rows = generate_kwic(
                documents, phrase_rows, args.kwic_sample_count, args.random_seed
            )
            for row in kwic_rows:
                prior = review_by_key.get(
                    (row.get("normalized_phrase"), row.get("document_id"), row.get("context"))
                )
                if prior:
                    for field in REVIEW_FIELDS:
                        row[field] = prior.get(field, "")
            write_csv(kwic_path, kwic_rows)
        else:
            kwic_rows = read_csv(kwic_path)

        if args.command in {"cooccurrence", "all"}:
            cooccurrence_rows = generate_cooccurrence(
                documents, mapping_rows, args.cooccurrence_min_documents
            )
            if args.command == "cooccurrence":
                write_csv(cooccurrence_path, cooccurrence_rows)
        else:
            cooccurrence_rows = read_csv(cooccurrence_path)

        naver_rows = []
        if args.naver_keyword_file:
            if not args.naver_keyword_file.exists():
                raise FileNotFoundError(
                    f"네이버 키워드 파일이 없습니다: {args.naver_keyword_file}"
                )
            naver_rows = import_naver(args.naver_keyword_file)
        elif args.command in {"merge-search-volume", "all"}:
            warnings.warn(
                "네이버 검색량 파일이 없어 결합 값은 비워 둡니다. "
                "--naver-keyword-file로 광고주센터 CSV/XLSX를 지정하세요."
            )

        if args.command in {"merge-search-volume", "all"}:
            merged_rows = merge_search_volume(
                phrase_rows, mapping_rows, search_mapping_rows, naver_rows, documents
            )
            if args.command == "merge-search-volume":
                write_csv(merged_path, merged_rows)
        else:
            merged_rows = read_csv(merged_path)

        if args.command == "all":
            final_rows = build_final_topics(
                documents, phrase_rows, mapping_rows, kwic_rows,
                cooccurrence_rows, merged_rows,
                args.community_high_threshold, args.search_high_threshold,
            )
            write_csv(final_path, final_rows)
            label_path = output / "relevance_evaluation_labels.csv"
            prior_labels = {
                (row.get("source"), row.get("document_id")): row
                for row in read_csv(label_path)
            }
            all_documents, _ = load_documents(files, args.source, include_excluded=True)
            label_rows = build_label_template(all_documents)
            for row in label_rows:
                prior = prior_labels.get((row["source"], row["document_id"]))
                if prior:
                    for field in (
                        "human_relevant", "false_positive_reason",
                        "false_negative_reason", "reviewer_note",
                    ):
                        row[field] = prior.get(field, "")
            write_csv(label_path, label_rows, LABEL_FIELDS)

        captured.extend(str(item.message) for item in caught)
    write_run_metadata(output / "analysis_run_metadata.json", stats, captured)
    print(f"분석 문서: {len(documents)}건 | 출처: {stats['sources']}")
    for message in captured:
        print(f"[경고] {message}")
    print(f"결과 디렉터리: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
