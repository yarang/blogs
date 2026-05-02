#!/bin/bash
set -e

echo "=========================================="
echo "Auto Comment Worker 배포 스크립트"
echo "=========================================="

WORKER_SERVER="oci-yarang-arm1"
WORKER_DIR="/var/www/auto-comment-worker"
SERVICE_NAME="auto-comment-worker"

echo ""
echo "1. 워커 디렉토리 생성 ($WORKER_SERVER)..."
ssh $WORKER_SERVER "sudo mkdir -p $WORKER_DIR && sudo chown ubuntu:ubuntu $WORKER_DIR"

echo ""
echo "2. 파일 업로드 ($WORKER_SERVER)..."
scp scripts/auto-comment-worker.py $WORKER_SERVER:$WORKER_DIR/
scp deploy/$SERVICE_NAME.service $WORKER_SERVER:/tmp/

echo ""
echo "3. systemd 서비스 설치 ($WORKER_SERVER)..."
ssh $WORKER_SERVER << 'ENDSSH'
sudo mv /tmp/$SERVICE_NAME.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
ENDSSH

echo ""
echo "4. nginx 설정 추가 ($WEB_SERVER)..."
WEB_SERVER="oci-yarang-ec1"
ssh $WEB_SERVER << 'ENDSSH'
# nginx 설정에 /ai-comment location 추가
sudo tee -a /etc/nginx/sites-available/blog > /dev/null << 'NGINX_CONF'

# AI 자동 응답 워커 웹훅
location /ai-comment {
    proxy_pass http://oci-yarang-arm1.fcoinfup.com:8081/webhook;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location /ai-comment-health {
    proxy_pass http://oci-yarang-arm1.fcoinfup.com:8081/health;
    proxy_set_header Host $host;
}
NGINX_CONF

sudo nginx -t && sudo systemctl reload nginx
ENDSSH

echo ""
echo "5. GitHub 토큰 설정이 필요합니다:"
echo "   echo 'your_github_token' | ssh $WORKER_SERVER 'cat > $WORKER_DIR/.github-token'"
echo "   ssh $WORKER_SERVER 'chmod 600 $WORKER_DIR/.github-token'"

echo ""
echo "=========================================="
echo "배포 완료!"
echo "=========================================="
