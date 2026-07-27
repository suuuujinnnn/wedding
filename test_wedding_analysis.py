import csv
import json
import tempfile
import unittest
from pathlib import Path

from wedding_analysis import (
    Document,
    active_mapping,
    build_final_topics,
    extract_phrases,
    generate_cooccurrence,
    generate_kwic,
    import_naver,
    load_documents,
    parse_volume,
    sentence_ngrams,
)
from quality_rules import analyze_post


class WeddingAnalysisTests(unittest.TestCase):
    def document(self, document_id, body, source="test", url=None):
        return Document(
            document_id=document_id, source=source, title="테스트 제목",
            body_clean=body, body_original=body,
            url=url or f"https://example.test/{document_id}",
        )

    def test_ngram_does_not_cross_sentence_boundary(self):
        first = sentence_ngrams("첫문장 끝")
        second = sentence_ngrams("다음문장 시작")
        phrases = {normalized for _, normalized, _ in first + second}
        self.assertNotIn("끝 다음문장", phrases)

    def test_kwic_document_link_and_repeat_deduplication(self):
        docs = [self.document("1", "계약 취소 문의입니다. 계약 취소 문의입니다.")]
        phrases = [{"source": "all", "normalized_phrase": "계약 취소", "phrase": "계약 취소"}]
        rows = generate_kwic(docs, phrases, sample_count=10)
        self.assertEqual(1, len(rows))
        self.assertEqual("https://example.test/1", rows[0]["url"])

    def test_document_count_ignores_repeated_phrase_and_scopes_are_distinct(self):
        docs = [
            self.document("1", "드레스 투어 좋았어요. 드레스 투어 또 했어요.", "one"),
            self.document("2", "드레스 투어 만족했어요.", "two"),
        ]
        rows = extract_phrases(docs, min_document_frequency=1, max_candidates=100)
        matching = {
            row["source"]: row
            for row in rows if row["normalized_phrase"] == "드레스 투어"
        }
        self.assertEqual(2, matching["all"]["document_count"])
        self.assertEqual(3, matching["all"]["occurrence_count"])
        self.assertEqual({"all", "one", "two"}, set(matching))

    def test_duplicate_documents_are_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.jsonl"
            post = {
                "record_type": "post", "source": "kgwed", "external_id": "1",
                "title": "웨딩홀 견적 후기", "body_clean": "웨딩홀 견적 가격 비교가 어려웠어요.",
                "url": "https://example.test/1",
            }
            path.write_text(
                json.dumps(post, ensure_ascii=False) + "\n"
                + json.dumps({**post, "external_id": "2"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            docs, stats = load_documents([path])
            self.assertEqual(1, len(docs))
            self.assertEqual(1, stats["counts"]["duplicates"])

    def test_mapping_and_self_cooccurrence_exclusion(self):
        mappings = [
            {"raw_phrase": "계약 취소", "canonical_phrase": "취소 문제", "status": "keep"},
            {"raw_phrase": "계약취소", "canonical_phrase": "취소 문제", "status": "keep"},
        ]
        self.assertEqual("취소 문제", active_mapping(mappings)["계약 취소"])
        docs = [
            self.document(str(index), "계약 취소 때문에 환불 상담 필요")
            for index in range(3)
        ]
        rows = generate_cooccurrence(docs, mappings, min_document_frequency=3)
        self.assertFalse(
            any(row["cooccurring_phrase"].replace(" ", "") in "취소문제" for row in rows)
        )

    def test_canonical_mapping_reaggregates_variant_documents(self):
        docs = [
            self.document("1", "계약 취소 때문에 고민입니다."),
            self.document("2", "계약취소 관련 환불 문의입니다."),
        ]
        mappings = [
            {"raw_phrase": "계약 취소", "canonical_phrase": "취소 문제", "status": "keep"},
            {"raw_phrase": "계약취소", "canonical_phrase": "취소 문제", "status": "keep"},
        ]
        final = build_final_topics(docs, [], mappings, [], [], [])
        self.assertEqual(1, len(final))
        self.assertEqual(2, final[0]["community_document_count"])

    def test_less_than_ten_is_not_zero(self):
        raw, numeric = parse_volume("< 10")
        self.assertEqual("< 10", raw)
        self.assertIsNone(numeric)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "naver.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=["연관키워드", "월간 PC 검색수", "월간 모바일 검색수"]
                )
                writer.writeheader()
                writer.writerow({
                    "연관키워드": "테스트", "월간 PC 검색수": "< 10",
                    "월간 모바일 검색수": "20",
                })
            row = import_naver(path)[0]
            self.assertEqual("< 10", row["pc_search_volume_raw"])
            self.assertIsNone(row["pc_search_volume_numeric"])
            self.assertIsNone(row["total_search_volume"])

    def test_dc_finance_and_useful_question_are_relevant(self):
        finance = analyze_post(
            "결혼자금 비용 분담 어떻게 하셨나요",
            "예식 비용과 신혼집 자금을 부모님 지원 없이 준비한 경험이 궁금합니다.",
            "dcinside",
        )
        question = analyze_post(
            "드레스 투어 어디가 괜찮나요",
            "두 업체를 비교 중인데 직접 방문한 후기와 선택 팁이 궁금합니다.",
            "dcinside",
        )
        self.assertTrue(finance["keep"])
        self.assertEqual("웨딩 비용·자금", finance["research_use"])
        self.assertTrue(question["keep"])
        self.assertEqual("웨딩 준비 사례", question["research_use"])

    def test_dc_sensational_gender_conflict_is_excluded(self):
        result = analyze_post(
            "한남 한녀 결혼 레전드 충격",
            "웨딩홀이라는 단어를 넣었지만 성별 갈등만 조장하는 글입니다.",
            "dcinside",
        )
        self.assertFalse(result["keep"])
        self.assertIn("선정적", result["reject_reason"])
        sexual_shaming = analyze_post(
            "비처녀는 웨딩드레스 입으면 안 되나요",
            "웨딩드레스 이야기를 빌려 성적 비하만 하는 글입니다.",
            "dcinside",
        )
        self.assertFalse(sexual_shaming["keep"])

    def test_generic_makeup_and_relationship_discourse_are_excluded(self):
        makeup = analyze_post(
            "남성 메이크업 초보자는 뭘 사면 좋나요",
            "일상 메이크업 제품 추천이 궁금합니다.",
            "dcinside",
        )
        discourse = analyze_post(
            "비혼주의자가 바라보는 결혼",
            "연애와 결혼의 장단점에 대한 일반적인 생각입니다.",
            "dcinside",
        )
        marriage_market = analyze_post(
            "연봉 5억 의사만 가능하다는 요즘 결혼시장",
            "결혼정보업체 커플매니저가 말하는 일반적인 결혼시장 기사입니다.",
            "dcinside",
        )
        self.assertFalse(makeup["keep"])
        self.assertFalse(discourse["keep"])
        self.assertFalse(marriage_market["keep"])

    def test_dc_board_recommendation_ui_is_not_interest_signal(self):
        result = analyze_post(
            "예식장 관련 짧은 글",
            "예식장 추천검색 추천 12 비추천 0 개념 추천 스크랩 신고",
            "dcinside",
        )
        self.assertFalse(result["keep"])


if __name__ == "__main__":
    unittest.main()
