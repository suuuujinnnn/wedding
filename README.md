# Wedding Crawling Report

DC인사이드 결혼 갤러리와 결직웨딩 후기 게시판의 글을 수집해 하나의 HTML 보고서로 정리합니다.

## 파일 구성

- `crawling_dc.py`: DC 관련 키워드 검색 결과에서 게시글을 수집합니다.
- `crawling_kgwed.py`: 결직웨딩 후기 목록에서 게시글을 수집합니다.
- `crawler_utils.py`: 요청, 재시도, robots.txt 확인 등 공통 기능입니다.
- `quality_rules.py`: 서비스와 이슈를 한국어 키워드로 분류합니다.
- `build_reports.py`: 저장된 본문을 다시 분석해 통합 CSV와 HTML을 만듭니다.
- `dc_wedding_posts.jsonl`: DC 상세 본문과 최근 수집 통계입니다.
- `kgwed_posts.jsonl`: 결직 상세 본문과 최근 수집 통계입니다.

## 실행 순서

새 게시글을 수집할 때만 아래 두 명령을 실행합니다.

```bash
python crawling_dc.py
python crawling_kgwed.py
```

보고서의 분류나 화면만 다시 만들 때는 크롤링할 필요가 없습니다.

```bash
python build_reports.py
```

최종 결과는 두 파일입니다.

- `reports/wedding_crawling_summary.html`: DC와 결직 결과를 합친 시각화 보고서
- `reports/wedding_crawling_summary.csv`: 같은 결과의 표 데이터

JSONL을 새로 수집하면 첫 줄에는 목록 페이지, 발견 링크, 상세 페이지 요청·저장 수가 기록되고 나머지 줄에는 게시글이 저장됩니다. 수집 결과가 0건이면 기존 파일을 덮어쓰지 않습니다.

## 설치

```bash
python -m pip install beautifulsoup4 requests urllib3
```

## 관심사 후속 분석

`analysis_pipeline.py`는 크롤러와 기존 `build_reports.py`를 변경하지 않는 후속
분석 단계입니다. 두 JSONL에서 `crawl_summary`를 제외하고 실제 필드
`title`, `body_clean`, `source`, `external_id`, `url`을 읽습니다.
작성일과 클러스터 ID는 현재 저장본에 없으므로 빈 값으로 유지합니다. 향후
`created_at`/`date`/`written_at`, `cluster_id`가 들어오면 로더가 함께 읽습니다.

분석 대상은 `quality_rules.analyze_post()`를 다시 통과한 정제 게시글입니다.
URL·HTML·일부 게시판 UI를 추가 제거하고, 본문 앞에 반복된 제목을 한 번
제거한 뒤 제목과 정제 본문을 각각 한 번 사용합니다. 내용 해시와 긴 정규화
접두부로 동일·재게시물을 제거하되, 원문 URL과 정제 전후 텍스트의 연결은
메모리의 문서 어댑터에 유지합니다.

DC 관련도는 추가금·환불 같은 문제 표현만 요구하지 않습니다. 웨딩 준비
맥락이 있으면서 질문·비교·후기·선택·상담·일정 같은 정보 신호가 있거나,
축의금·결혼 예산·결혼자금·부모 지원·비용 분담·신혼집 자금 같은 재정
관심사가 있으면 분석에 포함합니다. 반대로 성적 대상화, 성별 비하·갈등
조장 표현은 제외합니다. `충격`, `레전드` 같은 제목 표현은 한 단어만으로
제외하지 않고 여러 낚시성 표현이 겹칠 때만 제외하여 정상 후기를 과도하게
잃지 않도록 합니다.

이 저장소에는 기존 TF-IDF, 클러스터링, 형태소 분석기 또는 패키지 관리 파일이
없습니다. 새 분석은 별도 대형 의존성 없이 재현할 수 있도록 한글·영문·숫자
정규식 토큰화와 제한적인 조사 정규화를 사용합니다. 명사만 선별하지 않으므로
행동·상태 표현도 후보에 남습니다. n-gram은 문장별로 만들어 문장 경계를
넘지 않습니다. 이 방식은 완전한 한국어 형태소 분석이 아니므로 KWIC 사람
검수가 필수입니다.

### 실행

전체 후속 분석:

```bash
python analysis_pipeline.py all
```

단계별 실행:

```bash
python analysis_pipeline.py phrases
python analysis_pipeline.py kwic
python analysis_pipeline.py cooccurrence
python analysis_pipeline.py merge-search-volume
```

주요 옵션:

```bash
python analysis_pipeline.py all \
  --input dc_wedding_posts.jsonl \
  --output-dir reports \
  --source dcinside \
  --min-document-frequency 5 \
  --cluster-min-documents 3 \
  --max-candidates 500 \
  --kwic-sample-count 5 \
  --random-seed 42 \
  --canonical-mapping reports/canonical_phrase_mapping.csv \
  --naver-keyword-file path/to/naver-keywords.csv
```

`--input`을 생략하면 두 기본 JSONL을 함께 읽습니다. `--source`를 생략하면
전체 통합 결과와 출처별 결과를 만듭니다. 기본 문서 빈도는 n-gram 5건,
동시출현 3건(`--cooccurrence-min-documents`)입니다. 표본이 기본값보다
작으면 안전한 범위에서 n-gram 문턱을 낮추고 메타데이터에 경고를 남깁니다.
클러스터 결과가 있는 입력은 `--cluster-min-documents`로 최소 문서 수를
바꿀 수 있습니다. 최종 높음/낮음 기준은 기본적으로 중앙값이며
`--community-high-threshold`, `--search-high-threshold`로 직접 지정할 수
있습니다.

