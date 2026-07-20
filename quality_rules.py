import html
import re


SERVICE_KEYWORDS = {
    "wedding_hall": [
        "웨딩홀", "예식장", "대관료", "식대",
        "보증인원", "꽃장식", "홀투어"
    ],
    "studio": [
        "웨딩촬영", "스튜디오", "본식스냅",
        "원본사진", "앨범", "사진 셀렉"
    ],
    "dress": [
        "드레스", "드레스샵", "드레스투어",
        "드투", "피팅", "가봉", "헬퍼비"
    ],
    "makeup": [
        "메이크업", "헤어메이크업",
        "얼리스타트", "출장비"
    ],
    "planner": [
        "웨딩플래너", "동행플래너", "비동행플래너",
        "플래너 상담", "플래너 추천"
    ],
    "package": [
        "스드메", "웨딩패키지", "웨딩박람회",
        "제휴업체", "결직웨딩"
    ],
    "wedding_goods": [
        "예물", "예복", "혼주한복", "신랑신부 한복"
    ],
}


ISSUE_KEYWORDS = {
    "unexpected_extra_cost": [
        "추가금", "추가 비용", "별도 비용",
        "원본비", "헬퍼비", "피팅비",
        "업그레이드 비용", "부가세 별도"
    ],
    "price_comparison": [
        "견적", "가격 비교", "같은 조건",
        "가격이 다르", "견적이 다르",
        "정찰제", "총액", "최종 비용"
    ],
    "contract_refund": [
        "계약금", "예약금", "홀딩비",
        "환불", "취소", "위약금", "약관"
    ],
    "affiliate_recommendation": [
        "제휴", "연계", "수수료",
        "고가라인", "강매", "당일 계약"
    ],
    "planner_workflow": [
        "일정 체크", "일정 관리", "예약",
        "카카오톡 안내", "업체 추천",
        "스타일 분석", "동행", "챙겨주"
    ],
    "service_quality": [
        "불친절", "친절", "지연", "누락",
        "실수", "재촬영", "보정", "결과물",
        "만족", "실망"
    ],
    "decision_overload": [
        "선택할 게", "알아보기 힘들",
        "비교하기 어렵", "정보가 없",
        "막막", "정신이 없", "시간이 부족"
    ],
}


NOISE_TERMS = [
    "씨를", "번식성공", "번식", "수컷",
    "한남", "한녀", "노괴", "퐁퐁남",
    "설거지론", "도태남", "처녀",
    "가임력", "섹스 가능한", "결혼정책",
    "출산율", "전세계약", "부동산계약",
    "내집스캔", "신혼집 전세"
]


DIRECT_EXPERIENCE_MARKERS = [
    "계약했", "상담받", "견적받",
    "결제했", "환불받", "취소했",
    "방문했", "촬영했", "투어했",
    "추가로 냈", "직접 알아봤",
    "제가 진행", "저희가 진행"
]


REPOST_MARKERS = [
    "펌)", "퍼옴", "유튜브",
    "youtu.be", "youtube.com",
    "기사 링크"
]


PREFERENCE_MARKERS = [
    "선택했", "추천", "마음에 들",
    "스타일", "분위기", "친절",
    "만족", "잘 어울"
]


PRICE_PATTERN = re.compile(
    r"\d{1,3}(?:,\d{3})+\s*원|"
    r"\d+(?:\.\d+)?\s*만원|"
    r"\d+\s*천원"
)


def normalize_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def match_groups(text: str, groups: dict[str, list[str]]) -> list[str]:
    return [
        group
        for group, keywords in groups.items()
        if any(keyword in text for keyword in keywords)
    ]


def is_candidate_title(title: str) -> bool:
    text = normalize_text(title)

    if any(term in text for term in NOISE_TERMS):
        return False

    services = match_groups(text, SERVICE_KEYWORDS)
    issues = match_groups(text, ISSUE_KEYWORDS)
    context_terms = [
        "웨딩", "결혼", "예식", "예식장", "스드메",
        "플래너", "업체", "신혼", "혼수", "촬영",
        "드레스", "메이크업", "앨범", "사진", "박람회"
    ]
    has_context = any(term in text for term in context_terms)

    # 디시는 제목만으로 서비스/이슈가 완전히 드러나지 않는 경우도 있으므로
    # 웨딩 맥락과 이슈가 함께 있으면 후보로 판단한다.
    return bool((services and issues) or (issues and has_context) or (services and has_context))


def extract_evidence_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?。])\s+|\n+", text)
    issue_terms = [
        keyword
        for keywords in ISSUE_KEYWORDS.values()
        for keyword in keywords
    ]

    evidence = []
    for sentence in sentences:
        sentence = sentence.strip()

        if len(sentence) < 10:
            continue

        if (
            any(term in sentence for term in issue_terms)
            or PRICE_PATTERN.search(sentence)
        ):
            evidence.append(sentence[:400])

    return evidence[:5]


def analyze_post(
    title: str,
    body: str,
    source: str,
) -> dict:
    title = normalize_text(title)
    body = normalize_text(body)
    text = f"{title} {body}"

    services = match_groups(text, SERVICE_KEYWORDS)
    issues = match_groups(text, ISSUE_KEYWORDS)
    noise_hits = [
        term for term in NOISE_TERMS
        if term in text
    ]

    direct_experience = any(
        marker in text
        for marker in DIRECT_EXPERIENCE_MARKERS
    )

    is_repost = any(
        marker.lower() in text.lower()
        for marker in REPOST_MARKERS
    )

    has_preference = any(
        marker in text
        for marker in PREFERENCE_MARKERS
    )

    if noise_hits:
        research_use = "exclude"
        reject_reason = "off_scope_social_discourse"

    elif services and issues:
        if issues == ["planner_workflow"]:
            research_use = "planner_workflow"
        else:
            research_use = "core_problem"
        reject_reason = None

    elif (
        source == "kgwed"
        and services
        and has_preference
    ):
        research_use = "vendor_preference"
        reject_reason = None

    else:
        research_use = "exclude"
        reject_reason = "no_research_issue"

    if research_use == "exclude":
        analysis_tier = "X"
    elif direct_experience:
        analysis_tier = "A"
    elif is_repost:
        analysis_tier = "B"
    else:
        analysis_tier = "C"

    return {
        "title": title,
        "body_clean": body,
        "service_categories": services,
        "issue_labels": issues,
        "research_use": research_use,
        "analysis_tier": analysis_tier,
        "direct_experience": direct_experience,
        "is_repost": is_repost,
        "price_mentions": sorted(set(
            PRICE_PATTERN.findall(text)
        )),
        "evidence_sentences": extract_evidence_sentences(text),
        "keep": research_use != "exclude",
        "reject_reason": reject_reason,
        "noise_hits": noise_hits,
    }