+++
title = "Stop Using JWTs: The Practicality and Implementation of Session-Based Authentication"
date = "2026-06-17T09:00:39+09:00"
draft = "false"
tags = ["Security", "WebDev", "Authentication", "Architecture", "Go"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

# Stop Using JWTs: The Practicality and Implementation of Session-Based Authentication

Recently, the topic "Stop Using JWTs" has resurfaced as a hot potato in communities like Hacker News. When JWTs (JSON Web Tokens) first emerged, they were considered the standard for Microservice Architectures (MSA) thanks to the magic word "stateless." However, in the reality of operating web services, we often fall into the trap of statelessness.

This article will explore why many developers are abandoning JWTs and returning to traditional session-based authentication (or database-based tokens), and how to implement it in practice.

## The Sweet Trap of JWTs

The biggest advantage of JWTs is that they don't require storing user state on the server. Since all information is contained within the token itself, only the signature needs to be verified without a database lookup. Theoretically, this offers excellent scalability.

However, this "advantage" quickly becomes a "disadvantage."

### 1. Revocation Problem
Once issued, JWTs are valid until their expiration date. What if a user logs out, or an administrator needs to force them to log out?

*   **Option 1:** Let the token remain valid until it expires, as it cannot be immediately revoked. (Impossible as a safety measure)
*   **Option 2:** Introduce a blacklist. (Ultimately requires a DB/Redis lookup -> loss of stateless advantage)

The moment you introduce a blacklist, you need to check it for every JWT verification, thus losing the advantage of "without database lookup."

### 2. Token Size and Overhead
JWTs, including headers, payloads, and signatures, are significantly larger than typical session IDs. The more claims (Roles, permissions, etc.) you include per user, the larger the token becomes. This wastes network bandwidth with every request.

## Returning to Session-Based Authentication

In conclusion, it's better to accept the fact that **"state is managed on the server-side."** Using an in-memory database like Redis allows for very fast session management, and immediate logout or forced logout is possible.

In this section, we will build a simple yet robust session-based authentication system using Go and Redis.

### Prerequisites

We assume Redis is installed and running locally.

### Implementation Code (Go)

The following code is a simple HTTP server that provides `/login`, `/protected`, and `/logout` endpoints.

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

// User information (in a real application, this would be fetched from a DB)
var userDB = map[string]string{
	"user1": "$2a$14$ajq8Q7fbnFR0nXf8bA7HcuiJ/6V.Z.yzX1lYh8g8h5x6z7x8x9x0x", // password: "password"
}

type Credentials struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

func main() {
	// Initialize Redis client
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

// Login handler
func loginHandler(w http.ResponseWriter, r *http.Request) {
	var creds Credentials
	err := json.NewDecoder(r.Body).Decode(&creds)
	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	// Check if user exists and verify password
	hashedPassword, exists := userDB[creds.Username]
	if !exists {
		w.WriteHeader(http.StatusUnauthorized)
		return
	}

	if err := bcrypt.CompareHashAndPassword([]byte(hashedPassword), []byte(creds.Password)); err != nil {
		w.WriteHeader(http.StatusUnauthorized)
		return
	}

	// Generate a new session ID
	sessionToken := uuid.NewString()

	// Store session in Redis (expires in 24 hours)
	err = rdb.Set(ctx, sessionToken, creds.Username, 24*time.Hour).Err()
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	// Set cookie (HttpOnly, Secure recommended)
	http.SetCookie(w, &http.Cookie{
		Name:    "session_token",
		Value:   sessionToken,
		Expires: time.Now().Add(24 * time.Hour),
		HttpOnly: true,
		Secure: true, // Only in HTTPS environment
		Path:   "/",
		SameSite: http.SameSiteStrictMode,
	})

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"message": "Login successful"})
}

// Authentication middleware
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

		// Retrieve session from Redis
		response, err := rdb.Get(ctx, sessionToken).Result()
		if err != nil {
			if err == redis.Nil {
				w.WriteHeader(http.StatusUnauthorized)
				return
			}
			w.WriteHeader(http.StatusInternalServerError)
			return
		}

		// Optionally, store username in request context
		// r = r.WithContext(context.WithValue(r.Context(), "username", response))

		next(w, r)
	}
}

// Protected resource handler
func protectedHandler(w http.ResponseWriter, r *http.Request) {
	c, _ := r.Cookie("session_token")
	username, _ := rdb.Get(ctx, c.Value).Result()
	json.NewEncoder(w).Encode(map[string]string{"message": fmt.Sprintf("Hello %s, you accessed a protected route!", username)})
}

// Logout handler
func logoutHandler(w http.ResponseWriter, r *http.Request) {
	c, _ := r.Cookie("session_token")
	sessionToken := c.Value

	// Delete session from Redis (immediate revocation)
	rdb.Del(ctx, sessionToken)

	// Invalidate cookie
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

### Code Explanation and Application Tips

1.  **Secure Cookie Usage:** `HttpOnly` and `Secure` flags are used to prevent XSS (Cross-Site Scripting) and Man-in-the-Middle attacks. It is safer to encourage the client (browser) to store tokens in cookies rather than LocalStorage.

2.  **Leveraging Redis:** Redis, being single-threaded, offers fast atomic operations and is ideal for use as a session store. Even if Redis goes down, the data isn't permanently needed (as users can re-login), so it's configured for fast response times.

3.  **Immediate Logout:** The `logoutHandler` includes code to delete the key from Redis (`rdb.Del`). This perfectly solves JWT's biggest weakness: "inability to log out." The moment the key is deleted, that token (session ID) is no longer valid.

## Conclusion: What Should You Choose?

*   **When JWTs are good:** When the system you are building consists of truly **independent microservices**, user authentication is needed for inter-service communication, and logout/reissue logic is not critical for simple API communications.

*   **When Sessions/Cookies are good:** For general web services, SaaS, and most cases where user security (immediate action required for account termination) is important.

The phrase "Stop Using JWTs" is not because JWT is a bad technology, but because it is **misused and applied inappropriately for the situation.** Adding complex JWT libraries and blacklist logic to a problem that can be solved with a simple session store can be an act of accumulating technical debt.

We recommend applying the Go code example above to your project and experiencing the ease of management and security firsthand.