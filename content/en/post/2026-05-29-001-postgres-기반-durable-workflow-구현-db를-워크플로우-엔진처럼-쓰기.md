+++
title = "Implementing Postgres-based Durable Workflows: Using a DB as a Workflow Engine"
date = "2026-05-29T09:00:36+09:00"
draft = "false"
tags = ["Architecture", "PostgreSQL", "Workflow", "Rust", "ZeroClaw"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

As we've been building a fast and lightweight microservice architecture recently, minimizing external dependencies has emerged as a critical challenge. Specifically, during the development of the ZeroClaw runtime, we considered introducing separate message queues like Kafka or Redis to ensure complex state machine management and reliable communication between agents, but we were concerned about operational complexity.

At this point, the **"Postgres-based Durable Workflow"** pattern, which has recently been a hot topic on Hacker News and similar platforms, caught our attention. This approach goes beyond simply storing data, leveraging the database itself as a workflow engine to handle state persistence and retry logic. In this post, we'll share the core concepts of this pattern and a practical implementation method applied to the ZeroClaw project.

### Why Postgres?

Traditionally, we might have used specialized workflow engines like Temporal.io or Cadence, or implemented event sourcing through Kafka. However, for small teams or personal projects, maintaining such infrastructure can be a significant burden.

PostgreSQL is already adopted as the default database for most services. It guarantees strong consistency through ACID transactions and allows for distributed lock implementation (claim-based lock) using the `SKIP LOCKED` feature. This means we can simplify our infrastructure stack by utilizing our "already trusted storage" as a queue, a scheduler, and a state store.

### Core Architecture: Using Tables as a Queue

The core of this pattern lies in defining workflow states and execution tasks within tables. Let's take the ZeroClaw agent task queue as an example.

#### 1. Defining the State Table (SQL)

We designed the `workflow_jobs` table to store the current state of a job and its next execution time.

```sql
CREATE TABLE workflow_jobs (
    id SERIAL PRIMARY KEY,
    job_type TEXT NOT NULL, -- e.g., 'agent_task', 'discord_notify'
    payload JSONB NOT NULL, -- Data required for execution
    status TEXT NOT NULL DEFAULT 'pending', -- pending, running, succeeded, failed
    claimed_at TIMESTAMP,
    run_after TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Timestamp for delayed execution or retries
    last_error TEXT,
    attempt_count INT DEFAULT 0,
    max_attempts INT DEFAULT 5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- State-based indexing (for efficient lookups)
CREATE INDEX idx_jobs_claim ON workflow_jobs (status, run_after) WHERE status = 'pending';
```

The `status` and `run_after` columns are key here. These two columns allow us to immediately find "jobs that need to be executed now."

#### 2. Scheduling and Executing Tasks (Rust Example)

Now, a worker must find a task, claim ownership, and execute it within a transaction. To prevent race conditions, we use the `FOR UPDATE SKIP LOCKED` clause.

Here's an example implementation using Rust and `sqlx`:

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

/// Function called by the worker in its execution loop.
/// Safely claims a job within a transaction.
pub async fn claim_job(pool: &PgPool, worker_id: &str) -> Result<Option<Job>, sqlx::Error> {
    let now = Utc::now();
    
    let mut tx = pool.begin().await?;
    
    // 1. Find an executable job and lock it.
    // SKIP LOCKED: Ignores rows that have already been locked by another worker.
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
            tx.rollback().await?; // No job to claim (Rollback is not strictly necessary but explicit)
            return Ok(None);
        }
    };

    // 2. Change the job status to 'running'.
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

/// Function to update status after job completion.
pub async fn complete_job(pool: &PgPool, job_id: i32, success: bool, error_msg: Option<String>) -> Result<(), sqlx::Error> {
    let status = if success { "succeeded" } else { "failed" };
    
    // For failures, exponential backoff can be considered to calculate run_after.
    let next_run = if success {
        None
    } else {
        // e.g., Retry after 10 seconds (actual implementation should include exponential logic based on attempt_count)
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

#### 3. Worker Loop Configuration

Now, using the functions above, we can run an infinite loop (or use Tokio's `tokio::time::interval`) to process jobs.

```rust
async fn worker_loop(pool: PgPool, worker_id: String) {
    loop {
        match claim_job(&pool, &worker_id).await {
            Ok(Some(job)) => {
                println!("[{}] Job acquired: {:?}", worker_id, job.job_type);
                
                // Execute actual business logic (e.g., LLM inference, API calls)
                let result = execute_logic(job.payload.clone()).await;

                // Reflect the result
                let _ = complete_job(&pool, job.id, result.is_ok(), result.err().map(|e| e.to_string())).await;
            }
            Ok(None) => {
                // If there are no jobs to process, wait briefly (to prevent high CPU usage)
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

### Pros, Cons, and Usage Tips

**Pros:**
1. **Simplicity:** Achieves reliability using only RDBMS transactions without complex distributed system theory.
2. **Operational Efficiency:** Backing up the DB also restores workflow states.
3. **Strong Consistency:** No worries about in-flight message loss.

**Cons:**
1. **Throughput Limitations:** Postgres has limitations on per-connection throughput, so a specialized MQ is better if you need tens of thousands of transactions per second.
2. **DB Load:** Workers continuously poll, so connection pools should be optimized using tools like `pgbouncer`.

### Conclusion

In ZeroClaw's multi-agent environment, the message processing throughput of individual agents wasn't high enough to justify introducing Kafka, but state management reliability was crucial. Through the Postgres-based architecture, we were able to achieve both "stable state management" and a "scalable task queue" without introducing separate infrastructure.

If your project is grappling with the trade-off between "simplicity" and "reliability," why not consider leveraging the readily available Postgres as a workflow engine before adopting heavy-duty solutions?

### References
- [Building durable workflows on Postgres](https://www.hanselminutes.com/890/building-durable-workflows-on-postgres-with-pavel-duchovny) (Hacker News Discussion)
- [SKIP LOCKED and Distributed Lock Implementation](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE)
```