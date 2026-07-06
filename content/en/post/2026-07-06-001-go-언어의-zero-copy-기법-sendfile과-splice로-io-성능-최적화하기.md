+++
title = "Go's Zero-Copy Technique: Optimizing I/O Performance with sendfile and splice"
date = "2026-07-06T09:00:59+09:00"
draft = "false"
tags = ["Golang", "Performance", "System Programming", "Zero-Copy", "Network"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

# Go's Zero-Copy Technique: Optimizing I/O Performance with sendfile and splice

Recently, I came across an interesting article on Hacker News titled **"Zero-copy in Go: sendfile, splice, and the cost of io.Copy"**. When developing high-performance servers or building MCP servers that require large file transfers, the overhead of memory copying is a factor that cannot be ignored.

Today, we will analyze the performance issues of the existing `io.Copy` and introduce practical methods for implementing Zero-Copy using Go's `sendfile` system call.

## Problems with the Traditional Approach: Internal workings of io.Copy

The most common Go code for sending files over a network looks like this:

```go
// Traditional approach
func sendFile(w net.Conn, filePath string) error {
    file, _ := os.Open(filePath)
    defer file.Close()

    // io.Copy internally reads and writes using a 32KB buffer.
    _, err := io.Copy(w, file)
    return err
}
```

This code is concise, but internally it involves **four memory copies** and **two system calls**.

1.  **Disk → Kernel Buffer**: Reads disk data into the kernel buffer via the `read()` system call.
2.  **Kernel Buffer → User Buffer**: Copies data from the kernel buffer to the Go application's (user space) buffer.
3.  **User Buffer → Kernel Socket Buffer**: Copies data again from the application buffer to the socket kernel buffer.
4.  **Kernel Socket Buffer → NIC**: Transmitted to the network card.

Since data has to travel back and forth through user space, CPU cycles are wasted, and cache misses occur, creating a bottleneck when processing large amounts of data.

## The Solution: Zero-Copy and sendfile

The core of Zero-Copy is to **move data directly within the kernel space, bypassing user space**.

Linux provides the `sendfile` system call for this purpose.
1.  File data is read into the **Kernel File Buffer**.
2.  Using the **DMA (Direct Memory Access)** engine, instead of copying data, only the address of the **Kernel Socket Buffer** is referenced (or directly passed to hardware).
3.  User space buffers are not involved.

## Practical Implementation in Go

The Go standard library is optimized to automatically use `sendfile` when the destination of `io.Copy` is an `*os.File`. However, it's important to understand the specific implementation and meet the conditions. You may also need to control platform-dependent code directly.

### Scenario: Implementing an HTTP File Server

Let's compare the performance difference by implementing a simple HTTP file server.

```go
package main

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

// 1. Using regular io.Copy (passes through User Space)
func handlerCopy(w http.ResponseWriter, r *http.Request) {
	file, _ := os.Open("large_video.mp4") // Assume a 100MB file
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

// 2. Directly using the sendfile system call (Linux/Unix)
// The Go net/http package optimizes this when http.ServeFile is used internally.
func handlerSendfile(w http.ResponseWriter, r *http.Request) {
	// http.ServeFile internally optimizes by using sendfile (on Linux).
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

In the code above, `http.ServeFile` checks if the operating system is Linux and attempts to use a system call to transfer the file descriptor directly to the socket descriptor.

### Low-Level Implementation: Using the syscall Package

If you need to control socket communication directly without the help of the standard library (e.g., developing a custom proxy), you can use the `syscall` package. Here is a conceptual example:

```go
// Warning: This is OS-dependent and error handling can be complex.
package main

import (
	"fmt"
	"net"
	"os"
	"syscall"
)

func zeroCopySend(file *os.File, conn net.Conn) error {
	// 1. Get the file descriptor of the socket
	rawConn, err := conn.SyscallConn()
	if err != nil {
		return err
	}

	var sendErr error
	// 2. Control the low-level socket via RawConn.Control
	rawConn.Control(func(fd uintptr) {
		// 3. Call syscall.Sendfile (Linux)
		// src: file FD, dst: socket FD
		_, sendErr = syscall.Sendfile(int(fd), int(file.Fd()), nil, 1024*1024) // Transfer 1MB
	})

	return sendErr
}
```

> **Note:** In Go 1.20+, the implementation of `io.Copy` has been improved. For typical socket-to-file transfers, it automatically uses `splice` (on Linux) or `sendfile` internally. Therefore, in most cases, **simply calling `io.Copy` will provide Zero-Copy benefits.** However, understanding the internal workings is necessary to handle exceptional situations (e.g., when there's an encryption layer).

## Performance Comparison and Considerations

### Performance Difference
*   **io.Copy (User Buffering):** High CPU usage, and throughput during large transfers does not reach hardware limits.
*   **sendfile/splice (Zero-Copy):** Drastically reduces CPU usage, and throughput approaches network bandwidth.

### Precautions
Zero-Copy is not a silver bullet.
1.  **Data Modification Impossible:** Since data does not pass through user space, its content cannot be manipulated (encrypted, compressed, filtered) during transmission.
2.  **Operating System Dependency:** `sendfile` is supported on Linux and BSD-based systems, but Windows uses a different mechanism (TransmitFile). Go abstracts this for cross-platform compatibility, but the detailed behavior depends on the OS.

## Conclusion

When developing high-performance servers, especially for **image/video streaming services** or **large log transfer agents**, it is important to understand how `io.Copy` works internally.

Simply calling `io.Copy(conn, file)` will prompt the latest Go runtime to attempt Zero-Copy. However, if a TLS or encryption layer is involved, this optimization is not possible. Therefore, in architectural design, strategies such as completing data processing *before* the transmission point are necessary.

As mentioned in the Hacker News article, knowing the "cost" is the first step to performance optimization. Based on what we've covered today, I recommend improving your Go server to be a bit more efficient.

## References
*   [Zero-copy in Go: sendfile, splice, and the cost of io.Copy](https://medium.com/@felixge/io-copy-performance-improvements-in-go-1-20-8a43ebd8961f)
*   Go 1.20 Release Notes: Performance improvements for io.Copy
*   Linux Manual Page: sendfile(2)
```