+++
title = "[MicroVM] Firecracker를 활용한 고립형 샌드박스 구축 가이드"
date = 2026-06-27T09:01:26+09:00
draft = false
tags = ["Rust", "Firecracker", "MicroVM", "DevOps", "Security"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# [MicroVM] Firecracker를 활용한 고립형 샌드박스 구축 가이드

최근 **MicroVM** 기술이 주목받고 있습니다. 전통적인 컨테이너(Docker 등)는 커널을 호스트와 공유하기 때문에 보안 격리(Isolation) 측면에서 완벽하다고 할 수 없습니다. 반면, AWS의 Firecracker와 같은 MicroVM은 가벼운 가상머신을 제공하여 '컨테이너의 속도'와 'VM의 보안'을 동시에 잡을 수 있습니다.

이번 글에서는 Rust 기반 에이전트 런타임인 ZeroClaw의 통신 프로토콜 설계 과정에서 고려한 **Firecracker MicroVM**을 사용하여, 신뢰할 수 없는 코드를 안전하게 실행하는 방법을 실용적인 코드와 함께 소개합니다.

## 왜 MicroVM인가?

기존의 블로그 API 서버나 MCP(Model Context Protocol) 클라이언트 개발에서는 주로 컨테이너 환경을 사용했습니다. 하지만 멀티 에이전트 시스템이나 외부 코드를 실행해야 하는 환경에서는 보안이 더욱 중요해집니다. 

*   **단일 프로세스 격리:** 각 MicroVM은 독립적인 커널 공간을 가집니다.
*   **빠른 부팅:** 밀리초 단위의 부팅 시간으로 컨테이너와 유사한 속도를 냅니다.
*   **리소스 제한:** CPU 및 메모리 사용량을 엄격하게 제한할 수 있습니다.

## 사전 준비 사항

이 가이드를 따라하려면 Linux 환경(KVM 활성화)과 Rust 툴체인이 필요합니다. Firecracker는 Linux KVM(Kernel-based Virtual Machine) 위에서 동작합니다.

```bash
# KVM 권한 확인
ls -la /dev/kvm
# 그룹에 추가 (권한이 없는 경우)
sudo usermod -aG kvm $USER
```

## 1. Firecracker 다운로드 및 준비

Firecracker는 단일 바이너리로 제공되어 배포가 매우 간편합니다.

```bash
cd /tmp
curl -L -o firecracker-v1.9.1 https://github.com/firecracker-microvm/firecracker/releases/download/v1.9.1/firecracker-v1.9.1-x86_64
chmod +x firecracker-v1.9.1
mv firecracker-v1.9.1 firecracker
```

## 2. MicroVM 부팅을 위한 루트 파일시스템 생성

MicroVM을 실행하려면 간단한 Linux 커널과 루트 파일시스템(이미지)이 필요합니다. 테스트를 위해 Ubuntu 이미지를 다운로드하겠습니다.

```bash
# 작업 디렉토리 생성
mkdir -p fc-demo
cd fc-demo

# Ubuntu 22.04 루트 파일시스템 다운로드
wget https://cloud-images.ubuntu.com/releases/22.04/release/ubuntu-22.04-server-cloudimg-amd64-root.tar.xz

# 이미지 변환 (raw 형식)
xz -d ubuntu-22.04-server-cloudimg-amd64-root.tar.xz
```

## 3. Rust로 제어 로직 작성하기

이제 Rust를 사용하여 Firecracker 인스턴스를 구동하고, 네트워크를 설정하며, 요청을 보내보겠습니다. `serde_json`을 사용하여 설정을 JSON으로 전달하는 방식이 가장 일반적입니다.

**Cargo.toml dependencies:**

```toml
[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
reqwest = { version = "0.12", features = ["blocking"] }
```

**Rust 구현 코드 (`main.rs`):**

```rust
use std::fs::{self, File};
use std::io::Write;
use std::process::{Command, Stdio};
use serde::Serialize;

// Firecracker 설정 구조체
#[derive(Serialize)]
struct BootSource {
    kernel_image_path: String,
    boot_args: String,
}

#[derive(Serialize)]
struct Drive {
    drive_id: String,
    path_on_host: String,
    is_root_device: bool,
    is_read_only: bool,
}

#[derive(Serialize)]
struct MachineConfig {
    vcpu_count: u8,
    mem_size_mib: u64,
    ht_enabled: bool,
}

#[derive(Serialize)]
struct NetworkInterface {
    if_id: String,
    guest_mac: String,
    host_dev_name: String,
}

fn main() {
    // 1. 작업 디렉토리 설정
    let vm_id = "my-first-microvm";
    fs::create_dir_all(format!("/tmp/fc-demo/{}", vm_id)).expect("Failed to create vm dir");

    // 2. Firecracker 프로세스 실행 (백그라운드)
    // 실제 환경에서는 데몬으로 관리하거나 API를 통해 소켓을 생성합니다.
    // 여기서는 간단히 API 서버를 소켓으로 실행한다고 가정하고 설정을 전송합니다.
    
    // 주의: 실제 실행하려면 커널 이미지(vmlinux)가 필요합니다. 
    // AWS Firecracker GitHub 릴리즈에서 다운로드 가능합니다.
    let kernel_path = "/tmp/fc-demo/vmlinux"; // 경로 확인 필요
    let rootfs_path = "/tmp/fc-demo/ubuntu-22.04-server-cloudimg-amd64-root.tar";

    // (실제 튜토리얼에서는 네트워크 설정이 복잡하므로 TAP 디바이스 생성 생략)
    // API 설정 생성 예시
    let boot_config = BootSource {
        kernel_image_path: kernel_path.to_string(),
        boot_args: "console=ttyS0 reboot=k panic=1 pci=off".to_string(),
    };

    let drive_config = Drive {
        drive_id: "rootfs".to_string(),
        path_on_host: rootfs_path.to_string(),
        is_root_device: true,
        is_read_only: false,
    };

    // JSON 파일로 설정 저장 (Firecracker는 HTTP API나 JSON 파일 입력을 받음)
    let config_json = serde_json::to_string_pretty(&vec![&boot_config, &drive_config]).unwrap();
    let mut file = File::create(format!("/tmp/fc-demo/{}/vm_config.json", vm_id)).unwrap();
    file.write_all(config_json.as_bytes()).unwrap();

    println!("MicroVM 설정 완료: {}", vm_id);
    println!("Firecracker는 보통 TAP 네트워크와 마운트 설정이 필요합니다.");
    println!("CLI 사용법 예시:");
    println!("./firecracker --api-sock /tmp/fc-demo/{}/api.sock", vm_id);
    println!("이후 curl을 통해 http://localhost/... 로 설정을 전송합니다.");
}
```

## 4. 실행 및 제어 (CLI 방식)

Rust 코드로 자동화하는 것이 이상적이지만, 개발 단계에서는 CLI로 직접 제어하며 동작을 확인하는 것이 좋습니다.

```bash
# 1. TAP 네트워크 인터페이스 생성 (호스트와 게스트 연결용)
sudo ip tuntap add tap0 mode tap
sudo ip addr add 169.254.0.1/30 dev tap0
sudo ip link set tap0 up

# 2. Firecracker 실행 (API 소켓 모드)
./firecracker --api-sock /tmp/fc-demo/my-api.sock &

# 3. 부팅 소스 설정 전송
curl --unix-socket /tmp/fc-demo/my-api.sock -i \
     -X PUT 'http://localhost/boot-source' \
     -H 'Accept: application/json' \
     -H 'Content-Type: application/json' \
     -d '{
        "kernel_image_path": "/path/to/vmlinux",
        "boot_args": "console=ttyS0 reboot=k panic=1 pci=off"
      }'

# 4. 마운트 설정 전송
curl --unix-socket /tmp/fc-demo/my-api.sock -i \
     -X PUT 'http://localhost/drives/rootfs' \
     -H 'Accept: application/json' \
     -H 'Content-Type: application/json' \
     -d '{
        "drive_id": "rootfs",
        "path_on_host": "/path/to/rootfs.ext4",
        "is_root_device": true,
        "is_read_only": false
      }'
      
# 5. 인스턴스 시작
curl --unix-socket /tmp/fc-demo/my-api.sock -i \
     -X PUT 'http://localhost/actions' \
     -H 'Accept: application/json' \
     -H 'Content-Type: application/json' \
     -d '{ "action_type": "InstanceStart" }'
```

## 결론 및 ZeroClaw 적용 계획

위에서 살펴본 것처럼 MicroVM은 강력한 격리성을 제공합니다. **ZeroClaw** 프로젝트의 '멀티 에이전트 아키텍처'에서 이 기술은 매우 유용합니다. 각 에이전트가 수행하는 작업(예: 파일 시스템 접근, 외부 네트워크 요청)을 독립된 Firecracker 인스턴스 내에서 실행하게 하여, 시스템 전체의 안정성을 해치지 않고 '신뢰할 수 없는 플러그인'을 실행할 수 있게 됩니다.

다음 포스트에서는 이 MicroVM 위에서 동작하는 에이전트 간의 통신을 어떻게 최적화할지에 대해 다루겠습니다.

## 참고자료

- [Firecracker GitHub](https://github.com/firecracker-microvm/firecracker)
- [MicroVMs: Run isolated sandboxes with full lifecycle control](Hacker News Link)
- [ZeroClaw 아키텍처 설계문서](내부 블로그 링크)