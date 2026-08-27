# Dynamic Fault Crawler 정리

## 파일 목적

`dynamic_fault_crawler.py`는 사출성형 제조 데이터에서 확인된 고장 원인을 이용해  
네이버에서 관련 기술 문서를 검색하고, 실제 웹페이지를 동적으로 렌더링한 뒤  
관련성이 높은 한국어 제조 문서만 선별하여 수집하는 크롤링 모듈이다.

현재 지원하는 고장 원인은 다음 3가지이다.

- 가스
- 미성형
- 초기허용불량

전체적인 처리 흐름은 다음과 같다.

```text
제조 데이터
    ↓
고장 원인 확인
    ↓
가스 / 미성형 / 초기허용불량
    ↓
검색어 생성
    ↓
DynamicFaultCrawler
    ↓
네이버 웹 검색
    ↓
검색 결과 링크 추출
    ↓
Selenium으로 실제 웹페이지 접속
    ↓
BeautifulSoup으로 HTML 파싱
    ↓
한국어 문서 여부 확인
    ↓
사출성형 관련성 확인
    ↓
고장 원인 관련성 확인
    ↓
관련 문서 수집
    ↓
CrawlResult
    ↓
Tkinter UI에서 표시
```

---

# CrawlResult 클래스

```python
@dataclass(frozen=True)
class CrawlResult:
    title: str
    url: str
    content: str
```

크롤링에 성공한 웹 문서 한 건을 저장하는 데이터 클래스이다.

## 저장 데이터

| 속성 | 역할 |
|---|---|
| `title` | 웹 문서 제목 |
| `url` | 실제 웹 문서 주소 |
| `content` | 웹페이지에서 추출한 본문 |

크롤러의 최종 결과는 여러 개의 `CrawlResult` 객체가 들어 있는 리스트 형태이다.

```text
[
    CrawlResult(...),
    CrawlResult(...),
    CrawlResult(...)
]
```

이 결과는 이후 Tkinter UI에서 문서 제목, URL, 본문을 표시하는 데 사용할 수 있다.

---

# DynamicFaultCrawler 클래스

```python
class DynamicFaultCrawler:
```

실제 동적 크롤링을 담당하는 핵심 클래스이다.

Selenium으로 웹페이지를 렌더링하고, BeautifulSoup으로 HTML을 분석한 뒤  
한국어·사출성형·고장원인 관련성을 검사하여 필요한 문서만 수집한다.

---

# 주요 설정값

## SEARCH_URL

```python
SEARCH_URL = (
    "https://search.naver.com/search.naver"
    "?where=web&query={query}&start={start}"
)
```

네이버 웹 검색 주소의 기본 형식이다.

검색어와 검색 시작 위치를 넣어 실제 검색 URL을 생성한다.

---

## 검색 페이지 설정

```python
RESULTS_PER_SEARCH_PAGE = 10
MAX_SEARCH_PAGES = 20
```

- 한 검색 페이지를 10개 결과 단위로 계산
- 최대 20페이지까지 탐색

---

## 검색 결과 영역

```python
RESULT_CONTAINER_SELECTOR = "#main_pack"
RESULT_SELECTOR = "#main_pack a[href]"
```

네이버 검색 결과 페이지에서 실제 링크들을 찾기 위한 CSS Selector이다.

---

## BLOCKED_RESULT_HOSTS

```python
BLOCKED_RESULT_HOSTS = {
    "search.naver.com",
    "m.search.naver.com",
    "help.naver.com",
    "keep.naver.com",
}
```

실제 기술문서가 아닌 네이버 내부 페이지 등이 결과에 포함되는 것을 막는다.

---

# 사출성형 관련 키워드

## TITLE_MANUFACTURING_TERMS

```python
TITLE_MANUFACTURING_TERMS = (
    "사출성형",
    "사출 성형",
    "injection molding",
    "injection moulding",
)
```

웹 문서 제목이 사출성형과 관련되어 있는지 판단할 때 사용한다.

---

## BODY_MANUFACTURING_TERMS

```text
사출
성형
금형
수지
제조
공정
설비
품질
불량
플라스틱
...
```

웹 문서 본문이 실제 제조·사출 공정에 관한 문서인지 판단하는 데 사용한다.

본문에 제조 관련 키워드가 일정 개수 이상 존재해야 관련 문서로 인정한다.

