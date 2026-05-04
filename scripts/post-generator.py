#!/usr/bin/env python3
"""post-generator.py — 일일 블로그 포스트 자동 생성기

Claude Code CLI로 토픽 선정 + 콘텐츠 생성 → Blog API로 발행.
기존 포스트, RSS 피드를 참고하여 주제를 선정합니다.
"""

import json
import os
import sys
import re
import subprocess
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

# ── 설정 ──────────────────────────────────────────────
CLAUDE_CODE_PATH = "/home/ubuntu/.local/bin/claude"
CLAUDE_SETTINGS = "/home/ubuntu/.agent_forge_for_zai.json"
API_KEY_FILE = "/etc/auto-comment-worker/credentials/blog-api-key"
BASE_URL = "https://blog.fcoinfup.com/api"
WORK_DIR = "/var/www/auto-comment-worker"

# RSS 피드 소스 (기술 블로그 트렌드 참고용)
RSS_FEEDS = [
    "https://news.ycombinator.com/rss",
    "https://dev.to/feed",
]

LOG_FILE = "/var/log/auto-comment-worker/post-generator.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8") if Path(LOG_FILE).parent.exists() else logging.StreamHandler()
    ]
)
log = logging.getLogger("post-generator")


def load_api_key():
    path = Path(API_KEY_FILE)
    if not path.exists():
        log.error(f"API key file not found: {API_KEY_FILE}")
        sys.exit(1)
    return path.read_text().strip()


def api_get(endpoint, api_key):
    """Blog API GET 요청"""
    req = Request(
        f"{BASE_URL}{endpoint}",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"}
    )
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        log.error(f"API GET {endpoint} failed: {e}")
        return None


def api_post(endpoint, data, api_key):
    """Blog API POST 요청"""
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = Request(
        f"{BASE_URL}{endpoint}",
        data=body,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        log.error(f"API POST {endpoint} failed: {e}")
        return None


def fetch_rss_titles():
    """RSS 피드에서 최근 제목들 수집 (트렌드 참고용)"""
    titles = []
    for feed_url in RSS_FEEDS:
        try:
            req = Request(feed_url, headers={"User-Agent": "PostGenerator/1.0"})
            with urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="replace")
            # 간단한 XML 파싱 (의존성 최소화)
            for match in re.finditer(r"<title[^>]*>(.*?)</title>", content, re.DOTALL):
                title = match.group(1).strip()
                if title and len(title) > 5 and title not in ("Hacker News", "DEV Community"):
                    titles.append(title)
        except Exception as e:
            log.warning(f"RSS fetch failed ({feed_url}): {e}")
    return titles[:30]  # 최대 30개


def get_existing_topics(api_key):
    """기존 포스트 제목 목록 조회"""
    posts = api_get("/posts?language=ko", api_key)
    if not posts:
        return []
    # posts가 리스트인지 dict인지 확인
    if isinstance(posts, dict):
        posts = posts.get("posts", [])
    return [p.get("title", "") for p in posts if isinstance(p, dict)]


def generate_post_with_claude(existing_topics, rss_titles):
    """Claude Code CLI로 포스트 생성"""
    existing_str = "\n".join(f"- {t}" for t in existing_topics[-20:]) if existing_topics else "(아직 포스트 없음)"
    rss_str = "\n".join(f"- {t}" for t in rss_titles[:15]) if rss_titles else "(RSS 수집 실패)"

    prompt = f"""당신은 기술 블로그 작성자입니다. 아래 정보를 참고하여 새로운 블로그 포스트를 작성하세요.

## 기존 포스트 목록 (중복 방지)
{existing_str}

## 최근 기술 트렌드 (RSS 피드에서 수집)
{rss_str}

## 작성 규칙
1. 기존 포스트와 중복되지 않는 새로운 주제를 선택하세요
2. 실용적이고 구체적인 기술 콘텐츠를 작성하세요
3. 독자가 바로 적용할 수 있는 코드 예제를 포함하세요
4. 한국어로 작성하세요
5. 분량: 1500~3000자

## 출력 형식 (반드시 이 JSON 형식을 따라주세요)
```json
{{
    "title": "포스트 제목",
    "tags": ["tag1", "tag2", "tag3"],
    "categories": ["Development"],
    "content": "마크다운 본문 내용..."
}}
```

위 JSON 형식으로만 응답하세요. JSON 외의 다른 텍스트를 포함하지 마세요.
"""

    cmd = [
        CLAUDE_CODE_PATH,
        "--settings", CLAUDE_SETTINGS,
        "--print", prompt
    ]

    log.info("Invoking Claude Code CLI for post generation...")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=180,
            cwd=WORK_DIR
        )

        if result.returncode != 0:
            log.error(f"Claude Code failed (exit={result.returncode}): {result.stderr[:500]}")
            return None

        output = result.stdout.strip()
        log.info(f"Claude Code output length: {len(output)} chars")

        # JSON 추출 (코드블록 안에 있을 수 있음)
        json_match = re.search(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
        if json_match:
            output = json_match.group(1)
        else:
            # 코드블록 없이 바로 JSON인 경우
            json_match = re.search(r'\{[\s\S]*\}', output)
            if json_match:
                output = json_match.group(0)

        post_data = json.loads(output)

        # 필수 필드 검증
        if not all(k in post_data for k in ("title", "content")):
            log.error(f"Missing required fields in generated post: {list(post_data.keys())}")
            return None

        return post_data

    except subprocess.TimeoutExpired:
        log.error("Claude Code timed out (180s)")
        return None
    except json.JSONDecodeError as e:
        log.error(f"Failed to parse Claude output as JSON: {e}")
        log.debug(f"Raw output: {output[:500]}")
        return None
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        return None


def publish_post(post_data, api_key):
    """Blog API로 포스트 발행"""
    payload = {
        "title": post_data["title"],
        "content": post_data["content"],
        "tags": post_data.get("tags", ["ai", "development"]),
        "categories": post_data.get("categories", ["Development"]),
        "draft": False,
        "auto_push": True,
        "language": "ko"
    }

    log.info(f"Publishing: {payload['title']}")
    result = api_post("/posts", payload, api_key)

    if result and result.get("success"):
        log.info(f"Published successfully: {result.get('filename', 'unknown')}")
        return True
    else:
        log.error(f"Publish failed: {result}")
        return False


def main():
    log.info("=" * 50)
    log.info("Post Generator started")

    api_key = load_api_key()

    # 1. 기존 포스트 목록 조회
    log.info("Fetching existing topics...")
    existing_topics = get_existing_topics(api_key)
    log.info(f"Found {len(existing_topics)} existing posts")

    # 2. RSS 피드에서 트렌드 수집
    log.info("Fetching RSS trends...")
    rss_titles = fetch_rss_titles()
    log.info(f"Collected {len(rss_titles)} RSS titles")

    # 3. Claude Code로 포스트 생성
    post_data = generate_post_with_claude(existing_topics, rss_titles)
    if not post_data:
        log.error("Failed to generate post. Aborting.")
        sys.exit(1)

    # 4. Blog API로 발행
    success = publish_post(post_data, api_key)
    if not success:
        log.error("Failed to publish post. Aborting.")
        sys.exit(1)

    # 5. 자동 번역 트리거 (번역은 auto-translate 타이머가 처리)
    log.info("New post published. Auto-translate timer will handle translation.")
    log.info("Post Generator completed successfully")


if __name__ == "__main__":
    main()
