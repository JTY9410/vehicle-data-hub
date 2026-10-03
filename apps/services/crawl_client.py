from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_LIMIT = 2000
DEFAULT_429_WAIT = 60
MAX_429_WAIT = 120
MAX_CONSECUTIVE_SKIPS = 20


class CrawlHttpError(RuntimeError):
    def __init__(self, code: int, body: str, retry_after: float | None = None):
        super().__init__(f"crawl API HTTP {code}: {body}")
        self.code = code
        self.body = body
        self.retry_after = retry_after


def parse_retry_after(headers) -> float | None:
    if not headers:
        return None
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if raw is None:
        return None
    try:
        return max(1.0, float(str(raw).strip()))
    except ValueError:
        return None


def retry_wait_seconds(exc: BaseException, *, attempt: int = 0) -> float:
    header = getattr(exc, "retry_after", None)
    if header is not None:
        return max(1.0, float(header))
    return min(MAX_429_WAIT, DEFAULT_429_WAIT * (attempt + 1))


def _default_http_get(url: str, headers: dict) -> dict:
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise CrawlHttpError(exc.code, body, parse_retry_after(exc.headers)) from exc
    except URLError as exc:
        raise RuntimeError(f"crawl API 연결 실패: {exc.reason}") from exc


def _transient_http(exc: BaseException) -> bool:
    msg = str(exc)
    if any(code in msg for code in ("HTTP 502", "HTTP 503")):
        return True
    if "연결 실패" in msg or "name resolution" in msg:
        return True
    return "HTTP 429" in msg and getattr(exc, "retry_after", None) is not None


def _get_with_retry(get, url: str, headers: dict, *, retries: int = 2, sleep=time.sleep):
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return get(url, headers)
        except RuntimeError as exc:
            last = exc
            if not _transient_http(exc) or attempt >= retries:
                raise
            header = getattr(exc, "retry_after", None)
            wait = min(60.0, max(1.0, float(header))) if header is not None else 3.0
            sleep(wait)
    assert last is not None
    raise last


def iter_crawling_rows(
    *,
    base_url: str,
    api_key: str,
    limit: int = DEFAULT_LIMIT,
    http_get=None,
    page_delay: float = 0.0,
    start_offset: int = 0,
    start_limit: int | None = None,
    sleep=time.sleep,
    on_limit=None,
    on_skip=None,
):
    """GET /api/crawling 을 id offset 커서로 모두 순회. 중복 id는 건너뛴다.

    offset은 "이 id부터"(포함)라서 다음 페이지는 마지막 id + 1부터 요청한다.
    크롤 서버가 특정 행 때문에 500을 내면 페이지를 줄여 좁히고, 1건도 실패하면 그 id를 건너뛴다.
    """
    get = http_get or _default_http_get
    offset = max(0, int(start_offset))
    page_limit = max(1, min(limit, int(start_limit or limit)))
    skips = 0
    seen_ids: set[int] = set()
    headers = {"x-api-key": api_key, "accept": "application/json"}
    while True:
        url = f"{base_url.rstrip('/')}/api/crawling?offset={offset}&limit={page_limit}"
        try:
            page = _get_with_retry(get, url, headers, sleep=sleep)
        except CrawlHttpError as exc:
            if exc.code != 500:
                raise
            if page_limit > 1:
                page_limit = max(1, page_limit // 4)
                if on_limit:
                    on_limit(page_limit)
                continue
            skips += 1
            if skips > MAX_CONSECUTIVE_SKIPS:
                raise
            if on_skip:
                on_skip(offset)
            offset += 1
            continue
        skips = 0
        datas = page.get("datas") or []
        if not datas:
            break
        yielded = 0
        max_id = offset - 1
        for item in datas:
            raw_id = item.get("id")
            if raw_id is not None:
                item_id = int(raw_id)
                max_id = max(max_id, item_id)
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
            yield item
            yielded += 1
        if yielded == 0 or len(datas) < page_limit or max_id < offset:
            break
        offset = max_id + 1
        if page_limit < limit:
            page_limit = min(limit, page_limit * 2)
            if on_limit:
                on_limit(page_limit)
        if page_delay:
            sleep(page_delay)
