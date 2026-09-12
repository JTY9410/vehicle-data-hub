from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_LIMIT = 2000


def _default_http_get(url: str, headers: dict) -> dict:
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise RuntimeError(f"crawl API HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"crawl API 연결 실패: {exc.reason}") from exc


def _get_with_retry(get, url: str, headers: dict, *, retries: int = 5, sleep=time.sleep):
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return get(url, headers)
        except RuntimeError as exc:
            last = exc
            if "HTTP 429" not in str(exc) or attempt >= retries:
                raise
            sleep(min(30, 2**attempt))
    assert last is not None
    raise last


def iter_crawling_rows(
    *,
    base_url: str,
    api_key: str,
    limit: int = DEFAULT_LIMIT,
    http_get=None,
):
    """GET /api/crawling 을 id offset 커서로 모두 순회. 중복 id는 건너뛴다."""
    get = http_get or _default_http_get
    offset = 0
    seen_ids: set[int] = set()
    headers = {"x-api-key": api_key, "accept": "application/json"}
    while True:
        url = f"{base_url.rstrip('/')}/api/crawling?offset={offset}&limit={limit}"
        page = _get_with_retry(get, url, headers)
        datas = page.get("datas") or []
        if not datas:
            break
        yielded = 0
        max_id = offset
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
        if yielded == 0 or len(datas) < limit or max_id <= offset:
            break
        offset = max_id
