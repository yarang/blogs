+++
title = "pg_durable 분석: Rust로 구현하는 내구성 있는 함수 실행"
date = 2026-06-06T09:00:49+09:00
draft = false
tags = ["Rust", "PostgreSQL", "pg_durable", "Architecture", "Database"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

최근 Microsoft가 오픈 소스로 공개한 `pg_durable`은 데이터베이스 내에서 직접 '내구성 있는(Durable)' 함수 실행을 가능하게 하는 실험적인 프로젝트입니다. 전통적인 마이크로서비스 아키텍처에서는 비즈니스 로직이 애플리케이션 계층에 위치하고, 데이터베이스는 단순히 상태를 저장하는 역할에 그치는 경우가 많습니다. 하지만 `pg_durable`은 로직과 데이터를 물리적으로 가까운 곳에 통합하여, 외부 시스템의 장애나 네트워크 비용을 최소화하는 접근 방식을 제시합니다.

이번 글에서는 `pg_durable`의 핵심 메커니즘을 분석하고, Rust와 PostgreSQL을 활용해 유사한 패턴을 구현하는 방법을 살펴보겠습니다.

## pg_durable의 핵심 메커니즘

`pg_durable`의 가장 큰 특징은 함수의 상태(State)와 실행 흐름(Execution Flow) 자체를 데이터베이스 레코드로 저장한다는 점입니다. 일반적인 애플리케이션에서 HTTP 요청이 실패하면 메모리에 있던 컨텍스트가 사라지지만, `pg_durable`은 실행할 함수의 입력(Input)과 현재 단계(Step)를 테이블에 기록합니다.

이를 통해 다음과 같은 이점을 얻을 수 있습니다:
1.  **자동 복구 (Auto-Recovery)**: 서버가 크래시되어도 데이터베이스에는 '실행해야 할 작업'이 남아있으므로, 서버 재시작 후 남은 작업을 이어서 수행할 수 있습니다.
2.  **정확히 한 번 실행 (Exactly-Once Semantics)**: 데이터베이스 트랜잭션을 활용해 상태 업데이트와 로직 실행을 원자적으로 처리할 수 있습니다.

## Rust로 데이터베이스 트리거 기반 워커 구현하기

`pg_durable`의 내부 구현은 복잡하지만, 이 패턴을 Rust와 PostgreSQL의 `LISTEN/NOTIFY` 기능을 사용해 간단하게 재현해 볼 수 있습니다. 이 접근 방식은 데이터베이스를 '메시지 브로커'처럼 활용하면서도 별도의 인프라 비용을 절약할 수 있습니다.

### 1. 데이터베이스 스키마 설계

먼저 작업(Job)을 저장할 테이블을 생성합니다.

```sql
CREATE TABLE durable_jobs (
    id SERIAL PRIMARY KEY,
    status TEXT NOT NULL, -- 'pending', 'running', 'completed'
    payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2. Rust 워커 구현 (sqlx 사용)

Rust의 비동기 런타임과 `sqlx`를 사용하여, 데이터베이스에 새 작업이 들어오면 이를 감지하고 처리하는 워커를 작성해 보겠습니다.

```toml
# Cargo.toml
[dependencies]
tokio = { version = "1", features = ["full"] }
sqlx = { version = "0.7", features = ["runtime-tokio", "postgres", "json"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
```

이제 Rust 코드로 워커를 구현합니다.

```rust
use sqlx::{PgPool, Listener};
use serde::{Deserialize, Serialize};
use tokio::time::{sleep, Duration};

#[derive(Debug, Serialize, Deserialize)]
struct JobPayload {
    user_id: i32,
    action: String,
}

#[tokio::main]
async fn main() -> Result<(), sqlx::Error> {
    // 데이터베이스 연결 풀 생성
    let pool = PgPool::connect("postgresql://user:password@localhost/mydb").await?;
    
    // 데이터베이스 변경 사항 감지 리스너 (pg_notify 활용)
    let mut listener = pool.acquire().await?.listen("job_channel");

    println!("Worker started, waiting for jobs...");

    loop {
        // 알림 수신 대기
        let notification = listener.recv().await?;
        println!("Received notification: {}", notification.payload);

        // 알림을 받으면 실제 작업 처리 시도
        process_jobs(&pool).await?;
    }
}

async fn process_jobs(pool: &PgPool) -> Result<(), sqlx::Error> {
    // 트랜잭션 내에서 'pending' 상태의 작업을 가져와 'running'으로 변경 (Locking)
    let mut tx = pool.begin().await?;
    
    let job_opt = sqlx::query_as::<_, (i32, JobPayload)>(
        r#"
        UPDATE durable_jobs 
        SET status = 'running' 
        WHERE id = (
            SELECT id FROM durable_jobs 
            WHERE status = 'pending' 
            FOR UPDATE SKIP LOCKED 
            LIMIT 1
        )
        RETURNING id, payload
        "#
    )
    .fetch_optional(&mut *tx)
    .await?;

    if let Some((id, payload)) = job_opt {
        println!("Processing job {}: {:?}", id, payload);
        
        // 비즈니스 로직 실행 (예: 외부 API 호출 등)
        // 실제 환경에서는 여기서 무거운 작업을 수행합니다.
        let result = simulate_heavy_task(&payload).await;

        match result {
            Ok(_) => {
                // 성공 시 상태를 'completed'로 업데이트
                sqlx::query("UPDATE durable_jobs SET status = 'completed' WHERE id = $1")
                    .bind(id)
                    .execute(&mut *tx)
                    .await?;
            }
            Err(e) => {
                // 실패 시 상태를 'failed'로 남겨두거나 재시도 로직 추가
                eprintln!("Job {} failed: {}", id, e);
                sqlx::query("UPDATE durable_jobs SET status = 'failed' WHERE id = $1")
                    .bind(id)
                    .execute(&mut *tx)
                    .await?;
            }
        }
        
        tx.commit().await?;
    }
    
    Ok(())
}

async fn simulate_heavy_task(payload: &JobPayload) -> Result<(), Box<dyn std::error::Error>> {
    // 예시: 2초 대기
    sleep(Duration::from_secs(2)).await;
    println!("Task executed for user {}", payload.user_id);
    Ok(())
}
```

### 3. 작업 등록 트리거

실제로는 애플리케이션 레벨에서 `INSERT` 쿼리를 날린 후 `NOTIFY`를 보내거나, 트리거를 사용해 자동화할 수 있습니다.

```sql
-- 트리거 함수 및 트리거 생성 예시
CREATE OR REPLACE FUNCTION notify_job() RETURNS TRIGGER AS $$
BEGIN
  PERFORM pg_notify('job_channel', NEW.id::text);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER job_notify_trigger
AFTER INSERT ON durable_jobs
FOR EACH ROW
EXECUTE FUNCTION notify_job();
```

## 아키텍처 적용 시 고려사항

이 패턴(`pg_durable` 스타일)을 ZeroClaw나 MCP 서버와 같은 고성능 시스템에 적용할 때는 다음 사항을 고려해야 합니다.

1.  **데이터베이스 부하**: 데이터베이스가 단순한 저장소가 아니라 실행 엔진의 역할을 일부 담당하므로, 워커가 너무 잦은 폴링(Polling)을 하거나 무거운 로직을 수행하면 DB 성능에 저하가 올 수 있습니다. `SKIP LOCKED` 구문을 사용해 여러 워커 인스턴스가 안전하게 분산 처리하도록 구성하는 것이 필수입니다.

2.  **확장성(Scale-out)**: 앞서 보여준 Rust 코드는 다중 프로세스로 실행하더라도 `FOR UPDATE SKIP LOCKED` 덕분에 안전하게 작업을 분산 처리할 수 있습니다. Kubernetes 환경이라면 `HorizontalPodAutoscaler`(HPA)를 통해 큐가 쌓일 때 워커 파드를 늘리는 식으로 유연한 대응이 가능합니다.

## 결론

Microsoft의 `pg_durable`은 '데이터 중심 아키텍처(Data-Centric Architecture)'의 진화된 형태를 보여줍니다. 복잡한 메시지 큐(Kafka, RabbitMQ)를 도입하기 전, 데이터베이스의 트랜잭션 기능을 적극 활용해 간단하고 강력한 내구성을 확보해 보는 것은 어떨까요? 위의 예제 코드는 바로 실무에서 테스트해 볼 수 있는 형태이므로, 여러분의 사이드 프로젝트나 백오피스 시스템에 적용해 보시길 권장합니다.