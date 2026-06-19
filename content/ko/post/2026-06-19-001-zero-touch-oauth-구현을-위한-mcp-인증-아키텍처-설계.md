+++
title = "Zero-Touch OAuth 구현을 위한 MCP 인증 아키텍처 설계"
date = 2026-06-19T09:00:58+09:00
draft = false
tags = ["MCP", "Security", "OAuth2", "ZeroClaw", "Architecture"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

최근 'Zero-Touch OAuth for MCP'라는 흥미로운 기술 트렌드를 접했습니다. 우리가 개발 중인 `ZeroClaw` 런타임과 `blog-api-server`의 MCP(Model Context Protocol) 통합 과정에서, 사용자 경험을 저해하지 않으면서도 보안성을 확보하는 것은 필수적인 과제입니다. 이번 포스트에서는 별도의 복잡한 설정 없이 사용자가 MCP 클라이언트를 연결할 수 있도록 돕는 'Zero-Touch' 인증 흐름을 설계하고, 이를 실제 코드로 구현하는 방법을 살펴보겠습니다.

### 왜 Zero-Touch인가?

기존의 OAuth 2.0 흐름은 사용자에게 'Client ID'와 'Client Secret'을 발급받아 설정 파일에 입력하도록 요구하곤 했습니다. 하지만 일반 사용자나 개발자에게 이는 큰 진입 장벽입니다. Zero-Touch OAuth는 클라이언트가 사전에 등록된 정보(Pre-registered metadata)를 통해 자동으로 인증을 시도하고, 사용자는 단순히 '허용' 버튼만 누르면 되는 흐름을 지향합니다.

### 아키텍처 설계

우리는 `blog-api-server`를 MCP Provider로, `Claude Code`나 커스텀 클라이언트를 MCP Consumer로 구성합니다. 핵심은 **PKCE (Proof Key for Code Exchange)** 확장을 사용하여 Secret을 저장하지 않는 Public Client 환경을 구축하는 것입니다.

**핵심 구성 요소:**
1.  **MCP Client (Consumer)**: 사용자의 로컬 환경에서 실행되는 에이전트입니다.
2.  **Auth Server**: `blog-api-server` 내에 구현된 OAuth2 인증 서버입니다.
3.  **Resource Server**: 실제 블로그 API입니다.

### 구현 단계 1: 서버 사이드 (blog-api-server)

먼저, Rust 기반의 `blog-api-server`에 간단한 인증 엔드포인트를 추가해야 합니다. 이전 글인 *'[blog-api-server] MCP 블로그 클라이언트 언어 파라미터 추가'*에서 언급된 아키텍처를 확장하여 Auth 모듈을 독립시킵니다.

여기서는 핵심 로직인 **코드 검증(Verification)** 로직을 보여드리겠습니다. 클라이언트로부터 받은 `code_verifier`를 검증하는 과정입니다.

```rust
// blog-api-server/src/auth/handler.rs
use axum::{extract::State, Json};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use base64::Engine as _;

#[derive(Deserialize)]
pub struct TokenRequest {
    pub code: String,
    pub code_verifier: String, // PKCE를 통해 클라이언트가 생성한 난수
    pub redirect_uri: String,
}

#[derive(Serialize)]
pub struct TokenResponse {
    pub access_token: String,
    pub token_type: String,
    pub expires_in: u64,
}

pub async fn exchange_token(
    State(state): State<AppState>,
    Json(payload): Json<TokenRequest>,
) -> Result<Json<TokenResponse>, String> {
    // 1. DB에서 Authorization Code 조회
    let auth_record = state.db.get_auth_code(&payload.code)
        .await
        .map_err(|_| "Invalid code".to_string())?;

    // 2. PKCE Challenge 검증 (핵심 보안 로직)
    let mut hasher = Sha256::new();
    hasher.update(payload.code_verifier.as_bytes());
    let hashed_verifier = hasher.finalize();
    let encoded_verifier = base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(hashed_verifier);

    if encoded_verifier != auth_record.code_challenge {
        return Err("Code verifier mismatch".to_string());
    }

    // 3. Access Token 발급
    let access_token = generate_jwt(&state.secrets, &auth_record.user_id);

    Ok(Json(TokenResponse {
        access_token,
        token_type: "Bearer".to_string(),
        expires_in: 3600,
    }))
}
```

이 코드는 클라이언트가 보내온 `code_verifier`를 해싱하여, 처음 인증 요청을 보낼 때 생성된 `code_challenge`와 일치하는지 확인합니다. 이 과정이 'Zero-Touch'를 보안적으로 가능하게 만드는 핵심입니다.

### 구현 단계 2: 클라이언트 사이드 (MCP Client)

이제 클라이언트는 사용자 개입 없이(혹은 최소한의 개입으로) 토큰을 발급받을 수 있습니다. Python을 사용한 MCP 클라이언트 예제를 작성해보겠습니다.

```python
import hashlib
import base64
import requests
from urllib.parse import urlencode

# Zero-Touch 설정 (하드코딩 혹은 환경 변수)
CLIENT_ID = "zeroclaw-mcp-client"
AUTH_URL = "https://api.myblog.com/oauth/authorize"
TOKEN_URL = "https://api.myblog.com/oauth/token"
REDIRECT_URI = "http://localhost:3000/callback"

# PKCE Code Verifier 생성
random_bytes = os.urandom(32)
code_verifier = base64.urlsafe_b64encode(random_bytes).rstrip(b'=').decode('utf-8')

# Code Challenge 생성
challenge_digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
code_challenge = base64.urlsafe_b64encode(challenge_digest).rstrip(b'=').decode('utf-8')

def get_auth_url():
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "mcp:read mcp:write",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256"
    }
    return f"{AUTH_URL}?{urlencode(params)}"

def exchange_code_for_token(auth_code):
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "code_verifier": code_verifier # 서버로 전송하여 검증받음
    }
    response = requests.post(TOKEN_URL, data=data)
    return response.json()

# 사용 예시
# 1. 사용자가 get_auth_url()를 통해 브라우저에서 인증 (최초 1회)
# 2. 리다이렉션된 쿼리 파라미터에서 'code' 추출
# 3. token = exchange_code_for_token(code)
```

### ZeroClaw 런타임 통합 고찰

지난 회고록인 *'[ZeroClaw] 2026 상반기 발전방향 회의록'*에서 언급했듯, 우리의 에이전트 런타임은 보안과 확장성을 최우선으로 고려해야 합니다. 위에서 구현한 OAuth 흐름을 ZeroClaw의 `Multi-Agent` 아키텍처에 통합한다면, 각 에이전트는 독립된 Identity를 가질 수 있습니다.

특히 *'[ZeroClaw] 멀티 에이전트 통신 프로토콜 설계'*에서 논의된 바와 같이, Agent 간 통신 시 이 Access Token을 사용하여 다른 에이전트의 리소스(API)에 안전하게 접근할 수 있는 기반을 마련하게 됩니다. 이는 단순한 블로그 자동화를 넘어, 에이전트가 에이전트를 신뢰하고 작업을 위임하는 분산 시스템의 첫걸음이 됩니다.

### 마치며

Zero-Touch OAuth는 사용자의 편의성과 보안이라는 두 마리 토끼를 잡는 훌륭한 접근 방식입니다. `blog-api-server`와 같은 작은 프로젝트부터 시작하여, 점차 `ZeroClaw`의 핵심 인증 모듈로 발전시켜 나갈 계획입니다. 위 코드는 기본적인 골격이므로, 실제 운영 환경에서는 State 검증, Refresh Token Rotation 등의 로직을 추가해야 합니다.

다음 포스트에서는 이렇게 확보된 토큰을 활용하여 MCP 서버와 실제로 데이터를 주고받는 '핸드셰이크(Handshake)' 과정을 디버깅해보겠습니다.