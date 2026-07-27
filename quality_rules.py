import html
import re


SERVICE_KEYWORDS = {
    "웨딩홀": [
        "웨딩홀", "예식장", "대관료", "식대", "보증인원", "꽃장식", "홀투어",
    ],
    "스튜디오·촬영": [
        "웨딩촬영", "스튜디오", "본식스냅", "원본사진", "앨범", "사진 셀렉",
    ],
    "드레스": [
        "드레스", "드레스샵", "드레스투어", "드투", "피팅", "가봉", "헬퍼비",
    ],
    "메이크업": [
        "메이크업", "메컵", "헤어메이크업", "얼리스타트", "출장비",
    ],
    "플래너": [
        "웨딩플래너", "동행플래너", "비동행플래너", "플래너 상담", "플래너 추천",
    ],
    "스드메·패키지": [
        "스드메", "드메", "웨딩패키지", "웨딩박람회", "제휴업체", "결직웨딩",
    ],
    "예물·혼수": [
        "예물", "예복", "혼주한복", "신랑신부 한복", "혼수", "웨딩밴드", "부케",
    ],
}


ISSUE_KEYWORDS = {
    "예상 밖 추가비용": [
        "추가금", "추가 비용", "별도 비용", "원본비", "헬퍼비", "피팅비",
        "업그레이드 비용", "부가세 별도", "비용이 추가", "추가로 내",
    ],
    "가격·견적 정보": [
        "견적", "가격 비교", "가격비교", "가격이 다르", "견적이 다르", "정찰제",
        "총액", "최종 비용", "가격 안내", "금액이 명시", "가격대", "가성비",
        "결혼식 비용", "웨딩 비용", "얼마정도", "얼마 정도", "저렴", "비싸",
    ],
    "계약·취소·환불": [
        "계약금", "예약금", "홀딩비", "환불", "취소", "위약금", "약관",
        "계약 취소", "예약 취소", "사기당", "계약 피해",
    ],
    "제휴·수수료 구조": [
        "제휴", "연계", "수수료", "고가라인", "강매", "당일 계약",
    ],
    "일정·예약 관리": [
        "일정 체크", "일정 관리", "일정 안내", "예약 변경", "카카오톡 안내",
        "준비물", "주차 안내", "스케쥴", "스케줄", "챙겨주", "몇시간",
        "몇 시간", "예약하기", "예식장 잡", "식장 잡",
    ],
    "서비스 불편·품질 문제": [
        "불친절", "지연", "누락", "실수", "재촬영", "보정 불만", "결과물 문제",
        "실망", "아쉬웠", "별로였", "문제가 있었", "연락이 안",
    ],
    "선택 피로·정보 부족": [
        "선택할 게", "알아보기 힘들", "비교하기 어렵", "정보가 없", "막막",
        "정신이 없", "시간이 부족", "번거롭", "지쳤", "어렵기도",
    ],
}


# 성적 대상화·성별 비하·갈등 조장처럼 웨딩 준비 정보로 재해석하기
# 어려운 표현입니다. 일반적인 비용·주거·정책 단어는 여기에 넣지 않습니다.
SENSATIONAL_NOISE_TERMS = [
    "씨를 뿌", "번식성공", "번식 성공", "섹스 가능한",
    "한남", "한녀", "노괴", "퐁퐁남", "설거지론", "도태남",
    "비처녀", "처녀성", "순결", "성경험", "먹버", "ㅅㅅ",
    "오지콤", "창녀", "걸레", "프리섹스", "섹-스", "아다",
    "경험 없는 여자",
]


# 특정 서비스 홍보나 웨딩 준비와 무관한 연애·결혼 일반 담론을 식별합니다.
# 이 목록은 강한 웨딩 준비 맥락보다 우선하는 명백한 노이즈만 둡니다.
UNRELATED_NOISE_TERMS = [
    "내집스캔", "청소업체직원", "결정사 가입", "결정사 후기",
    "연애상담", "전남친", "전여친",
]


# 한 단어만으로 제외하지 않고 제목에서 두 개 이상 겹칠 때만 과도한
# 낚시성 표현으로 봅니다.
SENSATIONAL_TITLE_MARKERS = [
    "충격", "경악", "소름", "난리났다", "실화냐", "레전드",
    "역대급", "미쳤다", "혐)", "주의)",
]


