#!/usr/bin/env python3
"""blog-agent.py — 통합 블로그 에이전트 프레임워크 설계

현재 3개 독립 프로세스를 1개 통합 에이전트로 재설계.
Claude Code CLI 의존 제거, 직접 LLM API 호출.

아키텍처:
  1개 프로세스 = Flask (webhook) + Scheduler (timer) + LLM Client (직접 API)
"""

import json
import difflib
import re
import hmac
import hashlib
import logging
import threading
import time
import html
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from urllib.request import Request, urlopen

from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import Schema, fields, validate, ValidationError, EXCLUDE

# ═══════════════════════════════════════════════════════════════
# 1. 설정 (Configuration)
# ═══════════════════════════════════════════════════════════════

@dataclass
class AgentConfig:
    """에이전트 전체 설정 — 환경변수 또는 설정 파일에서 로드"""
    # LLM
    llm_base_url: str = "https://api.z.ai/api/anthropic"
    llm_api_key: str = ""
    llm_model: str = "glm-4.7"
    llm_timeout: int = 120

    # Blog API
    blog_api_url: str = "https://blog.fcoinfup.com/api"
    blog_api_key: str = ""

    # GitHub
    github_token: str = ""
    webhook_secret: str = ""
    repo_owner: str = "yarang"
    repo_name: str = "blogs"
    blog_owners: list = field(default_factory=lambda: ["yarang"])

    # Server
    port: int = 8081
    host: str = "0.0.0.0"

    # Scheduler
    translate_interval_hours: int = 6
    post_generate_hour: int = 9  # KST

    # Paths
    audit_log: str = "/var/log/auto-comment-worker/audit.log"
    credential_dir: str = "/etc/auto-comment-worker"

    @classmethod
    def from_credentials(cls):
        """파일 기반 인증 정보 로드"""
        config = cls()
        cred_dir = Path(config.credential_dir)

        token_file = cred_dir / "github-token"
        if token_file.exists():
            config.github_token = token_file.read_text().strip()

        secret_file = cred_dir / "credentials" / "webhook-secret"
        if secret_file.exists():
            config.webhook_secret = secret_file.read_text().strip()

        api_key_file = cred_dir / "credentials" / "blog-api-key"
        if api_key_file.exists():
            config.blog_api_key = api_key_file.read_text().strip()

        # ZAI 설정에서 LLM API 키 로드
        zai_file = Path.home() / ".agent_forge_for_zai.json"
        if zai_file.exists():
            zai = json.loads(zai_file.read_text())
            env = zai.get("env", {})
            config.llm_api_key = env.get("ANTHROPIC_AUTH_TOKEN", "")
            config.llm_base_url = env.get("ANTHROPIC_BASE_URL", config.llm_base_url)
            config.llm_model = env.get("ANTHROPIC_DEFAULT_SONNET_MODEL", config.llm_model)

        return config


# ═══════════════════════════════════════════════════════════════
# 2. LLM 클라이언트 (Claude Code CLI 대체)
# ═══════════════════════════════════════════════════════════════

class LLMClient:
    """직접 Anthropic Messages API 호출.

    Claude Code CLI 대비:
    - 시작 시간: 9.7초 → 2.3초 (4.2배 빠름)
    - 디스크: 688MB → 0MB
    - system/user 메시지 분리 가능
    - temperature, max_tokens 세밀 제어
    """

    def __init__(self, config: AgentConfig):
        self.base_url = config.llm_base_url
        self.api_key = config.llm_api_key
        self.model = config.llm_model
        self.timeout = config.llm_timeout
        self.log = logging.getLogger("llm")

    def chat(
        self,
        user_prompt: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> Optional[str]:
        """LLM API 호출 — 단일 턴 완성"""
        messages = [{"role": "user", "content": user_prompt}]

        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system_prompt:
            body["system"] = system_prompt

        data = json.dumps(body).encode("utf-8")
        req = Request(
            f"{self.base_url}/v1/messages",
            data=data,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )

        try:
            with urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read())
                content = result.get("content", [])
                texts = [b["text"] for b in content if b.get("type") == "text"]
                return "\n".join(texts)
        except Exception as e:
            self.log.error(f"LLM call failed: {e}")
            return None


# ═══════════════════════════════════════════════════════════════
# 3. 태스크 모듈 (각 에이전트 기능)
# ═══════════════════════════════════════════════════════════════

class CommentHandler:
    """댓글 AI 응답 — 기존 auto-comment-worker.py 핵심 로직"""

    SYSTEM_PROMPT = (
        "당신은 기술 블로그의 AI 어시스턴트입니다. "
        "독자의 댓글에 전문적이면서 친절하게 응답합니다. "
        "200자 이내로 간결하게 답변하세요. "
        "필요하면 추가 정보나 관련 키워드를 제시하세요."
    )

    AI_MARKERS = [
        "🤖 AI 어시스턴트", "AI 어시스턴트", "AgentForge",
        "Claude Code로 자동 생성", "자동 생성되었습니다",
    ]

    def __init__(self, llm: LLMClient, config: AgentConfig):
        self.llm = llm
        self.config = config
        self.log = logging.getLogger("comment")

    def is_ai_comment(self, body: str) -> bool:
        body_lower = body.lower()
        return any(m.lower() in body_lower for m in self.AI_MARKERS)

    def is_owner(self, username: str) -> bool:
        return username in self.config.blog_owners

    def generate_reply(self, context: str, comment: str) -> str:
        reply = self.llm.chat(
            user_prompt=f"## 블로그 포스트 문맥\n{context[:2000]}\n\n## 독자 댓글\n{comment}",
            system_prompt=self.SYSTEM_PROMPT,
            max_tokens=500,
            temperature=0.7,
        )
        return reply or "의견 감사합니다! 기술적인 부분에 대해 더 논의해보면 좋을 것 같습니다."

    def format_reply(self, reply: str) -> str:
        return (
            f"---\n**🤖 AI 어시스턴트**\n\n{reply}\n\n"
            f"*이 댓글은 AgentForge로 자동 생성되었습니다.*\n---"
        )

    def post_to_github(self, discussion_id: str, body: str) -> bool:
        query = """
        mutation($discussionId: ID!, $body: String!) {
            addDiscussionComment(input: {discussionId: $discussionId, body: $body}) {
                comment { id }
            }
        }
        """
        data = json.dumps({
            "query": query,
            "variables": {"discussionId": discussion_id, "body": body}
        }).encode()
        req = Request("https://api.github.com/graphql", data=data, headers={
            "Authorization": f"Bearer {self.config.github_token}",
            "Content-Type": "application/json",
        })
        try:
            with urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
                return "errors" not in result
        except Exception as e:
            self.log.error(f"GitHub post failed: {e}")
            return False


class BlogAPIClient:
    """Blog API 공용 클라이언트"""

    def __init__(self, config: AgentConfig):
        self.base_url = config.blog_api_url
        self.api_key = config.blog_api_key
        self.log = logging.getLogger("blogapi")

    def get(self, endpoint, timeout=30):
        return self._call(endpoint, "GET", timeout=timeout)

    def post(self, endpoint, data=None, timeout=600):
        return self._call(endpoint, "POST", data=data, timeout=timeout)

    def _call(self, endpoint, method="GET", data=None, timeout=30):
        url = f"{self.base_url}{endpoint}"
        body = json.dumps(data, ensure_ascii=False).encode() if data else None
        req = Request(url, data=body, method=method, headers={
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        })
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as e:
            self.log.error(f"API {method} {endpoint}: {e}")
            return None


class TranslateHandler:
    """자동 번역 — Blog API /translate/sync 호출"""

    def __init__(self, api: BlogAPIClient):
        self.api = api
        self.log = logging.getLogger("translate")

    def check_and_sync(self) -> dict:
        status = self.api.get("/translate/status")
        if not status:
            return {"error": "status check failed"}

        count = status.get("needs_translation_count", 0)
        if count == 0:
            self.log.info("All posts translated")
            return {"translated": 0, "status": "up_to_date"}

        self.log.info(f"Found {count} untranslated posts, syncing...")
        result = self.api.post("/translate/sync")
        if result:
            self.log.info(f"Translation sync: {result.get('summary', {})}")
            return result
        return {"error": "sync failed"}


class PostGenerator:
    """포스트 자동 생성 — LLM 직접 호출 + Blog API 발행"""

    SYSTEM_PROMPT = (
        "당신은 기술 블로그 작성자입니다. "
        "실용적이고 구체적인 기술 콘텐츠를 작성합니다. "
        "독자가 바로 적용할 수 있는 코드 예제를 포함하세요. "
        "한국어로 작성하고 1500~3000자 분량으로 작성합니다. "
        "반드시 JSON 형식으로만 응답하세요."
    )

    RSS_FEEDS = [
        "https://news.ycombinator.com/rss",
        "https://dev.to/feed",
    ]

    def __init__(self, llm: LLMClient, api: BlogAPIClient):
        self.llm = llm
        self.api = api
        self.log = logging.getLogger("postgen")

    def generate_and_publish(self) -> bool:
        existing = self._get_existing_topics()
        rss = self._fetch_rss_titles()

        post_data = self._generate_content(existing, rss)
        if not post_data:
            self.log.error("Content generation failed")
            return False

        # 프로그래매틱 중복 검사
        is_dup, similar_to = self._is_duplicate_title(
            post_data.get("title", ""), existing
        )
        if is_dup:
            self.log.warning(
                f"Skipping duplicate post: '{post_data['title']}' "
                f"(similar to: '{similar_to}')"
            )
            return False

        return self._publish(post_data)

    def _generate_content(self, existing, rss):
        existing_str = "\n".join(f"- {t}" for t in existing[-20:]) or "(없음)"
        rss_str = "\n".join(f"- {t}" for t in rss[:15]) or "(없음)"

        user_prompt = f"""기존 포스트 (중복 방지):
{existing_str}

최근 기술 트렌드 (RSS):
{rss_str}

위 정보를 참고하여 새 블로그 포스트를 JSON으로 작성하세요:
{{"title": "...", "tags": [...], "categories": ["Development"], "content": "마크다운 본문"}}"""

        output = self.llm.chat(
            user_prompt=user_prompt,
            system_prompt=self.SYSTEM_PROMPT,
            max_tokens=8192,
            temperature=0.8,
        )
        if not output:
            return None

        match = re.search(r"```json\s*\n(.*?)\n```", output, re.DOTALL)
        raw = match.group(1) if match else output
        match2 = re.search(r"\{[\s\S]*\}", raw)
        if match2:
            try:
                return json.loads(match2.group(0))
            except json.JSONDecodeError:
                pass
        return None

    def _get_existing_topics(self):
        result = self.api.get("/posts?language=ko&limit=100")
        if isinstance(result, dict):
            result = result.get("posts", [])
        return [p.get("title", "") for p in (result or []) if isinstance(p, dict)]

    def _fetch_rss_titles(self):
        titles = []
        for url in self.RSS_FEEDS:
            try:
                req = Request(url, headers={"User-Agent": "BlogAgent/1.0"})
                with urlopen(req, timeout=10) as resp:
                    content = resp.read().decode("utf-8", errors="replace")
                for m in re.finditer(r"<title[^>]*>(.*?)</title>", content, re.DOTALL):
                    t = m.group(1).strip()
                    if t and len(t) > 5:
                        titles.append(t)
            except Exception:
                pass
        return titles[:30]


    def _is_duplicate_title(self, new_title, existing_titles):
        """프로그래매틱 제목 유사도 검사.

        difflib.SequenceMatcher로 기존 제목과 비교.
        유사도 0.6 이상이면 중복으로 판정.
        """
        if not existing_titles:
            return False, ""
        new_lower = new_title.lower().strip()
        for existing in existing_titles:
            ex_lower = existing.lower().strip()
            ratio = difflib.SequenceMatcher(None, new_lower, ex_lower).ratio()
            if ratio >= 0.6:
                self.log.warning(
                    f"Duplicate detected: '{new_title}' ≈ '{existing}' "
                    f"(similarity={ratio:.2f})"
                )
                return True, existing
        return False, ""

    def _publish(self, post_data):
        payload = {
            "title": post_data["title"],
            "content": post_data["content"],
            "tags": post_data.get("tags", ["development"]),
            "categories": post_data.get("categories", ["Development"]),
            "draft": False,
            "auto_push": True,
            "language": "ko",
        }
        result = self.api.post("/posts", payload, timeout=60)
        if result and result.get("success"):
            self.log.info(f"Published: {result.get('filename')}")
            return True
        return False


# ═══════════════════════════════════════════════════════════════
# 4. 스케줄러 (systemd timer 대체)
# ═══════════════════════════════════════════════════════════════

class Scheduler:
    """내장 스케줄러 — systemd timer 2개를 프로세스 내부로 통합.

    장점:
    - systemd unit 파일 4개 제거 (service + timer × 2)
    - 에이전트 상태 공유 (LLM 클라이언트, 설정 단일화)
    - 스케줄 변경 시 재배포 불필요

    단점:
    - 프로세스 크래시 시 스케줄러도 중단
      → systemd Restart=always로 보완
    """

    def __init__(self):
        self._jobs: list[dict] = []
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.log = logging.getLogger("scheduler")

    def every(self, hours: int, task, name: str = ""):
        self._jobs.append({
            "name": name or task.__name__,
            "interval_sec": hours * 3600,
            "task": task,
            "last_run": 0,
        })
        return self

    def daily_at(self, hour: int, task, name: str = ""):
        self._jobs.append({
            "name": name or task.__name__,
            "daily_hour": hour,
            "task": task,
            "last_run_date": "",
        })
        return self

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.log.info(f"Scheduler started with {len(self._jobs)} jobs")

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            now = time.time()
            for job in self._jobs:
                try:
                    if "interval_sec" in job:
                        if now - job["last_run"] >= job["interval_sec"]:
                            self.log.info(f"Running: {job['name']}")
                            job["task"]()
                            job["last_run"] = now

                    elif "daily_hour" in job:
                        kst = timezone(timedelta(hours=9))
                        now_kst = datetime.now(kst)
                        today = now_kst.strftime("%Y-%m-%d")
                        if (now_kst.hour >= job["daily_hour"]
                                and job["last_run_date"] != today):
                            self.log.info(f"Running daily: {job['name']}")
                            job["task"]()
                            job["last_run_date"] = today

                except Exception as e:
                    self.log.error(f"Job {job['name']} failed: {e}")

            time.sleep(60)  # 1분마다 체크


# ═══════════════════════════════════════════════════════════════
# 5. 유틸리티
# ═══════════════════════════════════════════════════════════════

class AuditLogger:
    def __init__(self, path: str):
        self.path = Path(path)

    def log(self, event: str, details: dict):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "details": details,
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def sanitize_input(body: str) -> str:
    if not body:
        return body
    body = re.sub(r"<[^>]+>", "", body)
    body = html.escape(body)
    return body[:1000]


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not signature or not secret:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


class WebhookSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    action = fields.Str(required=True, validate=validate.Equal("created"))
    comment = fields.Dict(required=True)
    discussion = fields.Dict(required=True)


# ═══════════════════════════════════════════════════════════════
# 6. 메인 에이전트 (통합 진입점)
# ═══════════════════════════════════════════════════════════════

class BlogAgent:
    """통합 블로그 에이전트.

    1개 프로세스에서:
    - Flask 웹훅 서버 (댓글 수신)
    - 내장 스케줄러 (번역 + 포스트 생성)
    - 직접 LLM API 호출
    를 모두 처리합니다.
    """

    def __init__(self):
        self.config = AgentConfig.from_credentials()
        self.llm = LLMClient(self.config)
        self.audit = AuditLogger(self.config.audit_log)
        self.blog_api = BlogAPIClient(self.config)

        # 태스크 핸들러
        self.comment = CommentHandler(self.llm, self.config)
        self.translate = TranslateHandler(self.blog_api)
        self.postgen = PostGenerator(self.llm, self.blog_api)

        # 스케줄러
        self.scheduler = Scheduler()
        self.scheduler.every(
            self.config.translate_interval_hours,
            self.translate.check_and_sync,
            name="auto-translate",
        )
        self.scheduler.daily_at(
            self.config.post_generate_hour,
            self.postgen.generate_and_publish,
            name="post-generator",
        )

        # Flask
        self.app = Flask(__name__)
        self.limiter = Limiter(
            get_remote_address, app=self.app,
            default_limits=["60 per minute"],
        )
        self._start_time = time.time()
        self._register_routes()

    def _register_routes(self):
        @self.app.route("/webhook", methods=["POST"])
        @self.limiter.limit("10 per minute")
        def webhook():
            return self._handle_webhook()

        @self.app.route("/health", methods=["GET"])
        def health():
            return jsonify({
                "status": "healthy",
                "agent": "blog-agent",
                "uptime_sec": int(time.time() - self._start_time),
                "scheduler_jobs": len(self.scheduler._jobs),
            })

        @self.app.route("/status", methods=["GET"])
        def status():
            return jsonify({
                "scheduler": [
                    {"name": j["name"],
                     "last_run": j.get("last_run", j.get("last_run_date", "never"))}
                    for j in self.scheduler._jobs
                ],
            })

    def _handle_webhook(self):
        sig = request.headers.get("X-Hub-Signature-256")
        if not verify_signature(request.data, sig, self.config.webhook_secret):
            self.audit.log("SIGNATURE_INVALID", {"ip": request.remote_addr})
            return jsonify({"status": "unauthorized"}), 401

        # discussion_comment 이벤트만 처리, 나머지는 무시
        event_type = request.headers.get("X-GitHub-Event", "")
        if event_type != "discussion_comment":
            return jsonify({"status": "ignored", "event": event_type}), 200

        try:
            payload = WebhookSchema().load(request.json)
        except ValidationError as e:
            self.audit.log("INVALID_PAYLOAD", {"ip": request.remote_addr, "errors": e.messages})
            return jsonify({"status": "invalid"}), 400

        comment = payload.get("comment", {})
        discussion = payload.get("discussion", {})
        author = comment.get("user", {}).get("login", "")
        body = sanitize_input(comment.get("body", ""))

        if self.comment.is_owner(author):
            return jsonify({"status": "owner_ignored"}), 200
        if self.comment.is_ai_comment(body):
            return jsonify({"status": "ai_ignored"}), 200

        self.audit.log("WEBHOOK_RECEIVED", {"author": author})

        # 별도 스레드에서 AI 응답 (웹훅 타임아웃 방지)
        threading.Thread(
            target=self._process_comment,
            args=(discussion, body, author),
            daemon=True,
        ).start()

        return jsonify({"status": "processing"}), 202

    def _process_comment(self, discussion, body, author):
        try:
            context = f"제목: {discussion.get('title', '')}\n\n내용: {discussion.get('body', '')}"
            reply = self.comment.generate_reply(context, body)
            formatted = self.comment.format_reply(reply)

            disc_number = discussion.get("number")
            disc_id = self._get_discussion_id(disc_number)
            if disc_id:
                self.comment.post_to_github(disc_id, formatted)
                self.audit.log("AI_RESPONSE_SENT", {"author": author})
        except Exception as e:
            logging.error(f"Comment processing failed: {e}")

    def _get_discussion_id(self, number):
        query = """
        query($owner: String!, $name: String!, $number: Int!) {
            repository(owner: $owner, name: $name) {
                discussion(number: $number) { id }
            }
        }
        """
        data = json.dumps({
            "query": query,
            "variables": {
                "owner": self.config.repo_owner,
                "name": self.config.repo_name,
                "number": number,
            }
        }).encode()
        req = Request("https://api.github.com/graphql", data=data, headers={
            "Authorization": f"Bearer {self.config.github_token}",
            "Content-Type": "application/json",
        })
        try:
            with urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                return result["data"]["repository"]["discussion"]["id"]
        except Exception:
            return None

    def run(self):
        self._start_time = time.time()
        self.scheduler.start()
        logging.info(f"BlogAgent starting on {self.config.host}:{self.config.port}")
        self.app.run(host=self.config.host, port=self.config.port, debug=False)


# ═══════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    agent = BlogAgent()
    agent.run()
