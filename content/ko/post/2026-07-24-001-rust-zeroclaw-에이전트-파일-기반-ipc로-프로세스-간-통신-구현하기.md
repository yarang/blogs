+++
title = "Rust ZeroClaw 에이전트: 파일 기반 IPC로 프로세스 간 통신 구현하기"
date = 2026-07-24T09:00:59+09:00
draft = false
tags = ["Rust", "ZeroClaw", "Multi-Agent", "IPC", "Architecture", "Systems Programming"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# 멀티 에이전트 환경에서의 IPC 설계: ZeroClaw와 파일 기반 통신

최근 멀티 에이전트 시스템을 구축하면서 가장 큰 병목이었던 부분은 바로 **에이전트 간 통신(Inter-Agent Communication)**이었습니다. 기존에는 HTTP나 WebSocket을 주로 사용했지만, 가벼운 에이전트 간의 빈번한 메시지 교환에는 오버헤드가 크고 복잡도가 높았습니다. 이를 해결하기 위해 우리 팀의 ZeroClaw 프로젝트에서는 **파일 기반 아키텍처(File-based IPC)**를 채택하여 고성능이면서도 간결한 통신 메커니즘을 구현했습니다.

이 글에서는 소프트웨어 렌더링의 직관적인 원리를 시스템 프로그래밍에 적용하듯, 복잡한 프로토콜 없이 파일 시스템의 원자적 연산만으로 안전한 통신을 구축하는 방법을 소개합니다.

## 왜 파일 기반 IPC인가?

'Beam Engine'이나 'Software rendering' 관련 글에서 보듯, 때로는 복잡한 추상화보다 단순하고 원초적인 접근 방식이 더 강력할 때가 있습니다. 소프트웨어 렌더링이 하드웨어 의존성을 없애는 것처럼, 파일 기반 통신은 복잡한 네트워크 스택이나 소켓 관리의 부담을 줄여줍니다.

*   **단순성:** 별도의 포트 관리나 연결 유지 로직이 필요 없습니다.
*   **안정성:** 운영체제의 파일 시스템 락과 원자적 쓰기(Atomic Write)에 의존하므로 데이터 정합성이 보장됩니다.
*   **확장성:** 에이전트가 프로세스로 분리되어 있어, 특정 에이전트의 장애가 전체 시스템을 멈추게 하지 않습니다.

## ZeroClaw 아키텍처 개요

ZeroClaw는 각 에이전트가 독립적인 Rust 프로세스로 실행되며, 공유 파일 시스템(Shared Directory)을 통해 통신하는 구조를 가집니다.

1.  **Inbox (입력):** 에이전트는 자신의 `inbox` 디렉토리를 감시(Watch)합니다.
2.  **Outbox (출력):** 메시지를 보낼 때는 상대방의 `inbox`에 파일을 생성합니다.
3.  **Protocol:** JSON 형식의 메시지를 `msg-{timestamp}-{uuid}.tmp`로 쓰고, 쓰기가 완료되면 `.tmp`를 제거하여(Rename) 확정합니다.

이 방식은 Unix 철학인 "Write once, read many"를 따르며, `rename` 시스템 콜이 원자적이라는 점을 이용해 '부분적으로 쓰인 메시지'를 읽는 문제를 방지합니다.

## 구현: Rust로 안전한 파일 채널 만들기

바로 적용할 수 있는 핵심 코드를 작성해 보겠습니다. 이 코드는 에이전트가 메시지를 보내고 받는 로직의 핵심입니다.

### 1. 메시지 구조 정의

먼저 에이전트 간 주고받을 데이터 구조를 정의합니다. `serde`를 사용하여 직렬화를 처리합니다.

```rust
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Serialize, Deserialize, Clone)]
struct AgentMessage {
    pub from: String,
    pub to: String,
    pub content: String,
    pub timestamp: u64,
}
```

### 2. 메시지 송신자(Sender) 구현

안전한 쓰기를 위해 임시 파일에 데이터를 기록한 후, `rename`을 통해 원자적으로 메시지를 전달합니다.

```rust
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

fn send_message(target_inbox: &Path, msg: &AgentMessage) -> std::io::Result<()> {
    // 1. 고유한 파일명 생성 (Timestamp + UUID 대체용 Random)
    let filename = format!("msg_{}.json", SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos());
    let tmp_path = target_inbox.join(format!("{}.tmp", filename));
    let final_path = target_inbox.join(&filename);

    // 2. 임시 파일에 쓰기
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&tmp_path)?;
    
    let json_str = serde_json::to_string(msg)?;
    file.write_all(json_str.as_bytes())?;
    file.sync_all()?; // 디스크에 플러시하여 데이터 보장

    // 3. 원자적 이름 변경 (Rename) -> 메시지 확정
    fs::rename(&tmp_path, &final_path)?;

    Ok(())
}
```

### 3. 메시지 수신자(Receiver) 구현

수신 측에서는 디렉토리 변경을 감시하거나 주기적으로 폴링하여 `.json` 확장자를 가진 새로운 파일을 처리합니다.

```rust
use std::fs;

fn process_inbox(inbox_path: &Path) -> std::io::Result<Vec<AgentMessage>> {
    let mut messages = Vec::new();

    // inbox 디렉토리가 없으면 생성 (에러 처리 생략)
    if !inbox_path.exists() {
        fs::create_dir_all(inbox_path)?;
        return Ok(messages);
    }

    for entry in fs::read_dir(inbox_path)? {
        let entry = entry?;
        let path = entry.path();

        // .json 파일만 처리하고, .tmp 파일(쓰기 중)은 무시
        if path.extension().and_then(|s| s.to_str()) == Some("json") {
            // 파일 읽기
            let content = fs::read_to_string(&path)?;
            if let Ok(msg) = serde_json::from_str::<AgentMessage>(&content) {
                messages.push(msg);
            }
            
            // 처리 후 파일 삭제 (Consumer 패턴)
            fs::remove_file(&path)?;
        }
    }
    Ok(messages)
}
```

### 4. 에이전트 런타임 루프

실제 에이전트는 이 로직을 무한 루프로 돌립니다. `notify` 크레이트를 사용하면 폴링 오버헤드를 줄일 수 있지만, 간단한 구현을 위해 `std::thread::sleep`을 사용한 폴링 방식을 보여드립니다.

```rust
use std::path::PathBuf;
use std::thread;
use std::time::Duration;

fn run_agent(agent_name: &str, inbox_dir: &str) {
    let inbox_path = PathBuf::from(inbox_dir);
    println!("[{}] Agent started.", agent_name);

    loop {
        match process_inbox(&inbox_path) {
            Ok(msgs) => {
                for msg in msgs {
                    println!("[{}] Received: {}", agent_name, msg.content);
                    // 여기서 비즈니스 로직 처리 및 응답 전송 로직 구현
                }
            }
            Err(e) => eprintln!("Error reading inbox: {}", e),
        }
        
        // CPU 점유율을 줄이기 위한 대기
        thread::sleep(Duration::from_millis(500));
    }
}
```

## 성능 및 최적화 고찰

이 아키텍처는 단순함이 무기이지만, 고성능을 요구하는 상황에서는 몇 가지 고려해야 할 점이 있습니다.

1.  **I/O Bottleneck:** 디스크 I/O가 빈번할 경우 성능 저하가 발생할 수 있습니다. 이때는 **RAM 디스크(tmpfs)**를 활용하여 inbox 경로를 메모리에 마운트하면 네트워크 소켓 통신에 근접한 성능을 낼 수 있습니다.
2.  **파일 시스템 한계:** 동시에 수만 개의 파일을 생성하면 파일 시스템의 inode 한계에 부딪힐 수 있습니다. 샤딩(Sharding)을 통해 inbox를 하위 디렉토리로 분리하는 전략이 필요합니다.

## 결론

ZeroClaw의 파일 기반 아키텍처는 복잡한 분산 시스템의 트랜잭션 관리를 파일 시스템의 견고함으로 대체하는 훌륭한 전략입니다. '98.css'가 복잡한 프레임워크 없이 브라우저의 네이티브 스타일을 사용하듯, 우리는 OS의 네이티브 기능을 활용하여 에이전트 통신을 구현했습니다.

이 접근 방식은 특히 **마이크로서비스 간 결합도를 낮추고 싶거나, 프로세스 충돌로부터 시스템을 격리하고 싶을 때** 매우 유용합니다. 여러분의 다음 프로젝트에서 복잡한 MQ(Message Queue) 대신, 단순한 파일 하나를 던져보는 건 어떨까요?

---

**참고:** ZeroClaw 프로젝트는 고성능 Rust 에이전트 런타임으로, 위 코드는 실제 아키텍처 설계안의 일부를 단순화한 것입니다.