---

# 고장 원인 키워드

```python
REASON_TERMS
```

데이터의 고장 원인을 인터넷 검색 결과와 연결하기 위한 핵심 설정이다.

## 가스

```text
가스
기포
은줄
gas
bubble
silver streak
```

## 미성형

```text
미성형
충전 부족
short shot
short-shot
incomplete filling
```

## 초기허용불량

```text
초기허용불량
초기 불량
초기품 불량
startup defect
start-up defect
startup reject
```

예를 들어 고장 원인이 `미성형`으로 확인되더라도  
인터넷 문서에는 `Short Shot`, `충전 부족` 등의 다른 표현이 사용될 수 있기 때문에  
관련 단어를 함께 검색·검사할 수 있도록 정의되어 있다.

---

# `__init__()` - 크롤러 초기 설정

```python
def __init__(
    self,
    headless=True,
    timeout=12,
    max_content_chars=6000
)
```

크롤러 객체가 생성될 때 기본 실행환경을 설정한다.

## 주요 설정

### `headless`

Chrome 브라우저를 화면에 표시할지 결정한다.

```text
True
→ 브라우저 화면 없이 실행

False
→ 실제 Chrome 화면 표시
```

### `timeout`

웹페이지 로딩을 최대 몇 초 기다릴지 설정한다.

### `max_content_chars`

한 웹 문서에서 저장할 최대 본문 길이를 설정한다.

---

# `crawl()` - 전체 크롤링 실행

```python
def crawl(...)
```

이 클래스에서 가장 중요한 핵심 함수이다.

검색 → 페이지 이동 → 문서 분석 → 관련성 검사 → 결과 저장의 전체 과정을 관리한다.

## 주요 입력값

| 파라미터 | 역할 |
|---|---|
| `query` | 네이버에 입력할 검색어 |
| `max_pages` | 최종적으로 수집할 문서 개수 |
| `progress` | 진행 상태를 UI 등에 전달하는 함수 |
| `required_reason` | 반드시 포함되어야 할 고장 원인 |

## 동작 과정

```text
검색어 검사
    ↓
고장 원인 확인
    ↓
Selenium 실행
    ↓
네이버 검색
    ↓
검색 결과 링크 추출
    ↓
중복 URL 제거
    ↓
각 웹 문서 접속
    ↓
HTML 파싱
    ↓
관련성 검사
    ↓
조건을 통과하면 CrawlResult 생성
    ↓
요청한 개수까지 반복
```

수집 조건을 충족하는 문서가 부족하면 `RuntimeError`를 발생시킨다.

---

# `build_search_url()` - 네이버 검색 URL 생성

```python
build_search_url(query, start)
```

검색어와 검색 시작 위치를 이용하여 실제 네이버 검색 URL을 생성한다.

예:

```text
사출성형 미성형 원인
        ↓
URL Encoding
        ↓
네이버 검색 URL
```

검색어의 한글이나 공백 등은 `quote_plus()`를 이용해 URL에 사용할 수 있도록 변환한다.

---

# `normalize_text()` - 문자열 정리

```python
normalize_text(value)
```

문자열의 불필요한 공백과 줄바꿈을 정리한다.

예:

```text
"사출성형     미성형\n원인"

        ↓

"사출성형 미성형 원인"
```

검색어, 제목, 본문 등을 비교하기 전에 텍스트 형태를 통일하는 역할을 한다.

---

# `infer_reason()` - 검색어에서 고장 원인 판별

```python
infer_reason(query)
```

사용자가 입력한 검색어에 어떤 고장 원인이 포함되어 있는지 자동으로 확인한다.

예:

```text
"사출성형 미성형 원인 해결"

        ↓

미성형
```

현재 판별 가능한 값은 다음 3가지이다.

```text
가스
미성형
초기허용불량
```

---

# `evaluate_relevance()` - 문서 관련성 검사

```python
evaluate_relevance(title, content, reason)
```

크롤링한 웹 문서가 실제 프로젝트에 필요한 문서인지 판정한다.

총 4개의 필터를 사용한다.

```text
웹 문서
   ↓
① 한국어 문서인가?
   ↓
② 제목이 사출성형과 관련 있는가?
   ↓
③ 선택한 고장원인 내용이 있는가?
   ↓
④ 제조업 관련 본문인가?
   ↓
관련 문서로 채택
```