PREFERENCE_MARKERS = [
    "선택했", "골랐", "추천", "마음에 들", "스타일", "분위기", "친절",
    "만족", "잘 어울", "계약했", "상담받", "방문했", "촬영했", "투어했",
]


WEDDING_CONTEXT_TERMS = (
    "웨딩", "결혼", "예식", "예식장", "스드메", "플래너", "업체", "신혼",
    "혼수", "촬영", "드레스", "메이크업", "앨범", "본식", "신부", "신랑",
)


DC_PREPARATION_TERMS = (
    "결혼 준비", "결혼준비", "결혼식 비용", "결혼식 식장", "웨딩 비용",
    "웨딩홀", "예식장", "스드메", "웨딩촬영", "웨딩 촬영", "본식스냅",
    "드레스투어", "드레스 투어", "드레스샵", "드레스 샵", "웨딩드레스",
    "웨딩 메이크업", "헤어메이크업",
    "플래너", "웨딩밴드", "부케", "예물", "예복", "가봉", "식대", "축의금",
    "결혼자금", "결혼 자금", "결혼예산", "결혼 예산", "예식비", "예식 비용",
    "부모님 지원", "부모 지원", "비용 분담", "결혼 비용 분담", "혼수 비용",
    "신혼집 자금", "신혼집 예산", "결혼 대출", "웨딩 대출",
)


FINANCE_INTEREST_TERMS = (
    "축의금", "답례품", "하객 비용", "결혼자금", "결혼 자금", "결혼예산",
    "결혼 예산", "예식비", "예식 비용", "웨딩 비용", "결혼식 비용",
    "부모님 지원", "부모 지원", "비용 분담", "결혼 비용 분담",
    "공동 부담", "혼수 비용", "예물 비용", "신혼집 자금", "신혼집 예산",
    "결혼 대출", "웨딩 대출", "결혼 적금", "웨딩 적금", "예산표",
)


# 불만뿐 아니라 질문·비교·선택·경험처럼 정보성 콘텐츠나 인터뷰 소재가
# 될 만한 신호를 포함합니다.
INFORMATION_INTEREST_MARKERS = (
    "?", "궁금", "어떻게", "어디", "얼마", "괜찮", "어때", "질문", "문의",
    "추천", "비교", "차이", "고민", "후기", "경험", "팁", "정보",
    "체크리스트", "선택", "골랐", "계약했", "상담", "방문",
    "투어", "견적", "예산", "비용", "가격", "일정", "예약",
)


RELATIONSHIP_DISCOURSE_MARKERS = (
    "비혼주의", "결혼시장", "결혼정보업체", "스타 커매", "커플매니저",
    "소개팅", "연애 상대", "예쁜 여자", "예쁜 남자", "여자들", "남자들",
    "여자는", "남자는",
    "여친", "남친",
)


PREPARATION_ACTION_MARKERS = (
    "계약했", "계약하려", "예약했", "예약하려", "견적 받", "견적받",
    "상담받", "상담 받", "투어했", "투어 중", "방문했", "다녀왔",
    "촬영했", "피팅했", "가봉", "준비 중", "준비중", "예비부부",
    "예비신부", "예비 신부", "예비신랑", "예비 신랑",
)


PRICE_PATTERN = re.compile(
    r"\d{1,3}(?:,\d{3})+\s*원|"
    r"\d+(?:\.\d+)?\s*만\s*원|"
    r"\d+\s*천\s*원|"
    r"\d+(?:\.\d+)?\s*억(?:\s*원)?"
)


