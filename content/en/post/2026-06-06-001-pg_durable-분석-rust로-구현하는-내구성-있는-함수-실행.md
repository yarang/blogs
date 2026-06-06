+++
title = "pg_durable Analysis: Implementing Durable Function Execution with Rust"
date = "2026-06-06T09:00:49+09:00"
draft = "false"
tags = ["Rust", "PostgreSQL", "pg_durable", "Architecture", "Database"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

Recently open-sourced by Microsoft, `pg_durable` is an experimental project that enables 'Durable' function execution directly within the database. In traditional microservice architectures, business logic often resides in the application layer, with the database primarily serving as a state storage. However, `pg_durable` proposes an approach that integrates logic and data in close proximity, minimizing external system failures or network costs.

In this article, we will analyze the core mechanisms of `pg_durable` and explore how to implement a similar pattern using Rust and PostgreSQL.

## Core Mechanisms of pg_durable

The most significant feature of `pg_durable` is that it stores the function's state and execution flow itself as database records. In typical applications, if an HTTP request fails, the in-memory context disappears. However, `pg_durable` records the input and current step of the function to be executed in a table.

This approach offers the following benefits:
1.  **Auto-Recovery**: Even if a server crashes, 'tasks to be executed' remain in the database, allowing for continued execution after the server restarts.
2.  **Exactly-Once Semantics**: By leveraging database transactions, state updates and logic execution can be handled atomically.

## Implementing a Database Trigger-Based Worker with Rust

While the internal implementation of `pg_durable` is complex, we can simply replicate this pattern using Rust and PostgreSQL's `LISTEN/NOTIFY` functionality. This approach utilizes the database as a 'message broker' while saving on separate infrastructure costs.

### 1. Database Schema Design

First, we create a table to store jobs.

```sql
CREATE TABLE durable_jobs (
    id SERIAL PRIMARY KEY,
    status TEXT NOT NULL, -- 'pending', 'running', 'completed'
    payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2. Rust Worker Implementation (Using sqlx)

We will use Rust's asynchronous runtime and `sqlx` to write a worker that detects and processes new jobs as they enter the database.

```toml
# Cargo.toml
[dependencies]
tokio = { version = "1", features = ["full"] }
sqlx = { version = "0.7", features = ["runtime-tokio", "postgres", "json"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
```

Now, let's implement the worker in Rust code.

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
    // Create a database connection pool
    let pool = PgPool::connect("postgresql://user:password@localhost/mydb").await?;
    
    // Listener to detect database changes (using pg_notify)
    let mut listener = pool.acquire().await?.listen("job_channel");

    println!("Worker started, waiting for jobs...");

    loop {
        // Wait for notifications
        let notification = listener.recv().await?;
        println!("Received notification: {}", notification.payload);

        // Upon receiving a notification, attempt to process the actual job
        process_jobs(&pool).await?;
    }
}

async fn process_jobs(pool: &PgPool) -> Result<(), sqlx::Error> {
    // Within a transaction, fetch a 'pending' job and change its status to 'running' (Locking)
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
        
        // Execute business logic (e.g., external API calls, etc.)
        // In a real environment, heavy tasks would be performed here.
        let result = simulate_heavy_task(&payload).await;

        match result {
            Ok(_) => {
                // On success, update status to 'completed'
                sqlx::query("UPDATE durable_jobs SET status = 'completed' WHERE id = $1")
                    .bind(id)
                    .execute(&mut *tx)
                    .await?;
            }
            Err(e) => {
                // On failure, leave status as 'failed' or add retry logic
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
    // Example: Wait for 2 seconds
    sleep(Duration::from_secs(2)).await;
    println!("Task executed for user {}", payload.user_id);
    Ok(())
}
```

### 3. Job Registration Trigger

In practice, you can automate this by sending an `INSERT` query from the application level and then issuing a `NOTIFY`, or by using a trigger.

```sql
-- Example of creating a trigger function and trigger
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

## Considerations for Applying the Architecture

When applying this pattern (the `pg_durable` style) to high-performance systems like ZeroClaw or MCP servers, consider the following:

1.  **Database Load**: Since the database partially acts as an execution engine rather than just a storage, frequent polling by workers or executing heavy logic can degrade DB performance. It is essential to configure it to allow multiple worker instances to process tasks safely and in a distributed manner, using the `SKIP LOCKED` clause.

2.  **Scalability (Scale-out)**: Even when the Rust code shown above is run as multiple processes, it can safely distribute tasks thanks to `FOR UPDATE SKIP LOCKED`. In a Kubernetes environment, flexible responses can be achieved by increasing worker pods when the queue grows, using `HorizontalPodAutoscaler` (HPA).

## Conclusion

Microsoft's `pg_durable` showcases an evolved form of 'Data-Centric Architecture'. Before introducing complex message queues (Kafka, RabbitMQ), why not achieve simple yet robust durability by actively leveraging the transactional capabilities of the database? The example code above is readily testable in practice, so we recommend applying it to your side projects or back-office systems.