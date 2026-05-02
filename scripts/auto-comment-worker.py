#!/usr/bin/env python3
import os
import json
import requests
import logging
import hmac
import hashlib
import html
import re
import stat
from datetime import datetime
from flask import Flask, request, jsonify
from subprocess import run
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import Schema, fields, validate, ValidationError

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 속도 제한 설정
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["10 per minute"],
    storage_uri="memory://"
)

# 감사 로그 설정
AUDIT_LOG = os.environ.get('AUDIT_LOG_PATH', '/var/log/auto-comment-worker/audit.log')


def log_audit(event_type: str, details: dict):
    """보안 이벤트 감사 로그 기록"""
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
        with open(AUDIT_LOG, 'a') as f:
            f.write(json.dumps({
                'timestamp': datetime.utcnow().isoformat(),
                'event': event_type,
                'details': details
            }) + '\n')
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")

# 환경 변수
GITHUB_TOKEN_FILE = os.environ.get('GITHUB_TOKEN_FILE', '')
if GITHUB_TOKEN_FILE and os.path.exists(GITHUB_TOKEN_FILE):
    # 토큰 파일 권한 검증
    st = os.stat(GITHUB_TOKEN_FILE)
    if st.st_mode & (stat.S_IRWXO | stat.S_IRWXG):
        logger.error("Token file has insecure permissions")
        raise PermissionError("Token file must be 600 or 400")
    with open(GITHUB_TOKEN_FILE, 'r') as f:
        GITHUB_TOKEN = f.read().strip()
else:
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')


def validate_executable_path(path: str) -> str:
    """실행 파일 경로 검증 (심볼릭 링크 지원)"""
    # 원본 경로가 존재하는지 먼저 확인
    if not os.path.exists(path):
        raise FileNotFoundError(f"Path not found: {path}")

    # 심볼릭 링크이면 실제 타겟을 확인하지 않고 링크 자체를 사용
    if os.path.islink(path):
        # 심볼릭 링크의 타겟이 존재하는지 확인
        target = os.readlink(path)
        if not os.path.exists(os.path.join(os.path.dirname(path), target)):
            # 절대 경로인 경우
            if not os.path.exists(target):
                raise FileNotFoundError(f"Symlink target not found: {target}")
        # 심볼릭 링크 자체를 반환 (exec가 링크를 따라감)
        return path

    # 일반 파일인 경우
    if not os.path.isfile(path):
        raise ValueError(f"Not a file: {path}")

    if not os.access(path, os.X_OK):
        raise PermissionError(f"Not executable: {path}")

    return path


CLAUDE_CODE_PATH = validate_executable_path(
    os.environ.get('CLAUDE_CODE_PATH', '/home/ubuntu/.local/bin/claude')
)
AGENTFORGE_CONFIG = os.path.expanduser('~/.agent_forge_for_zai.json')
GITHUB_API_URL = "https://api.github.com/graphql"

# 웹훅 시크릿 로드
WEBHOOK_SECRET = None
WEBHOOK_SECRET_FILE = os.environ.get('GITHUB_WEBHOOK_SECRET_FILE', '')

# 파일에서 시크릿 로드 시도
if WEBHOOK_SECRET_FILE:
    try:
        if os.path.exists(WEBHOOK_SECRET_FILE):
            st = os.stat(WEBHOOK_SECRET_FILE)
            if st.st_mode & (stat.S_IRWXO | stat.S_IRWXG):
                logger.error("Webhook secret file has insecure permissions")
                raise PermissionError("Webhook secret file must be 600 or 400")
            with open(WEBHOOK_SECRET_FILE, 'r') as f:
                WEBHOOK_SECRET = f.read().strip()
            logger.info(f"Webhook secret loaded from file: {WEBHOOK_SECRET_FILE}")
        else:
            logger.warning(f"Webhook secret file not found: {WEBHOOK_SECRET_FILE}")
    except Exception as e:
        logger.error(f"Failed to read webhook secret file: {e}")

# 파일 로드 실패시 환경변수에서 시도
if not WEBHOOK_SECRET:
    WEBHOOK_SECRET = os.environ.get('GITHUB_WEBHOOK_SECRET', '')
    if WEBHOOK_SECRET:
        logger.info("Webhook secret loaded from environment variable")

# 시크릿이 없는 경우 경고하지만 서비스는 계속 실행
if not WEBHOOK_SECRET:
    logger.warning("GITHUB_WEBHOOK_SECRET not configured - webhook signature validation will fail")

