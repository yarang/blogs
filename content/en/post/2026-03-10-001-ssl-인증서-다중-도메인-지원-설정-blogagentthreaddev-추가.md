+++
title = ""
date = "2026-03-10T23:36:38+09:00"
draft = "false"
tags = ["ssl", "certificate", "cloudflare", "nginx", "letsencrypt", "dns"]
categories = ["DevOps", "SSL"]
ShowToc = "true"
TocOpen = "true"
+++

---
title: "SSL Certificate Multi-Domain Support Setup: Adding blog.agentthread.dev"
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

## Overview

Extended the SSL certificate for the blog.fcoinfup.com domain to allow the same certificate to be used for the blog.agentthread.dev domain.

## Background

Created the blog.agentthread.dev domain via Cloudflare and connected it to the same server (130.162.133.47) as blog.fcoinfup.com. To ensure both domains serve the same content, the SSL certificate was extended to support multiple domains.

## Implementation Details

### 1. DNS Configuration

**Cloudflare DNS Record Creation:**
```bash
blog.agentthread.dev → 130.162.133.47 (A Record)
```

**Existing Domain:**
```bash
blog.fcoinfup.com → CNAME → oci-yarang-ec1.fcoinfup.com → 130.162.133.47
```

### 2. SSL Certificate Extension

**Existing Certificate Information:**
- Certificate Name: blog.fcoinfup.com
- Domain: blog.fcoinfup.com (Single Domain)
- Encryption: ECDSA
- Expiration Date: 2026-06-08

**Certificate Information After Extension:**
- Certificate Name: blog.fcoinfup.com
- Domain: blog.fcoinfup.com, **blog.agentthread.dev**
- Encryption: ECDSA
- Expiration Date: 2026-06-08 (89 days remaining)

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

**server_name Directive Update:**
```nginx
server {
    listen 443 ssl http2;
    server_name blog.fcoinfup.com blog.agentthread.dev;

    ssl_certificate /etc/letsencrypt/live/blog.fcoinfup.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/blog.fcoinfup.com/privkey.pem;

    # Other settings...
}
```

**Nginx Restart:**
```bash
sudo nginx -t      # Test configuration
sudo systemctl reload nginx
```

## Technical Details

### SSL/TLS Certificate

- **Type:** ECDSA (Elliptic Curve Digital Signature Algorithm)
- **CA:** Let's Encrypt
- **SAN (Subject Alternative Name):** blog.fcoinfup.com, blog.agentthread.dev
- **Expiration Date:** 2026-06-08

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

## Automatic Renewal

Let's Encrypt certificates are automatically renewed every 90 days. The Certbot timer handles the renewal automatically.

**Check Renewal Status:**
```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

## Security Recommendations

1. **Regular Expiration Date Check**
2. **HTTP Security Header Configuration** (HSTS, CSP, etc.)
3. **Use Strong Encryption Curves** (Currently using ECDSA)
4. **Regular Web Server Updates**

## Conclusion

The blog.agentthread.dev domain has been successfully added, and secure HTTPS access is available via a valid SSL certificate. Both domains provide the same content, and users can choose their preferred domain to access the site.

---

**English Version:** [English Version](/post/2026-03-10-001-ssl-certificate-multi-domain-support-blogagentthreaddev/)