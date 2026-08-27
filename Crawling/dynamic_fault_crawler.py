"""네이버에서 검색하고 한국어 제조 문서만 수집하는 동적 크롤러."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class CrawlResult:
    """UI에 표시할 웹 문서 한 건."""

    title: str
    url: str
    content: str


class DynamicFaultCrawler:
    """Selenium으로 렌더링하고 BeautifulSoup으로 관련 한국어 문서를 선별한다."""

    SEARCH_URL = (
        "https://search.naver.com/search.naver"
        "?where=web&query={query}&start={start}"
    )
    RESULTS_PER_SEARCH_PAGE = 10
    MAX_SEARCH_PAGES = 20
    RESULT_CONTAINER_SELECTOR = "#main_pack"
    RESULT_SELECTOR = "#main_pack a[href]"
    BLOCKED_RESULT_HOSTS = {
        "search.naver.com",
        "m.search.naver.com",
        "help.naver.com",
        "keep.naver.com",
    }

    TITLE_MANUFACTURING_TERMS = (
        "사출성형",
        "사출 성형",
        "injection molding",
        "injection moulding",
    )
    BODY_MANUFACTURING_TERMS = (
        "사출", "성형", "금형", "수지", "제조", "공정", "설비", "품질",
        "불량", "플라스틱", "injection", "molding", "moulding", "mold",
        "mould", "resin", "manufacturing", "process", "defect", "plastic",
    )
    REASON_TERMS = {
        "가스": ("가스", "기포", "은줄", "gas", "bubble", "silver streak"),
        "미성형": (
            "미성형", "충전 부족", "short shot", "short-shot", "incomplete filling",
        ),
        "초기허용불량": (
            "초기허용불량", "초기 불량", "초기품 불량", "startup defect",
            "start-up defect", "startup reject",
        ),
    }
    MIN_TITLE_HANGUL = 1
    MIN_BODY_HANGUL = 20
    MIN_BODY_HANGUL_RATIO = 0.25

    def __init__(self, headless: bool = True, timeout: int = 12,
                 max_content_chars: int = 6000) -> None:
        self.headless = headless
        self.timeout = timeout
        self.max_content_chars = max_content_chars

    def crawl(
        self,
        query: str,
        max_pages: int = 5,
        progress: Callable[[str], None] | None = None,
        required_reason: str | None = None,
    ) -> list[CrawlResult]:
        """요청 개수만큼 필터를 통과한 한국어 문서를 반환한다.

        최대 검색 범위 안에서 개수를 채우지 못하면 부분 결과를 반환하지 않고
        RuntimeError를 발생시킨다.
        """
        query = self.normalize_text(query)
        if not query:
            raise ValueError("검색어를 입력하세요.")
        if not 1 <= max_pages <= 10:
            raise ValueError("수집 문서 수는 1~10 사이여야 합니다.")

        reason = self.normalize_text(required_reason) or self.infer_reason(query)
        if not reason:
            raise ValueError(
                "선택한 고장 원인을 확인할 수 없습니다. "
                "검색어에 가스, 미성형 또는 초기허용불량을 포함하세요."
            )

        webdriver, by, wait, expected_conditions = self._import_selenium()
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--lang=ko-KR")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1440,1000")

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(self.timeout)
        results: list[CrawlResult] = []
        examined_count = 0
        seen_urls: set[str] = set()
        consecutive_empty_pages = 0
        try:
            for search_page in range(1, self.MAX_SEARCH_PAGES + 1):
                start = (search_page - 1) * self.RESULTS_PER_SEARCH_PAGE + 1
                search_url = self.build_search_url(query, start)
                self._notify(
                    progress,
                    f"네이버 검색 결과 {search_page}페이지 확인 중 "
                    f"(수집 {len(results)}/{max_pages}건)",
                )
                driver.get(search_url)
                wait(driver, self.timeout).until(
                    expected_conditions.presence_of_element_located(
                        (by.CSS_SELECTOR, self.RESULT_CONTAINER_SELECTOR)
                    )
                )

                page_candidates = [
                    candidate
                    for candidate in self._unique_links(
                        self.extract_search_links(driver.page_source)
                    )
                    if candidate[0] not in seen_urls
                ]
                if not page_candidates:
                    consecutive_empty_pages += 1
                    if consecutive_empty_pages >= 2:
                        break
                    continue
                consecutive_empty_pages = 0

                for url, search_title in page_candidates:
                    seen_urls.add(url)
                    examined_count += 1
                    self._notify(
                        progress,
                        f"한국어·관련성 확인 중 "
                        f"(후보 {examined_count}, 수집 {len(results)}/{max_pages}): "
                        f"{search_title}",
                    )
                    try:
                        driver.get(url)
                        wait(driver, self.timeout).until(
                            expected_conditions.presence_of_element_located(
                                (by.TAG_NAME, "body")
                            )
                        )
                        title, content = self.parse_document(
                            driver.page_source,
                            fallback_title=driver.title or search_title,
                        )
                        relevant, failures = self.evaluate_relevance(
                            title=title or search_title,
                            content=content,
                            reason=reason,
                        )
                        if not relevant:
                            self._notify(
                                progress,
                                f"수집 제외 ({', '.join(failures)}): "
                                f"{title or search_title}",
                            )
                            continue

                        results.append(CrawlResult(
                            title=title or search_title or url,
                            url=driver.current_url,
                            content=content[:self.max_content_chars],
                        ))
                        self._notify(
                            progress,
                            f"문서 수집 완료 ({len(results)}/{max_pages}): "
                            f"{title or search_title}",
                        )
                        if len(results) == max_pages:
                            break
                    except Exception as error:
                        self._notify(progress, f"문서 건너뜀: {type(error).__name__}")

                if len(results) == max_pages:
                    break
        finally:
            driver.quit()

        if len(results) != max_pages:
            raise RuntimeError(
                f"요청한 문서 {max_pages}건 중 {len(results)}건만 조건을 "
                f"통과했습니다. 네이버 검색 결과 최대 {self.MAX_SEARCH_PAGES}페이지와 "
                f"후보 {examined_count}건을 확인했지만 관련 한국어 제조 문서가 "
                "부족합니다. 검색어 또는 관련성 필터를 조정하세요."
            )
        return results

    @classmethod
    def build_search_url(cls, query: str, start: int = 1) -> str:
        """검색 시작 위치를 포함한 네이버 웹 검색 URL을 만든다."""
        if start < 1:
            raise ValueError("검색 시작 위치는 1 이상이어야 합니다.")
        return cls.SEARCH_URL.format(query=quote_plus(query), start=start)

    @staticmethod
    def normalize_text(value: str | None) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    @classmethod
    def infer_reason(cls, query: str) -> str:
        normalized_query = cls.normalize_text(query).casefold()
        for reason in cls.REASON_TERMS:
            if reason.casefold() in normalized_query:
                return reason
        return ""

    @classmethod
    def evaluate_relevance(
        cls, title: str, content: str, reason: str
    ) -> tuple[bool, list[str]]:
        """한국어·제목·고장 원인·제조 본문의 네 필터를 평가한다."""
        title_text = cls.normalize_text(title).casefold()
        body_text = cls.normalize_text(content).casefold()
        combined_text = f"{title_text} {body_text}"

        korean_matches = cls.is_korean_document(title_text, body_text)
        title_matches = any(
            term.casefold() in title_text for term in cls.TITLE_MANUFACTURING_TERMS
        )
        reason_terms = cls.REASON_TERMS.get(reason, (reason,))
        reason_matches = any(term.casefold() in combined_text for term in reason_terms)
        manufacturing_hits = sum(
            term.casefold() in body_text for term in cls.BODY_MANUFACTURING_TERMS
        )
        body_matches = manufacturing_hits >= 2

        failures: list[str] = []
        if not korean_matches:
            failures.append("한국어 문서 아님")
        if not title_matches:
            failures.append("제목에 사출성형 없음")
        if not reason_matches:
            failures.append(f"{reason} 내용 없음")
        if not body_matches:
            failures.append("제조업 본문 아님")
        return not failures, failures

    @classmethod
    def is_korean_document(cls, title: str, content: str) -> bool:
        """제목과 본문의 한글 문자 수·비율로 한국어 문서인지 판정한다."""
        title_hangul = len(re.findall(r"[가-힣]", title))
        body_hangul = len(re.findall(r"[가-힣]", content))
        body_letters = len(re.findall(r"[A-Za-z가-힣]", content))
        hangul_ratio = body_hangul / body_letters if body_letters else 0.0
        return (
            title_hangul >= cls.MIN_TITLE_HANGUL
            and body_hangul >= cls.MIN_BODY_HANGUL
            and hangul_ratio >= cls.MIN_BODY_HANGUL_RATIO
        )

    @classmethod
    def extract_search_links(cls, html: str) -> list[tuple[str | None, str]]:
        """네이버 결과 영역에서 실제 HTTP(S) 문서 링크만 추출한다."""
        soup = BeautifulSoup(html, "html.parser")
        links: list[tuple[str | None, str]] = []
        for tag in soup.select(cls.RESULT_SELECTOR):
            url = (tag.get("href") or "").strip()
            parsed = urlparse(url)
            host = parsed.netloc.casefold()
            if parsed.scheme not in {"http", "https"} or not host:
                continue
            if host in cls.BLOCKED_RESULT_HOSTS:
                continue
            title = tag.get_text(" ", strip=True)
            if not title:
                continue
            links.append((url, title))
        return links

    @classmethod
    def parse_document(cls, html: str, fallback_title: str = "") -> tuple[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.select(
            "script, style, noscript, template, svg, nav, footer, aside"
        ):
            tag.decompose()

        title_tag = soup.find("title")
        title = (
            cls.normalize_text(title_tag.get_text(" ", strip=True))
            if title_tag is not None
            else cls.normalize_text(fallback_title)
        )
        content_area = soup.find("article") or soup.find("main") or soup.find("body")
        content = (
            cls.normalize_text(content_area.get_text(" ", strip=True))
            if content_area is not None
            else ""
        )
        return title, content

    @classmethod
    def _unique_links(cls, links) -> list[tuple[str, str]]:
        unique: list[tuple[str, str]] = []
        seen: set[str] = set()
        for raw_url, raw_title in links:
            url = (raw_url or "").strip()
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or url in seen:
                continue
            seen.add(url)
            unique.append((url, cls.normalize_text(raw_title) or parsed.netloc))
        return unique

    @staticmethod
    def _notify(progress: Callable[[str], None] | None, message: str) -> None:
        if progress is not None:
            try:
                progress(message)
            except Exception:
                pass

    @staticmethod
    def _import_selenium():
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.support.ui import WebDriverWait
        except ImportError as error:
            raise RuntimeError(
                "동적 크롤링에 Selenium이 필요합니다. "
                "가상환경에서 'pip install -r requirements-crawler.txt'를 실행하세요."
            ) from error
        return webdriver, By, WebDriverWait, EC