조건을 만족하지 못하면 제외 이유도 함께 반환한다.

예:

```text
한국어 문서 아님
제목에 사출성형 없음
미성형 내용 없음
제조업 본문 아님
```

---

# `is_korean_document()` - 한국어 문서 판별

```python
is_korean_document(title, content)
```

문서 제목과 본문에서 한글의 개수와 비율을 계산하여  
한국어 중심 문서인지 판단한다.

검사 항목은 다음과 같다.

```text
제목의 한글 문자 수
본문의 한글 문자 수
본문 전체 문자 중 한글 비율
```

기본 조건:

```text
제목 한글 1글자 이상
본문 한글 20글자 이상
본문 한글 비율 25% 이상
```

---

# `extract_search_links()` - 네이버 검색 결과 링크 추출

```python
extract_search_links(html)
```

네이버 검색 결과 HTML에서 실제 외부 웹문서 주소를 추출한다.

처리 과정:

```text
네이버 검색 HTML
    ↓
BeautifulSoup
    ↓
#main_pack a[href]
    ↓
HTTP / HTTPS 링크 확인
    ↓
네이버 내부 페이지 제거
    ↓
URL + 제목 반환
```

결과 형태:

```python
[
    (url, title),
    (url, title),
    ...
]
```

---

# `parse_document()` - 웹 문서 제목과 본문 추출

```python
parse_document(html, fallback_title)
```

실제 웹페이지 HTML에서 분석에 필요한 제목과 본문만 추출한다.

먼저 다음 요소들을 제거한다.

```text
script
style
noscript
template
svg
nav
footer
aside
```

즉 JavaScript 코드, CSS, 메뉴, 푸터 등  
분석에 불필요한 HTML 요소를 제거한다.

본문은 다음 순서로 찾는다.

```text
article
   ↓ 없으면
main
   ↓ 없으면
body
```

최종적으로 다음 값을 반환한다.

```python
(title, content)
```

---

# `_unique_links()` - 검색 URL 중복 제거

```python
_unique_links(links)
```

같은 웹페이지가 검색 결과에 여러 번 등장하는 경우 중복을 제거한다.

또한 정상적인 HTTP/HTTPS 웹주소인지 검사한다.

```text
검색 링크들
    ↓
잘못된 URL 제거
    ↓
중복 URL 제거
    ↓
고유한 URL 목록 반환
```

---

# `_notify()` - 진행 상태 전달

```python
_notify(progress, message)
```

현재 크롤링 진행 상황을 외부 함수에 전달한다.

예:

```text
네이버 검색 결과 1페이지 확인 중
한국어·관련성 확인 중
문서 수집 완료
문서 수집 제외
```

Tkinter와 연결하면 다음과 같은 상태 표시 기능을 만들 수 있다.

```text
[현재 상태]

미성형 관련 문서 검색 중...
후보 15개 확인
관련 문서 3/5건 수집 완료
```

---

# `_import_selenium()` - Selenium 동적 로딩

```python
_import_selenium()
```

동적 크롤링에 필요한 Selenium 라이브러리를 불러온다.

사용 모듈:

```text
webdriver
By
WebDriverWait
expected_conditions
```

Selenium이 설치되어 있지 않으면 오류 메시지를 발생시킨다.

---

#  클래스 내부 함수 구조

```text
DynamicFaultCrawler
│
├── __init__()
│   └── 크롤러 환경 설정
│
├── crawl()
│   └── 전체 크롤링 프로세스 관리
│
├── build_search_url()
│   └── 네이버 검색 URL 생성
│
├── normalize_text()
│   └── 텍스트 공백/형태 정리
│
├── infer_reason()
│   └── 검색어에서 고장 원인 판별
│
├── evaluate_relevance()
│   └── 웹문서 관련성 검사
│
├── is_korean_document()
│   └── 한국어 문서 판별
│
├── extract_search_links()
│   └── 네이버 검색결과 URL 추출
│
├── parse_document()
│   └── 웹문서 제목/본문 추출
│
├── _unique_links()
│   └── URL 중복 제거
│
├── _notify()
│   └── 크롤링 진행상태 전달
│
└── _import_selenium()
    └── Selenium 라이브러리 로딩
```

---


