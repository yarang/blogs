#!/usr/bin/env python3
import os
import json
import requests
import logging
from flask import Flask, request, jsonify
from subprocess import run

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 환경 변수
GITHUB_TOKEN_FILE = os.environ.get('GITHUB_TOKEN_FILE', '')
if GITHUB_TOKEN_FILE and os.path.exists(GITHUB_TOKEN_FILE):
    with open(GITHUB_TOKEN_FILE, 'r') as f:
        GITHUB_TOKEN = f.read().strip()
else:
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
CLAUDE_CODE_PATH = os.environ.get('CLAUDE_CODE_PATH', '/home/ubuntu/.local/bin/claude')
AGENTFORGE_CONFIG = os.path.expanduser('~/.agent_forge_for_zai.json')
GITHUB_API_URL = "https://api.github.com/graphql"

# 블로그 소유주 (답변하지 않을 사용자 목록)
BLOG_OWNERS = os.environ.get('BLOG_OWNERS', 'yarang').split(',')

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
        }
    )

    if response.status_code == 200:
        data = response.json()
        return data.get("data", {}).get("repository", {}).get("discussion", {}).get("id")

    return None

def post_reply_graphql(discussion_graphql_id: str, original_comment: str, original_author: str, reply: str) -> bool:
    """GraphQL API로 Discussion에 응답 게시"""
    body = f"""---
**🤖 AI 어시스턴트**

{reply}

*이 댓글은 AgentForge + Claude Code로 자동 생성되었습니다.*

---

@{original_author} 님이 원래 작성한 댓글:
> {original_comment[:200]}...
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
        }
    )

    if response.status_code == 200:
        data = response.json()
        if "errors" in data:
            logger.error(f"GraphQL errors: {data['errors']}")
            return False
        return True

    return False

@app.route('/webhook', methods=['POST'])
def github_webhook():
    """GitHub Webhook 수신"""
    payload = request.json

    logger.info(f"Payload keys: {list(payload.keys())}")

    # Discussion 댓글 이벤트만 처리
    if payload.get('action') != 'created':
        return jsonify({'status': 'ignored'}), 200

    # 댓글 정보 추출
    comment = payload.get('comment', {})
    discussion = payload.get('discussion', {})
    repository = payload.get('repository', {})

    comment_body = comment.get('body', '')
    discussion_title = discussion.get('title', '')
    discussion_body = discussion.get('body', '')
    repo_full_name = repository.get('full_name')
    discussion_number = discussion.get('number')
    comment_id = comment.get('id')

    repo_owner, repo_name = repo_full_name.split('/', 1) if '/' in repo_full_name else (repo_full_name, '')
    original_author = comment.get('user', {}).get('login', '사용자')

    logger.info(f"Comment from: {original_author}")
    logger.info(f"Discussion: #{discussion_number}")

    # 블로그 소유주의 댓글이면 무시
    if _is_blog_owner(original_author):
        logger.info(f"Ignoring comment from blog owner: {original_author}")
        return jsonify({'status': 'owner_comment_ignored'}), 200

    # AI가 생성한 댓글이면 무시
    if _is_ai_generated_comment(comment_body):
        logger.info(f"Ignoring AI-generated comment from: {original_author}")
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
            return jsonify({'status': 'replied'}), 200
        else:
            logger.error(f"✗ Failed to reply to comment {comment_id}")
            return jsonify({'status': 'failed'}), 500

    except Exception as e:
        logger.error(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """헬스 체크"""
    return jsonify({
        'status': 'healthy',
        'blog_owners': BLOG_OWNERS
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8081))
    app.run(host='0.0.0.0', port=port)
