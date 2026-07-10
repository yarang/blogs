+++
title = "Rust로 구현하는 PostgreSQL Wire Protocol: pgrx와 비동기 I/O의 활용"
date = 2026-07-10T09:00:38+09:00
draft = false
tags = ["Rust", "PostgreSQL", "Database", "pgrx", "Architecture", "Tutorial"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# Rust로 구현하는 PostgreSQL Wire Protocol: pgrx와 비동기 I/O의 활용

최근 Hacker News에서 "Postgres rewritten in Rust"라는 흥미로운 프로젝트가 화제가 되었습니다. 기존 C 기반 PostgreSQL의 복잡한 코드베이스를 Rust로 재작성하여 100% 테스트를 통과했다는 소식은 많은 개발자들에게 영감을 주었습니다. 이번 글에서는 단순히 뉴스로 접하고 넘어갈 것이 아니라, Rust가 가진 강력한 타입 시스템과 메모리 안전성을 활용해 데이터베이스 엔진을 어떻게 구현할 수 있는지, 특히 **PostgreSQL Wire Protocol**을 직접 구현하는 방법을 실용적인 관점에서 살펴보겠습니다.

## 1. PostgreSQL Wire Protocol 이해하기

PostgreSQL은 클라이언트와 서버 간의 통신을 위해 자체 정의된 프로토콜을 사용합니다. 메시지는 크게 **Frontend(클라이언트 -> 서버)** 메시지와 **Backend(서버 -> 클라이언트)** 메시지로 나뉘며, 스트림 위에서 패킷 단위로 전송됩니다.

기본적인 메시지 구조는 다음과 같습니다:

1.  **메시지 타입 (1 byte):** 'Q'(Query), 'D'(Data) 등의 식별자
2.  **메시지 길이 (4 bytes):** 길이를 포함한 전체 바이트 수(Int32)
3.  **페이로드 (Payload):** 실제 데이터

Rust의 `bytes::BytesMut`나 제로 카피 파싱 라이브러리인 `nom`을 활용하면 이 바이트 스트림을 안전하고 효율적으로 처리할 수 있습니다.

## 2. 프로젝트 설정 및 의존성

실습을 위해 `tokio` 기반의 비동기 서버를 구성해 보겠습니다. `Cargo.toml`에 다음 의존성을 추가합니다.

```toml
[dependencies]
tokio = { version = "1", features = ["full"] }
bytes = "1"
# 선택 사항: 구조화된 로깅을 위해
tracing = "0.1"
tracing-subscriber = "0.3"
```

## 3. 핸드세이크 및 Start-up 메시지 처리

클라이언트가 연결하면 가장 먼저 `StartupMessage`를 기대합니다. 이를 처리하는 간단한 핸들러를 작성해 보겠습니다.

```rust
use bytes::{Buf, BytesMut};
use std::io::{self, Error, ErrorKind};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpListener;

#[tokio::main]
async fn main() -> io::Result<()> {
    let listener = TcpListener::bind("127.0.0.1:5432").await?;
    println!("PostgreSQL-compatible server listening on port 5432");

    loop {
        let (mut socket, _) = listener.accept().await?;
        tokio::spawn(async move {
            let mut buf = BytesMut::with_capacity(8192);
            
            // Start-up 메시지 수신 대기
            match socket.read_buf(&mut buf).await {
                Ok(_) => {
                    // 프로토콜 버전 체크 (예: 3.0 -> 0x00 03 00 00)
                    if buf.len() < 4 {
                        return;
                    }
                    let version = i32::from_be_bytes([buf[0], buf[1], buf[2], buf[3]]);
                    tracing::info!("Connection request with version: {}", version);

                    // 인자 파싱 (key:value pairs)
                    // 실제 구현에서는 루프를 돌며 null로 구분된 문자열을 파싱해야 합니다.
                    
                    // 인증 성공 응답 전송 (AuthOK)
                    let auth_ok = vec![b'R', 0, 0, 0, 8, 0, 0, 0, 0]; // Type 'R', Length 8, Status 0
                    socket.write_all(&auth_ok).await.unwrap();
                }
                Err(e) => return,
            }
        });
    }
}
```

## 4. Simple Query 프로토콜 구현

가장 기본적인 쿼리인 `Simple Query`('Q' 메시지)를 처리하는 로직을 추가해 봅시다. 클라이언트가 SQL을 보내면 서버는 결과를 `RowDescription`, `DataRow`, `CommandComplete`, `ReadyForQuery` 순서로 응답해야 합니다.

```rust
// ... 이전 코드 ...

// 간단한 파싱 함수 구현
fn parse_message(buf: &mut BytesMut) -> Result<(char, String), io::Error> {
    if buf.len() < 5 {
        return Err(Error::new(ErrorKind::UnexpectedEof, "Message too short"));
    }
    
    let tag = buf[0] as char;
    let len = i32::from_be_bytes([buf[1], buf[2], buf[3], buf[4]]) as usize;

    if buf.len() < len + 1 { // 길이 검증 (Length는 자신을 포함하므로 주의 필요, 여기선 단순화)
         return Err(Error::new(ErrorKind::UnexpectedEof, "Incomplete message"));
    }

    buf.advance(5); // 태그와 길이 필드 스킵
    let payload = buf.split_to(len - 4); // 남은 길이만큼 분리
    
    // null terminated string 처리 (Simple Query)
    let query_str = String::from_utf8_lossy(&payload[..payload.len()-1]).to_string();
    
    Ok((tag, query_str))
}

// 메인 루프 내부 로직 (수정)
// ... Startup 이후 ...

loop {
    // 클라이언트로부터 메시지 수신
    if socket.read_buf(&mut buf).await? == 0 {
        return Ok(()); // 연결 종료
    }

    // 메시지 파싱 (단순화를 위해 하나만 처리한다고 가정)
    let (tag, query) = parse_message(&mut buf)?;

    if tag == 'Q' {
        println!("Received Query: {}", query);

        // 1. RowDescription (컬럼 정보)
        // 'T' + Length(4) + Fields(2) + Name + ...
        let mut resp = BytesMut::new();
        resp.extend_from_slice(&[b'T']); // Tag
        resp.extend_from_slice(&0i32.to_be_bytes()); // Placeholder length
        resp.extend_from_slice(&1i16.to_be_bytes()); // Number of columns
        resp.extend_from_slice(b"id\0"); // Column Name
        resp.extend_from_slice(&0i32.to_be_bytes()); // Table OID
        resp.extend_from_slice(&0i16.to_be_bytes()); // Column Index
        resp.extend_from_slice(&23i32.to_be_bytes()); // Type OID (int4)
        resp.extend_from_slice(&4i16.to_be_bytes()); // Type length
        resp.extend_from_slice(&0i32.to_be_bytes()); // Type modifier
        resp.extend_from_slice(&0i16.to_be_bytes()); // Format code (text)
        
        // 길이 업데이트 (끝에서 다시 계산하여 넣어야 함, 여기선 생략)
        
        // 2. DataRow
        resp.extend_from_slice(&[b'D']);
        // ... 데이터 로직 ...

        // 3. CommandComplete
        let complete_msg = format!("SELECT 1\0");
        let mut complete_pkt = BytesMut::new();
        complete_pkt.extend_from_slice(&[b'C']);
        complete_pkt.extend_from_slice(&(complete_msg.len() as i32 + 4).to_be_bytes());
        complete_pkt.extend_from_slice(complete_msg.as_bytes());

        // 4. ReadyForQuery
        let ready = vec![b'Z', 0, 0, 0, 5, b'I']; // 'I' = Idle

        socket.write_all(&resp).await?;
        socket.write_all(&complete_pkt).await?;
        socket.write_all(&ready).await?;
    }
}
```

## 5. pgrx를 활용한 확장성 고려

직접 프로토콜을 구현하는 것은 학습 목적으로는 훌륭하지만, 실제 PostgreSQL 내부 기능을 확장하려면 `pgrx` 프레임워크를 사용하는 것이 현실적입니다. `pgrx`는 Rust로 PostgreSQL 사용자 정의 함수(UDF)나 인덱스 메서드를 작성할 수 있게 해줍니다.

```rust
// pgrx 예시 (Cargo.toml에 pgrx 의존성 필요)
use pgrx::prelude::*;

#[pg_extern]
fn hello_rust(name: &str) -> String {
    format!("Hello, {}!", name)
}
```

하지만 Wire Protocol을 직접 제어해야 하는 독립적인 서버(예: 프록시나 샤딩 미들웨어)를 만들 때는 위에서 작성한 `tokio` 기반의 핸들러가 더 유연한 선택지가 될 수 있습니다.

## 6. 결론 및 ZeroClaw와의 연결

Rust는 데이터베이스와 같은 안전성과 성능이 동시에 요구되는 시스템을 구축하기에 최적의 언어입니다. 우리 팀인 ZeroClaw에서 진행 중인 **[Multi-Agent] 파일 기반 아키텍처**나 **[Cloud Monitor]** 프로젝트의 내부 데이터 파이프라인을 구축할 때도, 안전한 병렬 처리를 위해 Rust 런타임을 적극적으로 도입할 계획입니다.

위 코드는 단순한 예제이지만, 실제로는 커넥션 풀링, SSL 암호화, 준비된 문장(Prepared Statement) 처리 등 복잡한 로직이 필요합니다. Hacker News에 올라온 "pg_in_rust" 프로젝트처럼, 이러한 기본적인 블록을 하나씩 쌓아나가면 언젠가 완전한 기능을 갖춘 데이터베이스 엔진을 만들 수 있을 것입니다.

이 글을 바탕으로 여러분의 프로젝트에 맞는 커스텀 데이터베이스 핸들러나 프록시를 직접 작성해 보시길 권장합니다.