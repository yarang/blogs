#!/usr/bin/env python3
"""comment-dashboard.py — 댓글 시스템 모니터링 대시보드 (CLI)

사용법:
    python3 comment-dashboard.py              # 전체 대시보드
    python3 comment-dashboard.py --days 7     # 최근 7일
    python3 comment-dashboard.py --json       # JSON 출력
"""

import json
import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta
from collections import Counter
from pathlib import Path

AUDIT_LOG = "/var/log/auto-comment-worker/audit.log"
GITHUB_TOKEN_FILE = "/etc/auto-comment-worker/github-token"
REPO_OWNER = "yarang"
REPO_NAME = "blogs"


def load_audit_log(days=30):
    """감사 로그 파싱"""
    entries = []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    log_path = Path(AUDIT_LOG)

    if not log_path.exists():
        return entries

    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts = datetime.fromisoformat(entry["timestamp"]).replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    entries.append(entry)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
    return entries


def get_github_discussions():
    """GitHub Discussions에서 최근 댓글 조회"""
    token_path = Path(GITHUB_TOKEN_FILE)
    if not token_path.exists():
        return None

    token = token_path.read_text().strip()
    query = """
    query($owner: String!, $name: String!) {
        repository(owner: $owner, name: $name) {
            discussions(first: 20, orderBy: {field: UPDATED_AT, direction: DESC}) {
                nodes {
                    title
                    number
                    comments(first: 10) {
                        totalCount
                        nodes {
                            author { login }
                            createdAt
                            bodyText
                        }
                    }
                }
                totalCount
            }
        }
    }
    """

    try:
        result = subprocess.run(
            ["curl", "-sf", "-X", "POST", "https://api.github.com/graphql",
             "-H", f"Authorization: Bearer {token}",
             "-H", "Content-Type: application/json",
             "-d", json.dumps({"query": query, "variables": {"owner": REPO_OWNER, "name": REPO_NAME}})],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except Exception:
        return None


def render_dashboard(days, as_json=False):
    """대시보드 렌더링"""
    entries = load_audit_log(days)
    discussions_data = get_github_discussions()

    # 감사 로그 통계
    event_counts = Counter(e["event"] for e in entries)
    daily_counts = Counter(e["timestamp"][:10] for e in entries)
    ip_counts = Counter(
        e.get("details", {}).get("ip", "unknown")
        for e in entries
        if e["event"] == "SIGNATURE_INVALID"
    )

    # AI 응답 통계
    ai_responses = [e for e in entries if e["event"] == "AI_RESPONSE_SENT"]
    webhooks_received = [e for e in entries if e["event"] == "WEBHOOK_RECEIVED"]

    # Discussion 통계
    disc_stats = {"total": 0, "total_comments": 0, "recent_comments": []}
    if discussions_data and "data" in discussions_data:
        repo = discussions_data["data"].get("repository", {})
        discussions = repo.get("discussions", {})
        disc_stats["total"] = discussions.get("totalCount", 0)
        for disc in discussions.get("nodes", []):
            comments = disc.get("comments", {})
            disc_stats["total_comments"] += comments.get("totalCount", 0)
            for c in comments.get("nodes", []):
                disc_stats["recent_comments"].append({
                    "discussion": disc["title"],
                    "author": c.get("author", {}).get("login", "unknown"),
                    "date": c["createdAt"][:10],
                    "preview": c.get("bodyText", "")[:80]
                })

    if as_json:
        print(json.dumps({
            "period_days": days,
            "audit_events": dict(event_counts),
            "daily_activity": dict(daily_counts),
            "suspicious_ips": dict(ip_counts),
            "ai_responses": len(ai_responses),
            "webhooks_received": len(webhooks_received),
            "discussions": disc_stats
        }, indent=2, ensure_ascii=False))
        return

    # CLI 렌더링
    print("=" * 60)
    print(f"  📊 댓글 시스템 대시보드 — 최근 {days}일")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print("\n📈 감사 로그 요약")
    print("-" * 40)
    for event, count in event_counts.most_common():
        icon = {"WEBHOOK_RECEIVED": "📥", "AI_RESPONSE_SENT": "🤖",
                "SIGNATURE_INVALID": "🚫", "INVALID_PAYLOAD": "⚠️"}.get(event, "📋")
        print(f"  {icon} {event:25s} {count:>5d}")
    print(f"  {'총':25s} {len(entries):>5d}")

    print(f"\n🤖 AI 응답: {len(ai_responses)}건 / 수신 웹훅: {len(webhooks_received)}건")

    if ip_counts:
        print("\n🚨 시그니처 실패 IP")
        print("-" * 40)
        for ip, count in ip_counts.most_common(5):
            print(f"  {ip:20s} {count:>5d}회")

    print(f"\n💬 GitHub Discussions")
    print("-" * 40)
    print(f"  총 Discussion: {disc_stats['total']}")
    print(f"  총 댓글:       {disc_stats['total_comments']}")

    if disc_stats["recent_comments"]:
        print(f"\n📝 최근 댓글 (최대 10건)")
        print("-" * 40)
        for c in disc_stats["recent_comments"][:10]:
            print(f"  [{c['date']}] @{c['author']}")
            print(f"    {c['discussion']}")
            print(f"    {c['preview']}...")
            print()

    # 서비스 상태
    print("⚙️  서비스 상태")
    print("-" * 40)
    try:
        r = subprocess.run(
            ["systemctl", "is-active", "auto-comment-worker"],
            capture_output=True, text=True, timeout=5
        )
        status = r.stdout.strip()
        icon = "✅" if status == "active" else "❌"
        print(f"  {icon} auto-comment-worker: {status}")
    except Exception:
        print("  ⚠️  상태 확인 불가")

    for timer in ["auto-translate", "post-generator"]:
        try:
            r = subprocess.run(
                ["systemctl", "is-active", f"{timer}.timer"],
                capture_output=True, text=True, timeout=5
            )
            status = r.stdout.strip()
            icon = "✅" if status == "active" else "⏸️"
            print(f"  {icon} {timer}.timer: {status}")
        except Exception:
            pass

    print("\n" + "=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="댓글 시스템 모니터링 대시보드")
    parser.add_argument("--days", type=int, default=30, help="조회 기간 (일)")
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    args = parser.parse_args()
    render_dashboard(args.days, args.json)
