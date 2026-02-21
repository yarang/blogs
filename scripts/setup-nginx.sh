#!/bin/bash
# OCI 서버에서 실행할 Nginx 설정 스크립트

set -e

# 변수 설정
DEPLOY_USER="${1:-ubuntu}"      # OCI 서버 사용자명 (예: ubuntu, opc)
DEPLOY_PATH="${2:-/var/www/blog}"  # 배포 경로
DOMAIN="${3:-blog.fcoinfup.com}"         # 도메인 (선택사항)

echo "=== OCI 블로그 서버 설정 시작 ==="
echo "사용자: $DEPLOY_USER"
echo "배포 경로: $DEPLOY_PATH"

# 패키지 업데이트 및 Nginx 설치
sudo apt-get update
sudo apt-get install -y nginx

# 배포 디렉토리 생성
sudo mkdir -p $DEPLOY_PATH
sudo chown -R $DEPLOY_USER:$DEPLOY_USER $DEPLOY_PATH

# Nginx 설정 파일 생성
sudo tee /etc/nginx/sites-available/blog > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    root $DEPLOY_PATH;
    index index.html;

    # 정적 파일 캐싱
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # 보안 헤더
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # gzip 압축
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    # 모든 요청을 index.html로 라우팅 (SPA 지원)
    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

# 사이트 활성화
sudo ln -sf /etc/nginx/sites-available/blog /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Nginx 설정 테스트
sudo nginx -t

# Nginx 재시작
sudo systemctl restart nginx
sudo systemctl enable nginx

# 방화벽 설정 (필요한 경우)
sudo ufw allow 'Nginx Full' 2>/dev/null || echo "UFW not configured, skipping firewall rules"

echo "=== 설정 완료 ==="
echo "정적 파일 배포 위치: $DEPLOY_PATH"
echo "Nginx 상태: $(sudo systemctl is-active nginx)"
echo ""
echo "다음 단계:"
echo "1. GitHub Secrets에 다음 값들을 설정하세요:"
echo "   - SSH_PRIVATE_KEY: SSH 개인 키"
echo "   - OCI_HOST: 서버 IP 주소"
echo "   - OCI_USER: $DEPLOY_USER"
echo "   - OCI_DEPLOY_PATH: $DEPLOY_PATH"
