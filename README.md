# Wedding Research Pipeline

이 저장소는 웨딩 관련 커뮤니티/후기 사이트에서 게시글을 수집하고,
TF-IDF + KMeans로 클러스터링한 뒤,
웨딩 문제 유형으로 재분류해 보고서로 정리하는 흐름을 담고 있습니다.

## 작업 순서

1. 크롤링
   - 디시인사이드 웨딩 갤러리 게시글을 넓게 수집합니다.
   - 결직웨딩 후기 게시판의 게시글을 수집합니다.
   - 각 게시글의 URL, 제목, 본문, HTML 스니펫을 저장합니다.

2. 품질 분류
   - quality_rules.py의 규칙으로 웨딩 문제 유형과 연구용도를 판단합니다.
   - keep 여부, issue_labels, research_use, analysis_tier를 부여합니다.

3. 중복 제거
   - 제목/본문 기준으로 중복 게시글을 제거합니다.

4. TF-IDF + KMeans 클러스터링
   - tfidf_cluster.py가 각 사이트별로 TF-IDF 벡터를 만들고 KMeans로 클러스터를 생성합니다.
   - 관련 없는 클러스터는 제외하고, 유효 클러스터만 남깁니다.

5. 보고서 생성
   - build_reports.py가 사이트별 요약 CSV/HTML과 이슈 그룹 보고서를 생성합니다.
   - reports/ 아래에 사이트별 파일이 생성됩니다.

## 주요 파일

- crawling_dc.py: 디시인사이드 크롤러
- crawling_kgwed.py: 결직웨딩 크롤러
- quality_rules.py: 웨딩 문제 유형 분류 규칙
- tfidf_cluster.py: TF-IDF + KMeans 클러스터링
- build_reports.py: 요약/이슈/키워드 보고서 생성
