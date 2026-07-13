+++
title = "Tiny Emulators로 배우는 에뮬레이션 기초와 Rust로 구현하는 초경량 vCPU"
date = 2026-07-13T09:01:22+09:00
draft = false
tags = ["Rust", "Emulation", "TinyEmulator", "SystemProgramming", "Architecture"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# Tiny Emulators로 배우는 에뮬레이션 기초와 Rust로 구현하는 초경량 vCPU

최근 해커 뉴스 등 기술 커뮤니티에서 'Tiny Emulators'가 화두가 되고 있습니다. 단순히 오락용 게임기를 돌리는 것을 넘어, 복잡한 소프트웨어 스택을 최소한의 코드로 검증하고, 아키텍처를 이해하는 최고의 학습 도구로 떠오르고 있기 때문입니다.

특히 'Old and new apps, via modern coding agents'라는 트렌드처럼, AI 에이전트가 레거시 코드를 분석하거나 새로운 환경에 배포할 때, 에뮬레이터는 안전한 샌드박스(Sandbox) 역할을 합니다. 이번 포스트에서는 가장 간단한 형태의 에뮬레이터를 직접 Rust로 설계하며 시스템 프로그래밍과 아키텍처의 핵심을 파헤쳐 보겠습니다.

## 1. 에뮬레이터란 무엇인가?

에뮬레이터(Emulator)는 특정 하드웨어(CPU, 메모리, I/O)를 소프트웨어로 모방하는 프로그램입니다. 우리가 흔히 쓰는 도커(Docker)나 가상머신(VM)과 비슷하지만, 에뮬레이터는 하드웨어의 명령어 세트(Instruction Set Architecture, ISA) 자체를 소프트웨어로 해석한다는 점이 다릅니다.

*   **인터프리터(Interpreter):** 명령어를 하나씩 읽어 해석하고 실행합니다. (구현 쉬움, 속도 느림)
*   **JIT (Just-In-Time) Compiler:** 실행 시점에 기계어로 번역하여 실행합니다. (구현 어려움, 속도 빠름)

'Claude Code'나 'GPT-5.6' 같은 최신 모델이 코드를 실행할 때 에뮬레이션을 활용하는 것은, 실제 환경을 오염시키지 않고 빠르게 피드백을 얻기 위해서입니다. 우리는 이 중 가장 기초가 되는 **바이너리 인터프리터**를 만들어보겠습니다.

## 2. 아키텍처 설계: vCPU 구조 정의

복잡한 x86이나 ARM 대신, 학습을 위해 단순화된 **Custom ISA**를 설계해 보겠습니다.

*   **데이터 폭:** 8비트 (0~255)
*   **레지스터:** 2개 (A, B)
*   **명령어 세트:**
    *   `MOV`: 데이터 이동
    *   `ADD`: 덧셈
    *   `SUB`: 뺄셈
    *   `JMP`: 분기 (Jump)
    *   `HLT`: 정지 (Halt)

이것만으로도 튜링 완전(Turing Complete)한 계산이 가능합니다.

## 3. Rust로 구현하기

Rust는 안전성(Safety)과 성능, 그리고 훌륭한 타입 시스템 덕분에 에뮬레이터 제작에 최적의 언어입니다. `match` 문을 통해 명령어를 디스패치(Dispatch)하는 과정은 CPU의 회로 동작을 소프트웨어적으로 모사하는 것과 같습니다.

### 3.1. 기본 구조체 정의

먼저 CPU의 상태(State)를 저장할 구조체를 정의합니다.

```rust
#[derive(Debug, Default)]
pub struct TinyCPU {
    // 범용 레지스터
    reg_a: u8,
    reg_b: u8,
    // 프로그램 카운터 (다음 실행할 명령어의 주소)
    pc: usize,
    // 메모리 (간단한 배열로 구현)
    memory: [u8; 256],
    // 실행 중지 플래그
    halted: bool,
}
```

### 3.2. 명령어(OpCode) 정의

명령어는 `u8` 정수로 매핑합니다.

```rust
#[derive(Debug, PartialEq)]
enum OpCode {
    MOV = 0, // 0: Move val to A
    ADD = 1, // 1: Add val to A
    SUB = 2, // 2: Sub val from A
    JMP = 3, // 3: Jump to address
    HLT = 4, // 4: Halt
    UNKNOWN,
}

impl From<u8> for OpCode {
    fn from(byte: u8) -> Self {
        match byte {
            0 => OpCode::MOV,
            1 => OpCode::ADD,
            2 => OpCode::SUB,
            3 => OpCode::JMP,
            4 => OpCode::HLT,
            _ => OpCode::UNKNOWN,
        }
    }
}
```

### 3.3. 실행 로직 (Fetch-Decode-Execute)

CPU의 핵심 싸이클인 **Fetch(인출) -> Decode(해석) -> Execute(실행)** 과정을 구현합니다.

```rust
impl TinyCPU {
    pub fn new() -> Self {
        Self::default()
    }

    // 바이너리 코드를 메모리에 로드
    pub fn load_program(&mut self, code: &[u8]) {
        // 안전한 복사를 위해 이터레이터 사용
        for (i, &byte) in code.iter().enumerate() {
            if i < self.memory.len() {
                self.memory[i] = byte;
            }
        }
    }

    // 한 사이클 실행
    pub fn step(&mut self) {
        if self.halted {
            return;
        }

        // 1. Fetch: PC 위치의 명령어 가져오기
        let raw_opcode = self.memory[self.pc];
        let opcode = OpCode::from(raw_opcode);
        self.pc += 1; // PC 진행

        // 2. Decode & Execute
        match opcode {
            OpCode::MOV => {
                // MOV 다음 바이트는 Operand(값)라고 가정
                let val = self.memory[self.pc];
                self.pc += 1;
                self.reg_a = val;
                println!("[MOV] A <= {}", val);
            }
            OpCode::ADD => {
                let val = self.memory[self.pc];
                self.pc += 1;
                self.reg_a = self.reg_a.wrapping_add(val);
                println!("[ADD] A = A + {} (A: {})", val, self.reg_a);
            }
            OpCode::SUB => {
                let val = self.memory[self.pc];
                self.pc += 1;
                self.reg_a = self.reg_a.wrapping_sub(val);
                println!("[SUB] A = A - {} (A: {})", val, self.reg_a);
            }
            OpCode::JMP => {
                let addr = self.memory[self.pc];
                self.pc = addr as usize; // PC를 주소로 변경
                println!("[JMP] PC <= {}", addr);
            }
            OpCode::HLT => {
                self.halted = true;
                println!("[HLT] System Stopped.");
            }
            OpCode::UNKNOWN => {
                println!("Error: Unknown Opcode at PC {}", self.pc - 1);
                self.halted = true;
            }
        }
    }

    // 루프 실행
    pub fn run(&mut self) {
        while !self.halted {
            self.step();
            // 무한 루프 방지를 위한 안전장치 (실제 에뮬레이터에선 인터럽트로 처리)
            if self.pc >= self.memory.len() {
                break;
            }
        }
        println!("Final State: A={}, B={}, PC={}", self.reg_a, self.reg_b, self.pc);
    }
}
```

## 4. 테스트: '5 더하기 3' 프로그램 작성

이제 우리가 만든 vCPU가 `5 + 3 = 8`을 수행하는 바이너리를 작성해 봅시다.

*   `MOV 5`: A 레지스터에 5 저장
*   `ADD 3`: A 레지스터에 3 더하기
*   `HLT`: 정지

이를 바이트 코드로 변환하면 다음과 같습니다.

```rust
fn main() {
    let mut cpu = TinyCPU::new();

    // 프로그램 작성: 5를 넣고, 3을 더하고, 멈춘다.
    // OpCode::MOV(0), 5
    // OpCode::ADD(1), 3
    // OpCode::HLT(4)
    let program: Vec<u8> = vec![
        0, 5, // MOV 5
        1, 3, // ADD 3
        4     // HLT
    ];

    println!("=== Tiny Emulator Boot ===");
    cpu.load_program(&program);
    cpu.run();
}
```

### 실행 결과

```text
=== Tiny Emulator Boot ===
[MOV] A <= 5
[ADD] A = A + 3 (A: 8)
[HLT] System Stopped.
Final State: A=8, B=0, PC=5
```

## 5. 확장 가능성 및 결론

이 50줄 남짓한 코드가 에뮬레이션의 본질입니다. 여기서 다음과 같은 기능을 추가하면 실제 복잡한 시스템으로 확장할 수 있습니다.

1.  **스택(Stack) 포인터와 함수 호출:** `CALL`, `RET` 명령어를 추가하여 재귀 호출 구현.
2.  **메모리 매핑 I/O:** 키보드 입력이나 화면 출력을 메모리 주소에 연결.
3.  **Rust의 `Box` 활용:** 동적 메모리 할당을 통해 힙 메모리 영역 구현.

최근 'MCP(Multi-Agent Communication Protocol)' 관련 글에서 언급된 것처럼, 작고 독립적인 컴포넌트(여기서는 TinyCPU)는 더 큰 시스템(예: AI 에이전트의 코드 실행 환경)의 부품으로 사용될 수 있습니다.

오늘 작성한 코드는 복잡한 OS에 의존하지 않고 논리만으로 동작하는 순수한 로직의 결정체입니다. 이러한 원초적인 아키텍처를 이해하는 것은 'Migrating a production AI agent'와 같은 고도화된 작업을 수행할 때도, 하부에서 일어나는 연산의 비용(Cost)과 메커니즘을 이해하는 데 큰 도움이 될 것입니다.

전체 소스 코드는 GitHub 저장소에 공유되어 있으니 직접 실행해 보시기 바랍니다.
