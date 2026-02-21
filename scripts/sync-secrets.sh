#!/bin/bash
# GitHub Secrets 동기화 스크립트
# .blogrc.yaml 설정을 기반으로 GitHub Secrets를 설정합니다.

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/.blogrc.yaml"

echo -e "${GREEN}=== GitHub Secrets 동기화 ===${NC}"

# gh CLI 확인
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh)가 설치되어 있지 않습니다.${NC}"
    echo "설치: brew install gh"
    exit 1
fi

# gh 인증 확인
if ! gh auth status &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI 로그인이 필요합니다.${NC}"
    echo "실행: gh auth login"
    exit 1
fi

# yq 확인 (YAML 파싱용)
if ! command -v yq &> /dev/null; then
    echo -e "${YELLOW}yq가 설치되어 있지 않습니다. 설치를 진행합니다...${NC}"
    brew install yq
fi

# 설정 파일 확인
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: .blogrc.yaml 파일이 없습니다.${NC}"
    exit 1
fi

# 설정 값 읽기
OCI_HOST=$(yq '.server.host' "$CONFIG_FILE")
OCI_USER=$(yq '.server.user' "$CONFIG_FILE")
OCI_DEPLOY_PATH=$(yq '.server.deploy_path' "$CONFIG_FILE")
SSH_KEY_PATH=$(yq '.deploy.ssh_key_path' "$CONFIG_FILE")

# SSH 키 경로 확장 (~ -> $HOME)
SSH_KEY_PATH="${SSH_KEY_PATH/#\~/$HOME}"

echo -e "${YELLOW}설정 값:${NC}"
echo "  OCI_HOST: $OCI_HOST"
echo "  OCI_USER: $OCI_USER"
echo "  OCI_DEPLOY_PATH: $OCI_DEPLOY_PATH"
echo "  SSH_KEY_PATH: $SSH_KEY_PATH"
echo ""

# Repository 정보 가져오기
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)
if [ -z "$REPO" ]; then
    echo -e "${RED}Error: Git remote가 설정되지 않았습니다.${NC}"
    echo "먼저 GitHub repository를 생성하고 remote를 추가하세요:"
    echo "  git remote add origin https://github.com/USERNAME/REPO.git"
    exit 1
fi

echo -e "${GREEN}Repository: $REPO${NC}"
echo ""

# Secrets 설정 함수
set_secret() {
    local name=$1
    local value=$2

    if [ -z "$value" ]; then
        echo -e "${RED}  [SKIP] $name: 값이 비어있습니다${NC}"
        return 1
    fi

    echo -n "  $name 설정 중... "
    if echo -n "$value" | gh secret set "$name" --repo "$REPO" 2>/dev/null; then
        echo -e "${GREEN}[OK]${NC}"
        return 0
    else
        echo -e "${RED}[FAIL]${NC}"
        return 1
    fi
}

echo -e "${YELLOW}GitHub Secrets 설정:${NC}"

# OCI_HOST
set_secret "OCI_HOST" "$OCI_HOST"

# OCI_USER
set_secret "OCI_USER" "$OCI_USER"

# OCI_DEPLOY_PATH
set_secret "OCI_DEPLOY_PATH" "$OCI_DEPLOY_PATH"

# SSH_PRIVATE_KEY
if [ -f "$SSH_KEY_PATH" ]; then
    SSH_PRIVATE_KEY=$(cat "$SSH_KEY_PATH")
    set_secret "SSH_PRIVATE_KEY" "$SSH_PRIVATE_KEY"
else
    echo -e "${RED}  [SKIP] SSH_PRIVATE_KEY: 키 파일을 찾을 수 없습니다 ($SSH_KEY_PATH)${NC}"
fi

echo ""
echo -e "${GREEN}=== 완료 ===${NC}"
echo "GitHub Secrets 확인: https://github.com/$REPO/settings/secrets/actions"
