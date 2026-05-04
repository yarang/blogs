#!/bin/bash
# auto-translate.sh — 미번역 포스트 자동 번역
# Blog API /translate/sync 호출

set -euo pipefail

API_KEY_FILE="/etc/auto-comment-worker/credentials/blog-api-key"
BASE_URL="https://blog.fcoinfup.com/api"
LOG_TAG="auto-translate"

log() { logger -t "$LOG_TAG" "$1"; echo "$(date -Iseconds) $1"; }

# API 키 로드
if [ ! -f "$API_KEY_FILE" ]; then
    log "ERROR: API key file not found: $API_KEY_FILE"
    exit 1
fi
API_KEY=$(cat "$API_KEY_FILE")

# 번역 상태 확인
log "Checking translation status..."
STATUS=$(curl -sf -H "X-API-Key: $API_KEY" "$BASE_URL/translate/status" 2>&1) || {
    log "ERROR: Failed to check translation status"
    exit 1
}

UNTRANSLATED=$(echo "$STATUS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('needs_translation_count', 0))
" 2>/dev/null || echo "0")

if [ "$UNTRANSLATED" = "0" ]; then
    log "All posts are translated. Nothing to do."
    exit 0
fi

log "Found $UNTRANSLATED untranslated post(s). Starting sync..."

# 번역 동기화 실행
RESULT=$(curl -sf -X POST -H "X-API-Key: $API_KEY" "$BASE_URL/translate/sync" --max-time 600 2>&1) || {
    log "ERROR: Translation sync failed"
    exit 1
}

TRANSLATED=$(echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
s = data.get('summary', {})
print(f\"translated={s.get('translated',0)} failed={s.get('failed',0)}\")
" 2>/dev/null || echo "parse error")

log "Translation sync completed: $TRANSLATED"
