+++
title = "Stop Using JWTs: 세션 기반 인증의 실용성과 구현"
date = 2026-06-17T09:00:39+09:00
draft = false
tags = ["Security", "WebDev", "Authentication", "Architecture", "Go"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# Stop Using JWTs: 세션 기반 인증의 실용성과 구현

최근 Hacker News와 같은 커뮤니티에서 "Stop Using JWTs"라는 주제가 다시 한번 뜨거운 감자로 떠올랐습니다. JWT(JSON Web Token)는 처음 등장했을 때만 해도 "무상태(Stateless)"라는 마법의 주문 덕분에 마이크로서비스 아키텍처(MSA)의 표준처럼 여겨졌습니다. 하지만 현실의 웹 서비스를 운영하면서 무상태의 함정에 빠지는 경우가 너무나 많습니다.

이 글에서는 왜 많은 개발자가 JWT에서 발을 떼고, 전통적인 세션 기반 인증(혹은 DB 기반 토큰)으로 돌아가고 있는지, 그리고 이를 실전에서 어떻게 구현하는지 살펴보겠습니다.

## JWT의 달콤한 함정

JWT의 가장 큰 장점은 서버에 사용자 상태를 저장하지 않아도 된다는 점입니다. 토큰 자체에 모든 정보가 담겨 있으니, 데이터베이스 조회 없이 서명만 검증하면 됩니다. 이론적으로는 확장성이 뛰어납니다.

하지만 이 "장점"은 곧 "단점"이 됩니다.

### 1. 폐기 불가능성(Revocation Problem)
JWT는 발급되면 유효기간이 끝날 때까지 유효합니다. 만약 사용자가 로그아웃을 하거나, 관리자가 강제로 탈퇴시켜야 한다면 어떻게 할까요? 

*   **Option 1:** 토큰을 즉시 파기할 수 없으니 냅두기 (보험상 불가능)
*   **Option 2:** 블랙리스트를 도입하기 (결국 DB/Redis 조회 필요 -> Stateless의 장점 상실)

블랙리스트를 도입하는 순간, JWT 검증을 위해 매번 블랙리스트를 확인해야 하므로, "데이터베이스 조회 없이"라는 장점이 사라집니다.

### 2. 토큰 크기와 부하
JWT는 헤더, 페이로드, 서명을 포함하여 일반적인 세션 ID보다 훨씬 큽니다. 사용자별로 다양한 클레임(Role, 권한 등)을 담을수록 토큰은 비대해집니다. 이는 매 요청마다 네트워크 대역폭을 낭비하게 만듭니다.

## 세션 기반 인증으로의 회귀

결론적으로, 우리는 **"서버 측에서 상태를 관리한다"**는 사실을 받아들이는 것이 낫습니다. Redis와 같은 인메모리 DB를 사용하면 매우 빠르게 세션을 관리할 수 있으며, 로그아웃이나 강제 탈퇴가 즉시 가능합니다.

이번 섹션에서는 Go 언어와 Redis를 사용하여 간단하지만 강력한 세션 기반 인증 시스템을 구축해 보겠습니다.

### 사전 준비

Redis가 로컬에 설치되어 있고 실행 중이라고 가정합니다.

### 구현 코드 (Go)

아래 코드는 `/login`, `/protected`, `/logout` 엔드포인트를 제공하는 간단한 HTTP 서버입니다.

```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"golang.org/x/crypto/bcrypt"
)

var ctx = context.Background()
var rdb *redis.Client

// 사용자 정보 (실제로는 DB에서 조회)
var userDB = map[string]string{
	"user1": "$2a$14$ajq8Q7fbnFR0nXf8bA7HcuiJ/6V.Z.yzX1lYh8g8h5x6z7x8x9x0x", // password: "password"
}

type Credentials struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

func main() {
	// Redis 클라이언트 초기화
	rdb = redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
		Password: "", // no password set
		DB: 0,  // use default DB
	})

	r := mux.NewRouter()
	r.HandleFunc("/login", loginHandler).Methods("POST")
	r.HandleFunc("/protected", authMiddleware(protectedHandler)).Methods("GET")
	r.HandleFunc("/logout", authMiddleware(logoutHandler)).Methods("POST")

	fmt.Println("Server starting on port 8000...")
	log.Fatal(http.ListenAndServe(":8000", r))
}

// 로그인 핸들러
func loginHandler(w http.ResponseWriter, r *http.Request) {
	var creds Credentials
	err := json.NewDecoder(r.Body).Decode(&creds)
	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	// 사용자 존재 및 비밀번호 확인
	hashedPassword, exists := userDB[creds.Username]
	if !exists {
		w.WriteHeader(http.StatusUnauthorized)
		return
	}

	if err := bcrypt.CompareHashAndPassword([]byte(hashedPassword), []byte(creds.Password)); err != nil {
		w.WriteHeader(http.StatusUnauthorized)
		return
	}

	// 새로운 세션 ID 생성
	sessionToken := uuid.NewString()

	// Redis에 세션 저장 (만료 24시간)
	err = rdb.Set(ctx, sessionToken, creds.Username, 24*time.Hour).Err()
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	// 쿠키 설정 (HttpOnly, Secure 권장)
	http.SetCookie(w, &http.Cookie{
		Name:    "session_token",
		Value:   sessionToken,
		Expires: time.Now().Add(24 * time.Hour),
		HttpOnly: true,
		Secure: true, // HTTPS 환경에서만
		Path:   "/",
		SameSite: http.SameSiteStrictMode,
	})

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"message": "Login successful"})
}

// 인증 미들웨어
func authMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		c, err := r.Cookie("session_token")
		if err != nil {
			if err == http.ErrNoCookie {
				w.WriteHeader(http.StatusUnauthorized)
				return
			}
			w.WriteHeader(http.StatusBadRequest)
			return
		}

		sessionToken := c.Value

		// Redis에서 세션 조회
		response, err := rdb.Get(ctx, sessionToken).Result()
		if err != nil {
			if err == redis.Nil {
				w.WriteHeader(http.StatusUnauthorized)
				return
			}
			w.WriteHeader(http.StatusInternalServerError)
			return
		}

		// 요청 컨텍스트에 사용자 이름 저장 (선택 사항)
		// r = r.WithContext(context.WithValue(r.Context(), "username", response))

		next(w, r)
	}
}

// 보호된 리소스 핸들러
func protectedHandler(w http.ResponseWriter, r *http.Request) {
	c, _ := r.Cookie("session_token")
	username, _ := rdb.Get(ctx, c.Value).Result()
	json.NewEncoder(w).Encode(map[string]string{"message": fmt.Sprintf("Hello %s, you accessed a protected route!", username)})
}

// 로그아웃 핸들러
func logoutHandler(w http.ResponseWriter, r *http.Request) {
	c, _ := r.Cookie("session_token")
	sessionToken := c.Value

	// Redis에서 세션 삭제 (즉시 폐기)
	rdb.Del(ctx, sessionToken)

	// 쿠키 무효화
	http.SetCookie(w, &http.Cookie{
		Name:    "session_token",
		Value:   "",
		Expires: time.Now().Add(-1 * time.Hour),
		HttpOnly: true,
		Path:   "/",
	})

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"message": "Logout successful"})
}
```

### 코드 설명 및 적용 팁

1.  **안전한 쿠키 사용:** `HttpOnly`와 `Secure` 플래그를 사용하여 XSS(교차 사이트 스크립팅) 및 중간자 공격을 방지했습니다. 클라이언트(브라우저)가 토큰을 LocalStorage가 아닌 쿠키에 저장하도록 유도하는 것이 안전합니다.

2.  **Redis 활용:** Redis는 싱글 스레드 기반이므로 원자적 연산이 빠르며, 세션 저장소로 사용하기에 최적입니다. 만약 Redis가 다운되더라도 영구적으로 데이터가 필요한 것은 아니므로(재로그인하면 됨), 빠른 응답 속도에 집중하여 설정합니다.

3.  **즉시 로그아웃:** `logoutHandler`를 보면 Redis에서 키를 삭제하는 코드(`rdb.Del`)가 있습니다. 이는 JWT의 가장 큰 약점인 "로그아웃이 안 됨"을 완벽하게 해결합니다. 키가 삭제되는 순간, 해당 토큰(세션 ID)은 더 이상 유효하지 않습니다.

## 결론: 무엇을 선택해야 할까?

*   **JWT가 좋은 경우:** 당신이 구축하는 시스템이 진정으로 **독립적인 마이크로서비스**들로 구성되어 있고, 서비스 간 통신에서 사용자 인증이 필요하며, 로그아웃/재발급 로직이 중요하지 않은 단순 API 통신인 경우.

*   **세션/Cookie가 좋은 경우:** 일반적인 웹 서비스, SaaS, 사용자의 보안(계정 탈��� 시 즉각적인 조치 필요)이 중요한 대부분의 경우.

"Stop Using JWTs"라는 말은 JWT가 나쁜 기술이라서가 아니라, **상황에 맞지 않게 오남당되고 있기 때문**입니다. 간단한 세션 저장소 하나면 해결될 문제에 복잡한 JWT 라이브러리와 블랙리스트 로직을 추가하는 것은 기술 부채를 쌓는 행위일 수 있습니다.

위의 Go 코드 예제를 프로젝트에 적용해 보시고, 관리의 용이성과 보안성을 직접 경험해 보시길 권장합니다.