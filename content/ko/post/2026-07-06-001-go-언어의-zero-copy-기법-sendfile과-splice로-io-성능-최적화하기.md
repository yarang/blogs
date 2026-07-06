+++
title = "Go 언어의 Zero-Copy 기법: sendfile과 splice로 I/O 성능 최적화하기"
date = 2026-07-06T09:00:59+09:00
draft = false
tags = ["Golang", "Performance", "System Programming", "Zero-Copy", "Network"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# Go 언어의 Zero-Copy 기법: sendfile과 splice로 I/O 성능 최적화하기

최근 Hacker News를 통해 흥미로운 글을 보았습니다. 바로 **"Zero-copy in Go: sendfile, splice, and the cost of io.Copy"**입니다. 고성능 서버를 개발하거나, 대용량 파일 전송이 필요한 MCP 서버를 구축할 때, 메모리 복사(Memory Copy) 오버헤드는 무시할 수 없는 요소입니다.

오늘은 기존의 `io.Copy`가 가진 성능 문제를 분석하고, Go의 `sendfile` 시스템 콜을 활용하여 Zero-Copy를 구현하는 실용적인 방법을 소개합니다.

## 기존 방식의 문제점: io.Copy의 내부 작동

파일을 네트워크로 전송하는 가장 일반적인 Go 코드는 다음과 같습니다.

```go
// 전통적인 방식
func sendFile(w net.Conn, filePath string) error {
    file, _ := os.Open(filePath)
    defer file.Close()

    // io.Copy는 내부적으로 32KB 버퍼를 사용하여 읽고 씁니다.
    _, err := io.Copy(w, file)
    return err
}
```

이 코드는 간결하지만, 내부적으로는 **4번의 메모리 복사**와 **2번의 시스템 콜**이 발생합니다.

1.  **Disk → Kernel Buffer**: `read()` 시스템 콜을 통해 디스크 데이터를 커널 버퍼로 읽어옵니다.
2.  **Kernel Buffer → User Buffer**: 커널 버퍼에서 Go 애플리케이션(사용자 공간) 버퍼로 데이터를 복사합니다.
3.  **User Buffer → Kernel Socket Buffer**: 애플리케이션 버퍼에서 소켓 커널 버퍼로 다시 복사합니다.
4.  **Kernel Socket Buffer → NIC**: 네트워크 카드로 전송됩니다.

사용자 공간(User Space)을 데이터가 왕복해야 하므로, CPU 사이클 낭비와 캐시 미스(Cache Miss)가 발생하여 대용량 처리 시 병목이 됩니다.

## 해결책: Zero-Copy와 sendfile

Zero-Copy의 핵심은 **커널 공간(Kernel Space) 내에서 데이터를 직접 이동시켜, 사용자 공간을 거치지 않도록 하는 것**입니다.

리눅스는 이를 위해 `sendfile` 시스템 콜을 제공합니다.
1.  파일 데이터를 **Kernel File Buffer**로 읽어옵니다.
2.  **DMA(Direct Memory Access)** 엔진을 사용하여 데이터를 복사하지 않고 **Kernel Socket Buffer**의 주소만 참조하게 합니다 (또는 하드웨어에 직접 전달).
3.  사용자 공간 버퍼를 거치지 않습니다.

## Go에서의 실전 구현

Go 표준 라이브러리는 `io.Copy`의 대상이 `*os.File`일 때 자동으로 `sendfile`을 사용하도록 최적화되어 있지만, 구체적인 구현을 이해하고 조건을 맞추는 것이 중요합니다. 또한, 플랫폼 의존적인 코드를 직접 제어해야 할 수도 있습니다.

### 시나리오: HTTP 파일 서버 구현

간단한 HTTP 파일 서버를 통해 성능 차이를 비교해 보겠습니다.

```go
package main

import (
    "fmt"
    "io"
    "net/http"
    "os"
    "time"
)

// 1. 일반적인 io.Copy 사용 (User Space 거침)
func handlerCopy(w http.ResponseWriter, r *http.Request) {
    file, _ := os.Open("large_video.mp4") // 100MB 가정의 파일
    defer file.Close()

    start := time.Now()
    written, err := io.Copy(w, file)
    if err != nil {
        http.Error(w, "File Error", 500)
        return
    }
    duration := time.Since(start)
    fmt.Printf("[io.Copy] Sent %d bytes in %v\n", written, duration)
}

// 2. sendfile 시스템 콜 직접 사용 (Linux/Unix)
// Go의 net/http 패키지 내부적으로 http.ServeFile을 사용하면 최적화됨.
func handlerSendfile(w http.ResponseWriter, r *http.Request) {
    // http.ServeFile은 내부적으로 sendfile(리눅스)을 사용하여 최적화합니다.
    http.ServeFile(w, r, "large_video.mp4")
    fmt.Printf("[ServeFile] Sent via optimized system call\n")
}

func main() {
    http.HandleFunc("/copy", handlerCopy)
    http.HandleFunc("/sendfile", handlerSendfile)
    fmt.Println("Server running on :8080")
    http.ListenAndServe(":8080", nil)
}
```

위 코드에서 `http.ServeFile`은 내부적으로 운영체제가 리눅스인지 확인하고, 파일 디스크립터를 소켓 디스크립터로 직접 전송하는 시스템 콜을 시도합니다.

### 저수준 구현: syscall 패키지 활용

만약 표준 라이브러리의 도움 없이 직접 소켓 통신을 제어해야 한다면(예: 커스텀 프록시 개발), `syscall` 패키지를 사용할 수 있습니다. 다음은 개념적인 예시 코드입니다.

```go
// 주의: 운영체제 의존적이며 에러 처리가 복잡할 수 있습니다.
package main

import (
    "fmt"
    "net"
    "os"
    "syscall"
)

func zeroCopySend(file *os.File, conn net.Conn) error {
    // 1. 소켓의 파일 디스크립터 가져오기
    rawConn, err := conn.SyscallConn()
    if err != nil {
        return err
    }

    var sendErr error
    // 2. RawConn.Control을 통해 저수준 소켓 제어
    rawConn.Control(func(fd uintptr) {
        // 3. syscall.Sendfile 호출 (리눅스)
        // src: 파일 FD, dst: 소켓 FD
        _, sendErr = syscall.Sendfile(int(fd), int(file.Fd()), nil, 1024*1024) // 1MB 전송
    })

    return sendErr
}
```

> **참고:** Go 1.20+ 버전에서는 `io.Copy`의 구현이 개선되어, 일반적인 소켓과 파일 간 전송에서 자동으로 `splice`(리눅스)나 `sendfile`을 사용하도록 내부적으로 최적화되었습니다. 따라서, 대부분의 경우 **단순히 `io.Copy`를 사용하는 것만으로도 Zero-Copy 혜택을 누릴 수 있습니다.** 하지만 내부 원리를 알아야 예외 상황(예: 암호화 계층이 있는 경우)을 처리할 수 있습니다.

## 성능 비교 및 고려사항

### 성능 차이
*   **io.Copy (User Buffering):** CPU 사용량이 높으며, 대용량 전송 시 처리량(Throughput)이 하드웨어 성능에 미치지 못합니다.
*   **sendfile/splice (Zero-Copy):** CPU 사용량이 획기적으로 줄어들고, 처리량이 네트워크 대역폭에 근접하게 향상됩니다.

### 주의사항
Zero-Copy가 만능은 아닙니다.
1.  **데이터 수정 불가:** 데이터가 사용자 공간을 거치지 않으므로, 전송 중에 내용을 가공(암호화, 압축, 필터링)할 수 없습니다.
2.  **운영체제 의존성:** `sendfile`은 리눅스, BSD 계열에서 지원하지만, Windows에서는 다른 메커니즘(TransmitFile)을 사용합니다. Go는 이를 크로스 플랫폼으로 추상화해 주지만, 세부 동작은 OS에 따릅니다.

## 결론

고성능 서버, 특히 **이미지/동영상 스트리밍 서비스**나 **대용량 로그 전송 에이전트**를 개발할 때는 `io.Copy`가 내부적으로 어떻게 동작하는지 이해하는 것이 중요합니다.

단순히 `io.Copy(conn, file)`을 호출하는 것만으로도 최신 Go 런타임은 Zero-Copy를 시도합니다. 하지만 TLS나 암호화 레이어가 끼어있다면 이 최적화가 불가능하므로, 아키텍처 설계 시 데이터 가공 지점을 전송 지점 이전에 완료해 두는 등의 전략이 필요합니다.

Hacker News의 기사에서 언급했듯, "비용(Cost)"을 아는 것이 성능 최적화의 첫걸음입니다. 오늘 소개한 내용을 바탕으로 여러분의 Go 서버를 조금 더 효율적으로 개선해 보시길 권장합니다.

## 레퍼런스
*   [Zero-copy in Go: sendfile, splice, and the cost of io.Copy](https://medium.com/@felixge/io-copy-performance-improvements-in-go-1-20-8a43ebd8961f)
*   Go 1.20 Release Notes: Performance improvements for io.Copy
*   Linux Manual Page: sendfile(2)
