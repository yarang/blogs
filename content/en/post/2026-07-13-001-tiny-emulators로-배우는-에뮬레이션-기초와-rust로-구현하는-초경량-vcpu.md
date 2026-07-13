+++
title = "Learning Emulation Fundamentals with Tiny Emulators and Implementing a Lightweight vCPU with Rust"
date = "2026-07-13T09:01:22+09:00"
draft = "false"
tags = ["Rust", "Emulation", "TinyEmulator", "SystemProgramming", "Architecture"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

# Learning Emulation Fundamentals with Tiny Emulators and Implementing a Lightweight vCPU with Rust

Recently, 'Tiny Emulators' have become a hot topic in tech communities like Hacker News. This is because they are emerging not just for running recreational game consoles, but as excellent learning tools for verifying complex software stacks with minimal code and understanding architectures.

Especially with the trend of 'Old and new apps, via modern coding agents,' emulators serve as safe sandboxes when AI agents analyze legacy code or deploy to new environments. In this post, we will delve into the core of system programming and architecture by designing the simplest form of an emulator directly in Rust.

## 1. What is an Emulator?

An emulator is a program that mimics specific hardware (CPU, memory, I/O) in software. It's similar to Docker or Virtual Machines (VMs) that we commonly use, but the difference is that emulators interpret the hardware's Instruction Set Architecture (ISA) itself in software.

*   **Interpreter:** Reads and executes instructions one by one. (Easy to implement, slow execution)
*   **JIT (Just-In-Time) Compiler:** Translates to machine code at runtime for execution. (Difficult to implement, fast execution)

The reason why the latest models like 'Claude Code' or 'GPT-5.6' utilize emulation when executing code is to get fast feedback without polluting the actual environment. We will create the most basic form: a **binary interpreter**.

## 2. Architecture Design: Defining the vCPU Structure

Instead of complex x86 or ARM, we will design a simplified **Custom ISA** for learning.

*   **Data Width:** 8-bit (0~255)
*   **Registers:** 2 (A, B)
*   **Instruction Set:**
    *   `MOV`: Data movement
    *   `ADD`: Addition
    *   `SUB`: Subtraction
    *   `JMP`: Branch (Jump)
    *   `HLT`: Halt

Even with just these, Turing Complete computation is possible.

## 3. Implementation with Rust

Rust is an optimal language for emulator development due to its safety, performance, and excellent type system. The process of dispatching instructions using the `match` statement is akin to simulating the operation of CPU circuits in software.

### 3.1. Defining Basic Structures

First, we define a struct to store the CPU's state.

```rust
#[derive(Debug, Default)]
pub struct TinyCPU {
    // General-purpose registers
    reg_a: u8,
    reg_b: u8,
    // Program Counter (address of the next instruction to execute)
    pc: usize,
    // Memory (implemented as a simple array)
    memory: [u8; 256],
    // Execution halt flag
    halted: bool,
}
```

### 3.2. Defining Instructions (OpCode)

Instructions are mapped to `u8` integers.

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

### 3.3. Execution Logic (Fetch-Decode-Execute)

We implement the core CPU cycle: **Fetch -> Decode -> Execute**.

```rust
impl TinyCPU {
    pub fn new() -> Self {
        Self::default()
    }

    // Loads binary code into memory
    pub fn load_program(&mut self, code: &[u8]) {
        // Use an iterator for safe copying
        for (i, &byte) in code.iter().enumerate() {
            if i < self.memory.len() {
                self.memory[i] = byte;
            }
        }
    }

    // Executes one cycle
    pub fn step(&mut self) {
        if self.halted {
            return;
        }

        // 1. Fetch: Get instruction at PC
        let raw_opcode = self.memory[self.pc];
        let opcode = OpCode::from(raw_opcode);
        self.pc += 1; // Increment PC

        // 2. Decode & Execute
        match opcode {
            OpCode::MOV => {
                // Assume the next byte is the Operand (value)
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
                self.pc = addr as usize; // Set PC to the address
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

    // Runs the loop
    pub fn run(&mut self) {
        while !self.halted {
            self.step();
            // Safety measure to prevent infinite loops (in a real emulator, this would be handled by interrupts)
            if self.pc >= self.memory.len() {
                break;
            }
        }
        println!("Final State: A={}, B={}, PC={}", self.reg_a, self.reg_b, self.pc);
    }
}
```

## 4. Testing: Writing a '5 plus 3' Program

Now let's write a binary for our vCPU to perform `5 + 3 = 8`.

*   `MOV 5`: Store 5 in register A
*   `ADD 3`: Add 3 to register A
*   `HLT`: Halt

Converting this to byte code:

```rust
fn main() {
    let mut cpu = TinyCPU::new();

    // Program: Load 5, add 3, then stop.
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

### Execution Result

```text
=== Tiny Emulator Boot ===
[MOV] A <= 5
[ADD] A = A + 3 (A: 8)
[HLT] System Stopped.
Final State: A=8, B=0, PC=5
```

## 5. Extensibility and Conclusion

This code of just over 50 lines is the essence of emulation. You can extend it into a real, complex system by adding features such as:

1.  **Stack Pointer and Function Calls:** Implement recursive calls by adding `CALL` and `RET` instructions.
2.  **Memory-Mapped I/O:** Connect keyboard input or screen output to memory addresses.
3.  **Using Rust's `Box`:** Implement a heap memory area through dynamic memory allocation.

As mentioned in recent articles about 'MCP (Multi-Agent Communication Protocol),' small, independent components (like TinyCPU here) can be used as parts of larger systems (e.g., environments for AI agents to execute code).

The code written today is a pure logical construct operating solely on logic, without relying on complex operating systems. Understanding such fundamental architectures will be of great help in understanding the cost and mechanisms of operations happening underneath when performing advanced tasks like 'Migrating a production AI agent.'

The full source code is shared in the GitHub repository, so please try running it yourself.

```