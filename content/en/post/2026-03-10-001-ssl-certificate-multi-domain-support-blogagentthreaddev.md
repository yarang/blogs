---
title: "SSL Certificate Multi-Domain Support: Adding blog.agentthread.dev"
date: 2026-03-10T23:36:38+09:00
draft: false
tags: ["ssl", "certificate", "cloudflare", "nginx", "letsencrypt", "dns"]
categories: ["DevOps", "SSL"]
---

# SSL Certificate Multi-Domain Support: Adding blog.agentthread.dev

## Overview

Extended the SSL certificate for blog.fcoinfup.com to support the blog.agentthread.dev domain, allowing both domains to use the same certificate.

## Background

Created the blog.agentthread.dev domain through Cloudflare and connected it to the same server as blog.fcoinfup.com (130.162.133.47). To serve identical content on both domains, the SSL certificate was extended to support multiple domains.

## Work Details

### 1. DNS Configuration

**Cloudflare DNS Record Creation:**
```bash
blog.agentthread.dev → 130.162.133.47 (A record)
```

**Existing Domain:**
```bash
blog.fcoinfup.com → CNAME → oci-yarang-ec1.fcoinfup.com → 130.162.133.47
```

### 2. SSL Certificate Extension

**Existing Certificate Info:**
- Certificate Name: blog.fcoinfup.com
- Domain: blog.fcoinfup.com (single domain)
- Encryption: ECDSA
- Expiration: 2026-06-08

**Extended Certificate Info:**
- Certificate Name: blog.fcoinfup.com
- Domains: blog.fcoinfup.com, **blog.agentthread.dev**
- Encryption: ECDSA
- Expiration: 2026-06-08 (89 days remaining)

### 3. Certbot Commands

**Certificate Extension:**
```bash
sudo certbot certonly --expand -d blog.fcoinfup.com -d blog.agentthread.dev
```

Or renew existing certificate:
```bash
sudo certbot renew --force-renewal --cert-name blog.fcoinfup.com
```

### 4. Nginx Configuration Update

**Update server_name directive:**
```nginx
server {
    listen 443 ssl http2;
    server_name blog.fcoinfup.com blog.agentthread.dev;

    ssl_certificate /etc/letsencrypt/live/blog.fcoinfup.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/blog.fcoinfup.com/privkey.pem;

    # Other settings...
}
```

**Reload Nginx:**
```bash
sudo nginx -t      # Test configuration
sudo systemctl reload nginx
```

## Technical Details

### SSL/TLS Certificate

- **Type:** ECDSA (Elliptic Curve Digital Signature Algorithm)
- **CA:** Let's Encrypt
- **SAN (Subject Alternative Name):** blog.fcoinfup.com, blog.agentthread.dev
- **Expiration:** 2026-06-08

### Web Server

- **Software:** nginx
- **HTTP→HTTPS Redirect:** Automatic redirect enabled
- **HTTP/2:** Enabled

### DNS

- **Provider:** Cloudflare
- **Record Type:** A
- **TTL:** 3600 seconds (1 hour)
- **Proxy:** Disabled (DNS only)

## Results

### Accessible URLs

Both domains are accessible via HTTPS:

- **https://blog.fcoinfup.com** ✅
- **https://blog.agentthread.dev** ✅

### HTTP Automatic Redirect

```
http://blog.fcoinfup.com     → https://blog.fcoinfup.com
http://blog.agentthread.dev  → https://blog.agentthread.dev
```

### SSL Verification

```bash
$ curl -I https://blog.agentthread.dev
HTTP/2 200
server: nginx
content-type: text/html
```

## Auto-Renewal

Let's Encrypt certificates automatically renew every 90 days. The Certbot timer handles renewal automatically.

**Check Renewal Status:**
```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

## Security Recommendations

1. **Regular certificate expiration checks**
2. **HTTP security headers configuration** (HSTS, CSP, etc.)
3. **Strong encryption curves** (currently using ECDSA)
4. **Regular web server updates**

## Conclusion

The blog.agentthread.dev domain has been successfully added, and secure HTTPS access is available through a valid SSL certificate. Both domains serve identical content, allowing users to choose their preferred domain for access.

---

**Korean Version:** [한국어 버전](/ko/post/2026-03-10-001-ssl-인증서-다중-도메인-지원-설정-blogagentthreaddev-추가/)