def normalize_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\b(?:조회|추천|비추천|댓글)\s*\d+\b", " ", text)
    text = re.sub(r"\s추천검색\b.*$", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def match_groups(text: str, groups: dict[str, list[str]]) -> list[str]:
    return [
        label
        for label, keywords in groups.items()
        if any(keyword in text for keyword in keywords)
    ]


def contains_any(text: str, terms: tuple[str, ...] | list[str]) -> bool:
    return any(term in text for term in terms)


def extract_evidence_sentences(text: str) -> list[str]:
    issue_terms = [keyword for keywords in ISSUE_KEYWORDS.values() for keyword in keywords]
    evidence = []

    for sentence in re.split(r"(?<=[.!?。])\s+|\n+", text):
        sentence = sentence.strip()
        if len(sentence) < 12:
            continue
        if contains_any(sentence, issue_terms) or PRICE_PATTERN.search(sentence):
            evidence.append(sentence[:360])

    return evidence[:5]


def analyze_post(title: str, body: str, source: str) -> dict:
    title = normalize_text(title)
    body = normalize_text(body)
    text = f"{title} {body}"

    services = match_groups(text, SERVICE_KEYWORDS)
    issues = match_groups(text, ISSUE_KEYWORDS)
    has_wedding_context = contains_any(text, WEDDING_CONTEXT_TERMS)
    has_preference = contains_any(text, PREFERENCE_MARKERS)
    sensational_hits = [
        term for term in SENSATIONAL_NOISE_TERMS if term in text
    ]
    unrelated_noise_hits = [
        term for term in UNRELATED_NOISE_TERMS if term in text
    ]
    sensational_title_hits = [
        term for term in SENSATIONAL_TITLE_MARKERS if term in title
    ]
    finance_interest = contains_any(text, FINANCE_INTEREST_TERMS)
    information_interest = contains_any(text, INFORMATION_INTEREST_MARKERS)
    relationship_discourse = contains_any(text, RELATIONSHIP_DISCOURSE_MARKERS)
    preparation_action = contains_any(text, PREPARATION_ACTION_MARKERS)
    has_price = bool(PRICE_PATTERN.search(text))
    personal_finance_question = has_price and contains_any(
        text, ("고민", "맞나", "어떻게", "분담", "지원", "모았", "부모님")
    )
    noise_hits = sensational_hits + unrelated_noise_hits + sensational_title_hits

    if sensational_hits or len(sensational_title_hits) >= 2:
        research_use = "제외"
        reject_reason = "선정적·자극적 표현 또는 성별 갈등 중심 콘텐츠"
    elif unrelated_noise_hits:
        research_use = "제외"
        reject_reason = "특정 서비스 홍보 또는 웨딩 준비와 무관한 결혼 일반 담론"
    elif source == "dcinside":
        has_preparation_context = contains_any(text, DC_PREPARATION_TERMS)
        finance_interest = finance_interest or (has_preparation_context and has_price)
        if issues and has_preparation_context:
            research_use = "핵심 이슈"
            reject_reason = None
        elif relationship_discourse and not (
            preparation_action or (finance_interest and personal_finance_question)
        ):
            research_use = "제외"
            reject_reason = "웨딩 준비보다 연애·결혼 일반 담론에 가까움"
        elif has_preparation_context and finance_interest:
            research_use = "웨딩 비용·자금"
            reject_reason = None
        elif has_preparation_context and (information_interest or has_preference):
            research_use = "웨딩 준비 사례"
            reject_reason = None
        else:
            research_use = "제외"
            reject_reason = "구체적인 웨딩 준비 질문·비교·경험을 확인하기 어려움"
    elif source == "kgwed" and has_wedding_context and issues:
        research_use = "핵심 이슈"
        reject_reason = None
    elif source == "kgwed" and has_wedding_context and (services or has_preference):
        research_use = "업체 선택 후기"
        reject_reason = None
    else:
        research_use = "제외"
        reject_reason = "웨딩 준비 서비스나 이슈를 확인하기 어려움"

    return {
        "title": title,
        "body_clean": body,
        "service_categories": services,
        "issue_labels": issues,
        "research_use": research_use,
        "price_mentions": sorted(set(PRICE_PATTERN.findall(text))),
        "evidence_sentences": extract_evidence_sentences(text),
        "keep": research_use != "제외",
        "reject_reason": reject_reason,
        "noise_hits": noise_hits,
        "sensational_hits": sensational_hits,
        "finance_interest": finance_interest,
        "information_interest": information_interest,
        "relationship_discourse": relationship_discourse,
        "preparation_action": preparation_action,
    }
