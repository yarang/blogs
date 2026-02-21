#!/bin/bash
# Blog Server Monitoring Agent
# 서버 상태를 주기적으로 확인하고 로그를 기록합니다.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/.blogrc.yaml"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/monitor.log"

# 로그 디렉토리 생성
mkdir -p "$LOG_DIR"

# 설정 읽기
if command -v yq &> /dev/null && [ -f "$CONFIG_FILE" ]; then
    SERVER_HOST=$(yq '.server.host' "$CONFIG_FILE")
    SERVER_USER=$(yq '.server.user' "$CONFIG_FILE")
    DEPLOY_PATH=$(yq '.server.deploy_path' "$CONFIG_FILE")
else
    SERVER_HOST="blog.fcoinfup.com"
    SERVER_USER="ubuntu"
    DEPLOY_PATH="/var/www/blog"
fi

# SSH 키 경로
SSH_KEY="$HOME/CERT/login_oci3"

# 로그 함수
log() {
    local level=$1
    local message=$2
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message" | tee -a "$LOG_FILE"
}

# 서버 체크 함수
check_server() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # HTTP 응답 체크
    local http_status=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://$SERVER_HOST" 2>/dev/null || echo "000")

    # HTTPS 응답 체크
    local https_status=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "https://$SERVER_HOST" 2>/dev/null || echo "000")

    # SSH 연결 체크
    local ssh_status="OK"
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes -i "$SSH_KEY" "$SERVER_USER@$SERVER_HOST" 'echo ok' &>/dev/null; then
        ssh_status="FAIL"
    fi

    # 결과 출력
    echo "[$timestamp] HTTP: $http_status | HTTPS: $https_status | SSH: $ssh_status" | tee -a "$LOG_FILE"

    # 상태에 따른 알림
    if [ "$http_status" != "200" ]; then
        log "WARN" "HTTP check failed: $http_status"
    fi
    if [ "$https_status" != "200" ] && [ "$https_status" != "000" ]; then
        log "WARN" "HTTPS check failed: $https_status"
    fi
    if [ "$ssh_status" != "OK" ]; then
        log "ERROR" "SSH connection failed"
    fi
}

# 서버 상세 정보 수집
collect_metrics() {
    log "INFO" "Collecting server metrics..."

    ssh -o ConnectTimeout=10 -i "$SSH_KEY" "$SERVER_USER@$SERVER_HOST" bash << 'REMOTE_SCRIPT'
        echo "=== System Resources ==="
        uptime
        echo ""
        echo "=== Memory Usage ==="
        free -h
        echo ""
        echo "=== Disk Usage ==="
        df -h /var/www
        echo ""
        echo "=== Nginx Status ==="
        sudo systemctl is-active nginx
        echo ""
        echo "=== Recent Access Logs ==="
        sudo tail -5 /var/log/nginx/access.log 2>/dev/null || echo "No access log"
REMOTE_SCRIPT
}

# 메인 로직
case "${1:-check}" in
    check)
        check_server
        ;;
    metrics)
        collect_metrics
        ;;
    watch)
        log "INFO" "Starting continuous monitoring (Ctrl+C to stop)"
        while true; do
            check_server
            sleep 60
        done
        ;;
    status)
        echo "=== Blog Server Monitor Status ==="
        echo "Server: $SERVER_HOST"
        echo "User: $SERVER_USER"
        echo "Deploy Path: $DEPLOY_PATH"
        echo ""
        echo "Recent logs:"
        tail -10 "$LOG_FILE" 2>/dev/null || echo "No logs yet"
        ;;
    *)
        echo "Usage: $0 {check|metrics|watch|status}"
        echo ""
        echo "Commands:"
        echo "  check   - Single health check"
        echo "  metrics - Collect detailed server metrics"
        echo "  watch   - Continuous monitoring (every 60s)"
        echo "  status  - Show monitor status and recent logs"
        exit 1
        ;;
esac