# 블로그 소유주 (답변하지 않을 사용자 목록)
BLOG_OWNERS = os.environ.get('BLOG_OWNERS', 'yarang').split(',')


# 웹훅 요청 검증 스키마
class WebhookSchema(Schema):
    action = fields.Str(required=True, validate=validate.Equal('created'))
    comment = fields.Dict(required=True)
    discussion = fields.Dict(required=True)
    repository = fields.Dict(required=True)
    sender = fields.Dict(required=False)

def sanitize_comment(body: str) -> str:
    """사용자 입력 sanitization"""
    if not body:
        return body
    # HTML 태그 제거
    body = re.sub(r'<[^>]+>', '', body)
    # HTML 엔티티 이스케이프
    body = html.escape(body)
    # 길이 제한
    body = body[:1000]
    return body

def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """GitHub 웹훅 시그니처 검증"""
    if not signature:
        logger.warning("Missing webhook signature")
        return False

    if not WEBHOOK_SECRET:
        logger.warning("GITHUB_WEBHOOK_SECRET not configured - skipping signature validation")
        # 시크릿이 없어도 서비스가 실행되도록 허용 (development mode)
        return True

    try:
        hash_algorithm, github_signature = signature.split('=', 1)
        if hash_algorithm != 'sha256':
            logger.warning(f"Invalid hash algorithm: {hash_algorithm}")
            return False

        mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload, digestmod=hashlib.sha256)
        expected_signature = mac.hexdigest()

        if not hmac.compare_digest(expected_signature, github_signature):
            logger.warning("Invalid webhook signature")
            return False

        return True
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False

def mask_username(username: str) -> str:
    """사용자명 마스킹"""
    if not username or len(username) < 4:
        return "***"
    return f"{username[:3]}***"

def _is_ai_generated_comment(body: str) -> bool:
    """AI가 생성한 댓글인지 식별"""
    ai_markers = [
        '🤖 AI 어시스턴트',
        'AI 어시스턴트',
        'AgentForge',
        'Claude Code로 자동 생성',
        '자동 생성되었습니다'
    ]
    body_lower = body.lower()
    return any(marker.lower() in body_lower for marker in ai_markers)

def _is_blog_owner(username: str) -> bool:
    """블로그 소유주인지 확인"""
    return username in BLOG_OWNERS

def analyze_comment(context: str, comment: str) -> str:
    """AgentForge 설정으로 Claude Code 실행"""
    prompt = f"""## 블로그 포스트 문맥
{context[:2000]}

## 독자 댓글
{comment}

이 댓글에 대한 응답을 작성해주세요.
- 기술 블로그 어시스턴트로서 전문적이면서 친절하게
- 200자 이내로 간결하게
- 필요한 경우 추가 정보나 링크 제시
"""

    cmd = [
        CLAUDE_CODE_PATH,
        '--settings', AGENTFORGE_CONFIG,
        '--print', prompt
    ]

    result = run(cmd, capture_output=True, text=True, timeout=60)

    if result.returncode == 0:
        output = result.stdout.strip()
        if output:
            return output

    return "의견 감사합니다! 기술적인 부분에 대해 더 논의해보면 좋을 것 같습니다. 🙏"

def get_discussion_graphql_id(repo_owner: str, repo_name: str, discussion_number: int) -> str:
    """Discussion의 GraphQL ID 가져오기"""
    query = """
    query($owner: String!, $name: String!, $number: Int!) {
        repository(owner: $owner, name: $name) {
            discussion(number: $number) {
                id
            }
        }
    }
    """

    variables = {
        "owner": repo_owner,
        "name": repo_name,
        "number": discussion_number
    }

    response = requests.post(
        GITHUB_API_URL,
        json={"query": query, "variables": variables},
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json"
        },
        timeout=10
    )

    if response.status_code == 200:
        data = response.json()
        return data.get("data", {}).get("repository", {}).get("discussion", {}).get("id")

    return None

