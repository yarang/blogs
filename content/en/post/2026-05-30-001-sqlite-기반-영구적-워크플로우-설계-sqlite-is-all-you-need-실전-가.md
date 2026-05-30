+++
title = "Designing Durable Workflows with SQLite: A Practical Guide to 'SQLite is All You Need'"
date = "2026-05-30T09:00:30+09:00"
draft = "false"
tags = ["SQLite", "Workflow", "Rust", "DurableExecution", "Architecture"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

# How to Make Your Workflows Durable with SQLite

Recently, an article titled "SQLite is all you need for durable workflows" gained significant traction on Hacker News. When designing distributed systems, it's easy to jump to solutions like Kafka, Redis, or complex clustering. However, the article argues that the core problems we aim to solve – 'State Management' and 'Resiliency' – can be sufficiently addressed by SQLite, a single-file database.

While developing agent systems like our team's 'ZeroClaw' or 'Discord Decision MCP', we opted to implement our workflow engines directly, leveraging SQLite's lightweight yet robust transactional capabilities before resorting to complex message queues. In this post, we'll share the core architecture and practical code examples.

## 1. What is a Durable Workflow?

A workflow is considered 'durable' if it can resume execution from the point of interruption, even if the program crashes or the server restarts. To achieve this, we need to guarantee two things:

1.  **Snapshotting:** Continuously save the current progress.
2.  **Exactly-Once Semantics:** Prevent duplicate execution upon restart.

## 2. Architecture Design: Using SQLite as a Queue and State Store

SQLite demonstrates remarkable performance in concurrent environments, thanks to its `WAL (Write-Ahead Logging)` mode and advanced locking mechanisms. Our workflow engine operates based on the following table structure.

### Database Schema

```sql
-- Table to store the current state of workflows
CREATE TABLE workflows (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL, -- pending, running, completed, failed
    current_step INTEGER NOT NULL DEFAULT 0,
    payload TEXT,         -- Input data in JSON format
    updated_at INTEGER NOT NULL
);

-- List of jobs to be executed (the queue)
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    target_step INTEGER NOT NULL,
    run_at INTEGER,       -- Scheduled execution time (NULL for immediate execution)
    FOREIGN KEY(workflow_id) REFERENCES workflows(id)
);

CREATE INDEX idx_jobs_run_at ON jobs(run_at);
```

### Rust Implementation Example

We'll write a simple workflow scheduler using Rust's `rusqlite` library. This code is inspired by the lightweight job scheduling logic in the 'ZeroClaw' runtime.

```rust
use rusqlite::{Connection, Result, params};
use std::time::{Duration, SystemTime};

fn main() -> Result<()> {
    // 1. Connect to an in-memory or file-based DB (WAL mode recommended)
    let mut conn = Connection::open("workflow.db")?;
    conn.execute_batch("PRAGMA journal_mode=WAL;")?;

    // 2. Create a workflow (initial state)
    let workflow_id = "order-12345";
    insert_workflow(&mut conn, workflow_id, "{\"item\": \"keyboard\"}")?;

    // 3. Schedule a job (payment step)
    enqueue_job(&mut conn, workflow_id, 1, None)?;

    // 4. Worker loop (daemonize in production)
    loop {
        match fetch_next_job(&mut conn)? {
            Some(job) => {
                println!("Processing job {} for workflow {}", job.target_step, job.workflow_id);
                
                // Execute business logic (e.g., LLM calls, external API requests)
                // simulate_work();

                // Upon success, schedule the next step or handle completion
                complete_step(&mut conn, &job.workflow_id, job.target_step)?;
            }
            None => {
                println!("No jobs, sleeping...");
                std::thread::sleep(Duration::from_secs(5));
            }
        }
    }
}

// Transaction to enqueue a job and update workflow status to 'pending'
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

// Function to fetch the next job to be processed (Locking Read)
fn fetch_next_job(conn: &mut Connection) -> Result<Option<Job>> {
    // Technique to lock and return rows using an UPDATE statement (UPDATE RETURNING)
    // Supported in SQLite 3.35.0 and later
    let mut stmt = conn.prepare(
        "UPDATE jobs 
         SET workflow_id = workflow_id || ':processing' -- Temporary status indicator (a dedicated status column is recommended)
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

// Process step completion
fn complete_step(conn: &mut Connection, workflow_id: &str, step: i32) -> Result<()> {
    let tx = conn.transaction()?;
    
    // Delete completed job
    tx.execute("DELETE FROM jobs WHERE workflow_id = ?1 AND target_step = ?2", params![workflow_id, step])?;
    
    // Update workflow status (to the next step)
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

## 3. Why is this Structure Powerful?

The biggest advantage of this approach is its **minimal operational overhead**.

*   In agent systems like 'ZeroClaw', each agent operates with its own SQLite file, avoiding bottlenecks of a centralized database.
*   When building bots like Discord MCP, instead of deploying complex Redis containers, simply backing up the `discord.db` file can perfectly protect all conversation history and in-progress tasks.

## 4. Conclusion: "Just Enough"

The title "SQLite is all you need" doesn't imply that SQLite can replace everything, but rather that **SQLite is sufficient for most problems**. Before introducing complex distributed systems, why not secure your workflow's reliability with the simplest and most stable file-based database?

In the next post, we'll discuss persistent volume strategies for reliably operating this SQLite workflow engine in a Kubernetes environment.
```