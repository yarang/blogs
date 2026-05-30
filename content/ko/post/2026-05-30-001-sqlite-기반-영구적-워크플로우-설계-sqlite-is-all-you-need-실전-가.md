+++
title = "SQLite 기반 영구적 워크플로우 설계: 'SQLite is all you need' 실전 가이드"
date = 2026-05-30T09:00:30+09:00
draft = false
tags = ["SQLite", "Workflow", "Rust", "DurableExecution", "Architecture"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# SQLite로 워크플로우를 지속 가능하게 만드는 방법

최근 Hacker News에서 "SQLite is all you need for durable workflows"라는 글이 큰 화제가 되었습니다. 분산 시스템을 설계할 때 Kafka, Redis, 복잡한 클러스터링을 떠올리기 쉽지만, 정작 우리가 해결하려는 핵심 문제인 '상태 유지(State Management)'와 '재시작 내성(Resiliency)'은 단일 파일 데이터베이스인 SQLite만으로도 충분히 해결할 수 있다는 주장입니다.

저희 팀의 'ZeroClaw'나 'Discord Decision MCP'와 같은 에이전트 시스템을 개발하면서, 복잡한 메시지 큐를 도입하기 전에 SQLite의 가벼우면서도 강력한 트랜잭션 기능을 활용해 워크플로우 엔진을 직접 구현해 보았습니다. 이 글에서는 그 핵심 아키텍처와 실제 코드 예제를 공유합니다.

## 1. 영구적 워크플로우(Durable Workflow)란?

워크플로우가 '영구적'이다 한다는 것은, 프로그램이 죽거나 서버가 재시작되더라도 중단된 지점부터 다시 시작할 수 있음을 의미합니다. 이를 위해 우리는 다음 두 가지를 보장해야 합니다.

1.  **상태 저장(Snapshotting):** 현재 진행 상황을 지속적으로 저장해야 합니다.
2.  **정확히 한 번 실행(Exactly-Once Semantics):** 재시작 시 중복 실행을 방지해야 합니다.

## 2. 아키텍처 설계: SQLite를 큐와 상태 저장소로 사용하기

SQLite는 `WAL(Write-Ahead Logging)` 모드와 고급 잠금 메커니즘 덕분에 동시성 환경에서도 놀라운 성능을 냅니다. 워크플로우 엔진은 다음과 같은 테이블 구조를 기반으로 동작합니다.

### 데이터베이스 스키마

```sql
-- 작업의 현재 상태를 저장하는 테이블
CREATE TABLE workflows (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL, -- pending, running, completed, failed
    current_step INTEGER NOT NULL DEFAULT 0,
    payload TEXT,         -- JSON 형태의 입력 데이터
    updated_at INTEGER NOT NULL
);

-- 실행해야 할 작업 목록 (큐)
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    target_step INTEGER NOT NULL,
    run_at INTEGER,       -- 예약 실행 시간 (NULL 즉시 실행)
    FOREIGN KEY(workflow_id) REFERENCES workflows(id)
);

CREATE INDEX idx_jobs_run_at ON jobs(run_at);
```

### Rust 구현 예제

Rust의 `rusqlite` 라이브러리를 사용하여 간단한 워크플로우 스케줄러를 작성해 보겠습니다. 이 코드는 'ZeroClaw' 런타임의 가벼운 작업 스케줄링 로직에서 영감을 받았습니다.

```rust
use rusqlite::{Connection, Result, params};
use std::time::{Duration, SystemTime};

fn main() -> Result<()> {
    // 1. 메모리 또는 파일 DB 연결 (WAL 모드 활성화 권장)
    let mut conn = Connection::open("workflow.db")?;
    conn.execute_batch("PRAGMA journal_mode=WAL;")?;

    // 2. 워크플로우 생성 (초기 상태)
    let workflow_id = "order-12345";
    insert_workflow(&mut conn, workflow_id, "{\"item\": \"keyboard\"}")?;

    // 3. 작업 예약 (결제 단계)
    enqueue_job(&mut conn, workflow_id, 1, None)?;

    // 4. 워커 루프 (실무에서는 데몬화)
    loop {
        match fetch_next_job(&mut conn)? {
            Some(job) => {
                println!("Processing job {} for workflow {}", job.target_step, job.workflow_id);
                
                // 비즈니스 로직 실행 (예: LLM 호출, 외부 API 요청)
                // simulate_work();

                // 성공 시 다음 스텝 예약 또는 완료 처리
                complete_step(&mut conn, &job.workflow_id, job.target_step)?;
            }
            None => {
                println!("No jobs, sleeping...");
                std::thread::sleep(Duration::from_secs(5));
            }
        }
    }
}

// 작업을 큐에 넣고, 워크플로우 상태를 'pending'으로 업데이트하는 트랜잭션
fn enqueue_job(conn: &mut Connection, workflow_id: &str, step: i32, delay: Option<SystemTime>) -> Result<()> {
    let tx = conn.transaction()?;
    
    tx.execute(
        "INSERT INTO jobs (workflow_id, target_step, run_at) VALUES (?1, ?2, ?3)",
        params![workflow_id, step, delay.and_then(|t| Some(t.duration_since(SystemTime::UNIX_EPOCH).unwrap().as_secs()))]
    )?;

    tx.execute(
        "UPDATE workflows SET status = 'pending', updated_at = ?1 WHERE id = ?2",
        params![SystemTime::now().duration_since(SystemTime::UNIX_EPOCH).unwrap().as_secs(), workflow_id]
    )?;

    tx.commit()
}

// 다음 처리할 작업을 가져오는 함수 (Locking Read)
fn fetch_next_job(conn: &mut Connection) -> Result<Option<Job>> {
    // UPDATE 문을 통해 행을 잠그고 반환하는 기법 (UPDATE RETURNING)
    // SQLite 3.35.0 이상 지원
    let mut stmt = conn.prepare(
        "UPDATE jobs 
         SET workflow_id = workflow_id || ':processing' -- 임시 상태 표시 (실제로는 status 컬럼 추천)
         WHERE rowid IN (
             SELECT rowid FROM jobs 
             WHERE run_at IS NULL OR run_at <= strftime('%s', 'now')
             LIMIT 1
         )
         RETURNING id, workflow_id, target_step;"
    )?;

    let mut rows = stmt.query(params![])?;
    match rows.next()? {
        Some(row) => Ok(Some(Job {
            id: row.get(0)?,
            workflow_id: row.get(1)?,
            target_step: row.get(2)?,
        })),
        None => Ok(None),
    }
}

// 스템 완료 처리
fn complete_step(conn: &mut Connection, workflow_id: &str, step: i32) -> Result<()> {
    let tx = conn.transaction()?;
    
    // 완료된 작업 삭제
    tx.execute("DELETE FROM jobs WHERE workflow_id = ?1 AND target_step = ?2", params![workflow_id, step])?;
    
    // 워크플로우 상태 업데이트 (다음 단계로)
    tx.execute(
        "UPDATE workflows SET current_step = ?1, updated_at = ?2 WHERE id = ?3",
        params![step + 1, SystemTime::now().duration_since(SystemTime::UNIX_EPOCH).unwrap().as_secs(), workflow_id]
    )?;
    
    tx.commit()
}

struct Job {
    id: i64,
    workflow_id: String,
    target_step: i64,
}
```

## 3. 왜 이 구조가 강력한가?

이 접근 방식의 가장 큰 장점은 **관리 부하(Ops Overhead)가 거의 없다는 점**입니다.

*   **ZeroClaw와 같은 에이전트 시스템**에서는 각 에이전트가 자신의 SQLite 파일을 가지고 동작하므로, 중앙 집중식 DB의 병목 현상을 피할 수 있습니다.
*   **Discord MCP** 같은 봇을 만들 때, 복잡한 Redis 컨테이너를 띄우는 대신 단순히 `discord.db` 파일만 백업해두면 모든 대화 기록과 처리 중인 작업을 완벽하게 보호할 수 있습니다.

## 4. 결론: "필요한 만큼만"

"SQLite is all you need"라는 제목은 SQLite가 모든 것을 대체할 수 있다는 뜻이 아니라, **대부분의 문제는 SQLite면 충분하다**는 뜻입니다. 복잡한 분산 시스템을 도입하기 전에, 가장 단순하고 안정적인 파일 기반 데이터베이스로 워크플로우의 신뢰성을 확보해 보는 것은 어떨까요?

다음 포스트에서는 이 SQLite 워크플로우 엔진을 Kubernetes 환경에서 안정적으로 운영하기 위한 Persisntent Volume 전략에 대해 다루겠습니다.