def post_reply_graphql(discussion_graphql_id: str, original_comment: str, original_author: str, reply: str) -> bool:
    """GraphQL API로 Discussion에 응답 게시"""
    # 입력 sanitization 적용
    safe_comment = sanitize_comment(original_comment)
    safe_author = sanitize_comment(original_author)
    safe_reply = sanitize_comment(reply)

    body = f"""---
**🤖 AI 어시스턴트**

{safe_reply}

*이 댓글은 AgentForge + Claude Code로 자동 생성되었습니다.*

---

@{safe_author} 님이 원래 작성한 댓글:
> {safe_comment[:200]}...
"""

    query = """
    mutation($discussionId: ID!, $body: String!) {
        addDiscussionComment(input: {discussionId: $discussionId, body: $body}) {
            comment {
                id
                databaseId
            }
        }
    }
    """

    variables = {
        "discussionId": discussion_graphql_id,
        "body": body
    }

    response = requests.post(
        GITHUB_API_URL,
        json={"query": query, "variables": variables},
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json"
        },
        timeout=10
    )

    if response.status_code == 200:
        data = response.json()
        if "errors" in data:
            logger.error(f"GraphQL errors: {data['errors']}")
            return False
        return True

    return False

@app.route('/webhook', methods=['POST'])
@limiter.limit("10 per minute")
def github_webhook():
    """GitHub Webhook 수신"""
    # 시그니처 검증
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_webhook_signature(request.data, signature):
        log_audit('SIGNATURE_INVALID', {'ip': request.remote_addr})
        return jsonify({'status': 'unauthorized'}), 401

    # 요청 스키마 검증
    schema = WebhookSchema()
    try:
        payload = schema.load(request.json)
    except ValidationError as err:
        logger.warning(f"Invalid webhook payload: {err.messages}")
        log_audit('INVALID_PAYLOAD', {'ip': request.remote_addr, 'errors': err.messages})
        return jsonify({'status': 'invalid'}), 400

    log_audit('WEBHOOK_RECEIVED', {'ip': request.remote_addr})

    logger.info(f"Payload keys: {list(payload.keys())}")

    # 댓글 정보 추출
    comment = payload.get('comment', {})
    discussion = payload.get('discussion', {})
    repository = payload.get('repository', {})

    comment_body = sanitize_comment(comment.get('body', ''))
    discussion_title = sanitize_comment(discussion.get('title', ''))
    discussion_body = sanitize_comment(discussion.get('body', ''))
    repo_full_name = repository.get('full_name')
    discussion_number = discussion.get('number')
    comment_id = comment.get('id')

    repo_owner, repo_name = repo_full_name.split('/', 1) if '/' in repo_full_name else (repo_full_name, '')
    original_author = comment.get('user', {}).get('login', '사용자')

    # 사용자명 마스킹
    masked_author = mask_username(original_author)
    logger.info(f"Comment from: {masked_author}")
    logger.info(f"Discussion: #{discussion_number}")

    # 블로그 소유주의 댓글이면 무시
    if _is_blog_owner(original_author):
        logger.info(f"Ignoring comment from blog owner: {masked_author}")
        return jsonify({'status': 'owner_comment_ignored'}), 200

    # AI가 생성한 댓글이면 무시
    if _is_ai_generated_comment(comment_body):
        logger.info(f"Ignoring AI-generated comment from: {masked_author}")
        return jsonify({'status': 'ai_comment_ignored'}), 200

    try:
        discussion_graphql_id = get_discussion_graphql_id(repo_owner, repo_name, discussion_number)

        if not discussion_graphql_id:
            logger.error("Failed to get Discussion GraphQL ID")
            return jsonify({'status': 'failed', 'message': 'Discussion not found'}), 404

        logger.info(f"Discussion GraphQL ID: {discussion_graphql_id}")

        context = f"제목: {discussion_title}\n\n내용: {discussion_body}"
        reply = analyze_comment(context, comment_body)

        if post_reply_graphql(discussion_graphql_id, comment_body, original_author, reply):
            logger.info(f"✓ Replied to comment {comment_id}")
            log_audit('AI_RESPONSE_SENT', {'discussion': discussion_number, 'comment_id': comment_id})
            return jsonify({'status': 'replied'}), 200
        else:
            logger.error(f"✗ Failed to reply to comment {comment_id}")
            return jsonify({'status': 'failed'}), 500

    except Exception as e:
        logger.error(f"✗ Error: {e}", exc_info=True)
        # 상세 traceback은 로그에만, 응답은 간소화
        return jsonify({'status': 'error', 'message': 'Internal error'}), 500

@app.route('/health', methods=['GET'])
def health():
    """헬스 체크"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8081))
    app.run(host='0.0.0.0', port=port)