### 기본 결과 파일

모든 CSV는 Excel에서 한글이 깨지지 않도록 UTF-8 BOM(`utf-8-sig`)으로
저장합니다.

- `kwic_review.csv`: 후보가 나온 문장과 앞뒤 문장, 제목, 출처, 게시글 ID,
  작성일, 원문 URL 및 빈 검수 컬럼
- `canonical_phrase_mapping.csv`: 사용자가 수정하는 유사 표현 매핑
- `naver_keyword_mapping.csv`: 대표 관심사와 네이버 조회 키워드 연결
- `final_interest_topics.csv`: 대표 표현, 출처 다양성, 검수율, 동시출현어,
  검색량, 활용 방향과 분포 기반 유형
- `relevance_evaluation_labels.csv`: 게시글 관련도 사람 라벨 입력 양식
- `analysis_run_metadata.json`: 입력 필드, 처리 건수, 표본 경고와 해석 한계

`python analysis_pipeline.py all`은 위 핵심 파일만 생성합니다. 상세 중간표가
필요한 경우에만 다음 단계 명령을 실행하면 `interest_phrases.csv`,
`cooccurrence.csv`, `community_naver_merged.csv`가 각각 생성됩니다.

```bash
python analysis_pipeline.py phrases
python analysis_pipeline.py cooccurrence
python analysis_pipeline.py merge-search-volume --naver-keyword-file 네이버파일.csv
```

현재 JSONL에는 TF-IDF/클러스터 필드가 없으므로 `cluster_id`는 비어 있습니다.
추후 실제 `cluster_id`가 저장되면 문서 수 3건 이상인 클러스터 표시가
`interest_phrases.csv`에 포함됩니다. 기존 보고서와 크롤링 명령은 그대로
사용할 수 있습니다.

### KWIC와 canonical mapping 검수

1. `kwic_review.csv`의 원문 URL과 문맥을 확인합니다.
2. `valid_context`에 `true`/`false`, `context_label`과
   `canonical_topic`, `reviewer_note`를 입력합니다.
3. `action`은 `keep`, `merge`, `split`, `exclude` 중 하나로 기록합니다.
4. `canonical_phrase_mapping.csv`에서 같은 의미의 `raw_phrase`에 같은
   `canonical_phrase`를 지정합니다. 제외할 표현은 `status=exclude`로 둡니다.
5. `python analysis_pipeline.py all`을 다시 실행합니다.

기존 매핑과 KWIC 검수 컬럼은 다시 실행해도 보존됩니다. 자동 생성 초안의
`status=pending`은 사람이 검토하지 않았다는 뜻입니다. 분석 결과를
`quality_rules.py`에 자동 반영하지 않습니다.

### 네이버 광고주센터 파일

공식 광고주센터 키워드 도구에서 받은 CSV 또는 XLSX를 로컬에 둔 뒤
`--naver-keyword-file`로 지정합니다. CSV는 UTF-8 또는 CP949를 읽습니다.
XLSX는 선택 의존성인 `openpyxl`이 필요하며, 설치하지 않으려면 CSV로
내보내면 됩니다.

필수 컬럼은 연관키워드, 월간 PC 검색수, 월간 모바일 검색수이며 공백이 있는
한글 이름과 공식 API 형태(`relKeyword`, `monthlyPcQcCnt`,
`monthlyMobileQcCnt`)를 감지합니다. 클릭수·경쟁도·광고 수는 있으면
함께 보존합니다. `'< 10'`은 원본 컬럼에 그대로 두고 수치 컬럼은 결측으로
처리합니다. 둘 중 하나가 `'< 10'`이면 `total_search_volume`도 결측으로
두어 자의적인 추정이나 0 변환을 하지 않습니다.

검색량 파일이 없어도 n-gram, KWIC, 매핑, 동시출현 분석은 실행되며 결합
단계만 빈 검색량과 경고를 남깁니다. 검색량을 임의 생성하거나 외부
비공식 서비스에서 가져오지 않습니다.

### 관련도 평가

`relevance_evaluation_labels.csv`의 `human_relevant`에 `true`/`false`를
입력한 뒤 실행합니다.

```bash
python evaluate_relevance.py
```

라벨이 없으면 수치를 만들지 않고 `검수 데이터 필요`라고 출력합니다.
광고·공지·UI 템플릿 후보도 사람 검수 전에는 자동으로 제외 규칙이 되지
않습니다.

### 해석 한계

커뮤니티 언급 문서 수는 수집 범위 안의 관찰값이며 전체 예비부부의 비율을
뜻하지 않습니다. 특히 결직웨딩은 업체 운영 후기 게시판이므로 광고성·보상성
후기 가능성을 일반 소비자 경험과 동일하게 해석하면 안 됩니다. 네이버
검색량은 네이버 광고 키워드 수요이며 인스타그램 내부 검색량이 아닙니다.
표본이 작거나 검수가 끝나지 않은 후보는 확정 인사이트가 아니라 조사
출발점입니다. NPMI도 낮은 문서 수에서는 불안정하므로 원시 고유 문서 수를
우선 확인하세요.
