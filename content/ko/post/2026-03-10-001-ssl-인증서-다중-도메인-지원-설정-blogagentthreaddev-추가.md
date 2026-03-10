+++
title = "SSL 인증서 다중 도메인 지원 설정: blog.agentthread.dev 추가"
date = 2026-03-10T23:36:38+09:00
draft = false
tags = ["ssl", "certificate", "cloudflare", "nginx", "letsencrypt", "dns"]
categories = ["DevOps", "SSL"]
ShowToc = true
TocOpen = true
+++

---
title: "SSL 인증서 다중 도메인 지원 설정: blog.agentthread.dev 추가"
date: 2026-03-10T19:30:00+09:00
draft: false
categories:
  - DevOps
  - SSL
tags:
  - ssl
  - certificate
  - cloudflare
  - nginx
  - letsencrypt
  - dns
---

## 개요

blog.fcoinfup.com 도메인의 SSL 인증서를 확장하여 blog.agentthread.dev 도메인에서도 동일한 인증서를 사용할 수 있도록 설정했습니다.

## 배경

Cloudflare를 통해 blog.agentthread.dev 도메인을 생성하고 blog.fcoinfup.com과 동일한 서버(130.162.133.47)로 연결했습니다. 두 도메인이 동일한 콘텐츠를 제공하도록 하기 위해 SSL 인증서를 다중 도메인을 지원하도록 확장했습니다.

## 작업 내용

### 1. DNS 설정

**Cloudflare DNS 레코드 생성:**
```bash
blog.agentthread.dev → 130.162.133.47 (A 레코드)
```

**기존 도메인:**
```bash
blog.fcoinfup.com → CNAME → oci-yarang-ec1.fcoinfup.com → 130.162.133.47
```

### 2. SSL 인증서 확장

**기존 인증서 정보:**
- 인증서 이름: blog.fcoinfup.com
- 도메인: blog.fcoinfup.com (단일 도메인)
- 암호화: ECDSA
- 만료일: 2026-06-08

**확장 후 인증서 정보:**
- 인증서 이름: blog.fcoinfup.com
- 도메인: blog.fcoinfup.com, **blog.agentthread.dev**
- 암호화: ECDSA
- 만료일: 2026-06-08 (89일 남음)

### 3. Certbot 명령어

**인증서 확장:**
```bash
sudo certbot certonly --expand -d blog.fcoinfup.com -d blog.agentthread.dev
```

또는 기존 인증서 갱신:
```bash
sudo certbot renew --force-renewal --cert-name blog.fcoinfup.com
```

### 4. Nginx 설정 업데이트

**server_name 지시자 업데이트:**
```nginx
server {
    listen 443 ssl http2;
    server_name blog.fcoinfup.com blog.agentthread.dev;

    ssl_certificate /etc/letsencrypt/live/blog.fcoinfup.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/blog.fcoinfup.com/privkey.pem;

    # 기타 설정...
}
```

**Nginx 재시작:**
```bash
sudo nginx -t      # 설정 테스트
sudo systemctl reload nginx
```

## 기술적 세부사항

### SSL/TLS 인증서

- **타입:** ECDSA (Elliptic Curve Digital Signature Algorithm)
- **CA:** Let's Encrypt
- **SAN (Subject Alternative Name):** blog.fcoinfup.com, blog.agentthread.dev
- **만료일:** 2026-06-08

### 웹 서버

- **소프트웨어:** nginx
- **HTTP→HTTPS 리다이렉트:** 자동 리다이렉트 활성화
- **HTTP/2:** 활성화

### DNS

- **제공자:** Cloudflare
- **레코드 타입:** A
- **TTL:** 3600초 (1시간)
- **Proxy:** 비활성 (DNS only)

## 결과

### 접속 가능한 URL

두 도메인 모두 HTTPS로 접속 가능:

- **https://blog.fcoinfup.com** ✅
- **https://blog.agentthread.dev** ✅

### HTTP 자동 리다이렉트

```
http://blog.fcoinfup.com     → https://blog.fcoinfup.com
http://blog.agentthread.dev  → https://blog.agentthread.dev
```

### SSL 검증

```bash
$ curl -I https://blog.agentthread.dev
HTTP/2 200
server: nginx
content-type: text/html
```

## 자동 갱신

Let's Encrypt 인증서는 90일마다 자동 갱신됩니다. Certbot timer가 자동으로 갱신을 처리합니다.

**갱신 상태 확인:**
```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

## 보안 권장사항

1. **정기적인 인증서 만료일 확인**
2. **HTTP 보안 헤더 설정** (HSTS, CSP 등)
3. **강력한 암호화 곡선 사용** (현재 ECDSA 사용)
4. **정기적인 웹 서버 업데이트**

## 결론

blog.agentthread.dev 도메인이 성공적으로 추가되었으며, 유효한 SSL 인증서를 통해 안전한 HTTPS 접속이 가능합니다. 두 도메인이 동일한 콘텐츠를 제공하며 사용자는 선호하는 도메인을 선택하여 접속할 수 있습니다.

---

**영어 버전:** [English Version](/en/post/2026-03-10-001-ssl-certificate-multi-domain-support-blogagentthreaddev/)
