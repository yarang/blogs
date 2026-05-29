+++
title = "Postgres 기반 Durable Workflow 구현: DB를 워크플로우 엔진처럼 쓰기"
date = 2026-05-29T09:00:36+09:00
draft = false
tags = ["Architecture", "PostgreSQL", "Workflow", "Rust", "ZeroClaw"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

최근 빠르고 가벼운 마이크로 서비스 아키텍처를 구축하면서, 외부 의존성을 최소화하는 것이 중요한 과제로 떠올랐습니다. 특히 ZeroClaw 런타임 개발 과정에서 복잡한 상태 머신 관리와 에이전트 간의 통신 신뢰성을 보장하기 위해 Kafka나 Redis 같은 별도의 메시지 큐를 도입하려 했으나, 운영 복잡도가 우려되었습니다.

이때 눈에 들어온 것이 최근 Hacker News 등에서 화제가 된 **'Postgres 기반 Durable Workflow'** 패턴입니다. 단순히 데이터를 저장하는 것을 넘어, 데이터베이스 자체를 워크플로우 엔진처럼 활용하여 상태 유지와 재시작(Retry) 로직을 처리하는 방식입니다. 이번 포스트에서는 이 패턴의 핵심 개념과 ZeroClaw 프로젝트에 적용한 실용적인 구현 방법을 공유합니다.

### 왜 Postgres인가?

기존에는 Temporal.io나 Cadence 같은 전문 워크플로우 엔진을 사용하거나, Kafka를 통해 이벤트 소싱을 구현했습니다. 하지만 소규모 팀이나 개인 프로젝트에서는 이러한 인프라를 유지하는 것이 큰 부담이 됩니다.

PostgreSQL은 이미 대부분의 서비스가 기본 데이터베이스로 채택하고 있습니다. ACID 트랜잭션을 통해 강력한 일관성을 보장하며, `SKIP LOCKED` 기능을 통해 분산 락(Claim-based lock)을 구현할 수 있습니다. 즉, '이미 우리가 가진 신뢰할 수 있는 저장소'를 큐(Queue)로, 스케줄러로, 그리고 상태 저장소로 활용하여 인프라 스택을 단순화할 수 있습니다.

### 핵심 아키텍처: 테이블을 큐처럼 사용하기

이 패턴의 핵심은 워크플로우의 상태(State)와 실행 대상(Task)을 테이블에 정의하는 것입니다. ZeroClaw의 에이전트 작업 큐를 예로 들어보겠습니다.

#### 1. 상태 테이블 정의 (SQL)

우리는 작업의 현재 상태와 다음 실행 시점을 저장하기 위해 `workflow_jobs` 테이블을 설계했습니다.

```sql
CREATE TABLE workflow_jobs (
    id SERIAL PRIMARY KEY,
    job_type TEXT NOT NULL, -- 예: 'agent_task', 'discord_notify'
    payload JSONB NOT NULL, -- 실행에 필요한 데이터
    status TEXT NOT NULL DEFAULT 'pending', -- pending, running, succeeded, failed
    claimed_at TIMESTAMP,
    run_after TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 지연 실행 또는 재시작 타임스탬프
    last_error TEXT,
    attempt_count INT DEFAULT 0,
    max_attempts INT DEFAULT 5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 상태 기반 인덱싱 (효율적인 조회를 위해)
CREATE INDEX idx_jobs_claim ON workflow_jobs (status, run_after) WHERE status = 'pending';
```

여기서 `status`와 `run_after` 컬럼이 핵심입니다. 이 두 컬럼을 통해 '지금 실행해야 할 작업'을 즉시 찾아낼 수 있습니다.

#### 2. 작업 예약 및 실행 (Rust 예제)

이제 워커(Worker)는 트랜잭션 내에서 작업을 찾고(`SELECT`), 소유권을 주장(`UPDATE`)한 뒤 실행해야 합니다. 이 과정에서 경쟁 조건(Race Condition)을 방지하기 위해 `FOR UPDATE SKIP LOCKED` 구문을 사용합니다.

다음은 Rust와 `sqlx`를 사용한 구현 예제입니다.

```rust
use sqlx::{PgPool, Postgres};
use sqlx::types::chrono::{Utc, DateTime};
use serde_json::Value;

#[derive(Debug)]
pub struct Job {
    pub id: i32,
    pub job_type: String,
    pub payload: Value,
}

/// 워커가 실행 루프에서 호출할 함수
/// 트랜잭션 내에서 안전하게 작업을 할당받습니다.
pub async fn claim_job(pool: &PgPool, worker_id: &str) -> Result<Option<Job>, sqlx::Error> {
    let now = Utc::now();
    
    let mut tx = pool.begin().await?;
    
    // 1. 실행 가능한 작업을 찾고 락을 겁니다.
    // SKIP LOCKED: 다른 워커가 이미 락을 건 행은 무시하고 넘어갑니다.
    let query = r#"
        SELECT id, job_type, payload 
        FROM workflow_jobs 
        WHERE status = 'pending' 
          AND run_after <= $1
        ORDER BY created_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1
        FOR UPDATE OF workflow_jobs
    "#;

    let job: Option<Job> = sqlx::query_as::<_, Job>(query)
        .bind(now)
        .fetch_optional(&mut *tx)
        .await?;

    let job = match job {
        Some(j) => j,
        None => {
            tx.rollback().await?; // 할당받을 작업 없음 (Rollback은 불필요하지만 명시적 표현)
            return Ok(None);
        }
    };

    // 2. 작업 상태를 'running'으로 변경
    sqlx::query(
        "UPDATE workflow_jobs SET status = 'running', claimed_at = $1, attempt_count = attempt_count + 1 WHERE id = $2"
    )
    .bind(Utc::now())
    .bind(job.id)
    .execute(&mut *tx)
    .await?;

    tx.commit().await?;

    Ok(Some(job))
}

/// 작업 완료 후 상태를 업데이트하는 함수
pub async fn complete_job(pool: &PgPool, job_id: i32, success: bool, error_msg: Option<String>) -> Result<(), sqlx::Error> {
    let status = if success { "succeeded" } else { "failed" };
    
    // 실패 시 지수 백오프(Exponential Backoff)를 고려하여 run_after를 계산할 수 있습니다.
    let next_run = if success {
        None
    } else {
        // 예: 10초 후 재시도 시도 (실제 구현에서는 attempt_count에 따른 지수 증가 로직 필요)
        Some(Utc::now() + chrono::Duration::seconds(10))
    };

    if success {
        sqlx::query(
            "UPDATE workflow_jobs SET status = $1, run_after = NULL WHERE id = $2"
        )
        .bind(status)
        .bind(job_id)
        .execute(pool)
        .await?;
    } else {
        sqlx::query(
            "UPDATE workflow_jobs SET status = $1, last_error = $2, run_after = $3 WHERE id = $4"
        )
        .bind(status)
        .bind(error_msg)
        .bind(next_run)
        .bind(job_id)
        .execute(pool)
        .await?;
    }

    Ok(())
}
```

#### 3. 워커 루프 구성

이제 위 함수를 사용해 무한 루프(또는 Tokio의 `tokio::time::interval`)를 돌며 작업을 처리합니다.

```rustnasync fn worker_loop(pool: PgPool, worker_id: String) {
    loop {
        match claim_job(&pool, &worker_id).await {
            Ok(Some(job)) => {
                println!("[{}] Job acquired: {:?}", worker_id, job.job_type);
                
                // 실제 비즈니스 로직 실행 (예: LLM 추론, API 호출)
                let result = execute_logic(job.payload.clone()).await;

                // 결과 반영
                let _ = complete_job(&pool, job.id, result.is_ok(), result.err().map(|e| e.to_string())).await;
            }
            Ok(None) => {
                // 처리할 작업이 없으면 잠시 대기 (CPU 점유율 방지)
                tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
            }
            Err(e) => {
                eprintln!("[{}] Worker error: {}", worker_id, e);
                tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;
            }
        }
    }
}
```

### 장단점 및 활용 팁

**장점:**
1. **단순성:** 복잡한 분산 시스템 이론 없이 RDBMS의 트랜잭션만으로 신뢰성을 확보합니다.
2. **운영 효율성:** DB만 백업하면 워크플로우 상태도 함께 복구됩니다.
3. **강력한 일관성:** 메시지 유실(In-flight loss)에 대한 걱정이 없습니다.

**단점:**
1. **처리량 처리량:** Postgres는 연결당 처리량에 한계가 있으므로, 초당 수만 건 이상의 처리량이 필요하면 전문 MQ가 낫습니다.
2. **DB 부하:** 워커가 순환 쿼리(Polling)를 지속적으로 수행하므로, `pgbouncer` 등을 통해 연결 풀을 최적화해야 합니다.

### 결론

ZeroClaw의 멀티 에이전트 환경에서는 개별 에이전트의 메시지 처리량이 Kafka를 도입할 만큼 높지 않지만, 상태 관리의 신뢰성은 매우 중요했습니다. Postgres 기반 아키텍처를 통해 별도의 인프라 도입 없이 '안정적인 상태 관리'와 '확장 가능한 작업 큐'를 모두 달성할 수 있었습니다.

만약 당신의 프로젝트가 '단순함'과 '신뢰성' 사이에서 고민하고 있다면, 굳이 무거운 솔루션을 도입하기 전에 가까운 곳에 있는 Postgres를 워크플로우 엔진으로 활용해 보는 것은 어떨까요?

### 참고자료
- [Building durable workflows on Postgres](https://www.hanselminutes.com/890/building-durable-workflows-on-postgres-with-pavel-duchovny) (Hacker News 토론)
- [SKIP LOCKED와 분산 락 구현](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE)