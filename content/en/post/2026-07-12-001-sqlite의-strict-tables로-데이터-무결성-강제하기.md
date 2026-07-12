+++
title = "Enforcing Data Integrity with SQLite's Strict Tables"
date = "2026-07-12T09:01:22+09:00"
draft = "false"
tags = ["SQLite", "Database", "Data Integrity", "Strict Tables", "SQL"]
categories = ["Development"]
ShowToc = "true"
TocOpen = "true"
+++

# Enforcing Data Integrity with SQLite's Strict Tables

A recent interesting article was posted on Hacker News titled **'Prefer strict tables in SQLite'**. While SQLite is often called the 'most beloved database' among developers, paradoxically, its flexibility can often lead to code that "may cause problems later."

Today, we'll introduce how to perform enterprise-level strict type validation even when using lightweight SQLite file databases, by leveraging the **Strict Tables** feature introduced in SQLite 3.37.0 (2021).

## The Problem: SQLite's Lenient Type System

SQLite traditionally uses a **'Dynamic Typing'** system. This means that data types are not stored with the column, but rather **with the value itself**. SQLite documentation refers to this as 'Manifest Typing'.

For example, if you try to insert a number into a column defined as `TEXT`, SQLite doesn't throw an error; instead, it converts the number to text and stores it.

```sql
-- Creating a typical table
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    account_balance INTEGER  -- Defined as an integer
);

-- The following INSERT 'succeeds' in SQLite.
-- We attempted to insert a string into 'balance', but SQLite accepts it.
INSERT INTO users (username, account_balance) VALUES ('hacker', 'invalid_string');

-- You can even mix different types like this.
INSERT INTO users (username, account_balance) VALUES ('admin', 100);
```

While this is useful for rapid prototyping, it can be a source of potential bugs in scenarios where data consistency is critical, such as financial data or log analysis systems. When you're accustomed to using `struct` in Rust or interfaces in TypeScript, encountering such inconsistencies at the database level can be quite jarring.

## The Solution: Introducing STRICT Tables

Using the `STRICT` keyword makes a table adhere to strong typing rules. In Strict tables, the data type of a column must be strictly observed; otherwise, an `SQLITE_CONSTRAINT_DATATYPE` error will occur.

### Syntax for Defining Strict Tables

```sql
CREATE TABLE users_strict (
    id INTEGER PRIMARY KEY,
    username TEXT,
    account_balance INTEGER,
    created_at TEXT  -- Dates are usually managed as ISO8601 strings
) STRICT;
```

Simply append the `STRICT` keyword at the end of your table definition.

### Comparing with Code

Let's examine the difference in behavior between a normal table and a STRICT table using Python code.

```python
import sqlite3

def run_example():
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # 1. Normal table (flexible)
    cursor.execute('''
        CREATE TABLE normal_users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            age INTEGER
        )
    ''')
    
    try:
        # The string '25' is inserted without error (handled internally)
        cursor.execute("INSERT INTO normal_users (name, age) VALUES (?, ?)", ('Alice', 'Twenty-Five'))
        print("[Normal Table] Inserted 'Twenty-Five' into INTEGER column. Success.")
        # Data retrieval
        print(cursor.execute("SELECT * FROM normal_users").fetchall())
    except Exception as e:
        print(f"[Normal Table] Error: {e}")

    # 2. STRICT table (strict)
    cursor.execute('''
        CREATE TABLE strict_users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            age INTEGER
        ) STRICT
    ''')

    try:
        # In STRICT mode, type mismatches will cause an error
        cursor.execute("INSERT INTO strict_users (name, age) VALUES (?, ?)", ('Bob', 'Thirty'))
        print("[Strict Table] Inserted 'Thirty' into INTEGER column. Success.")
    except sqlite3.IntegrityError as e:
        print(f"[Strict Table] Blocked invalid data! Error: {e}")

    # Valid insertion
    cursor.execute("INSERT INTO strict_users (name, age) VALUES (?, ?)", ('Bob', 30))
    print("[Strict Table] Valid insert successful.")
    print(cursor.execute("SELECT * FROM strict_users").fetchall())

    conn.close()

if __name__ == '__main__':
    run_example()
```

**Execution Result:**
```
[Normal Table] Inserted 'Twenty-Five' into INTEGER column. Success.
[(1, 'Alice', 'Twenty-Five')]
[Strict Table] Blocked invalid data! Error: datatype mismatch
[Strict Table] Valid insert successful.
[(1, 'Bob', 30)]
```

As you can see, Strict tables immediately return an error when data of the wrong type is attempted, increasing the reliability of your system.

## Constraints and Supported Types for Strict Tables

When using Strict tables, you should keep a few rules in mind.

### 1. Allowed Data Types

In Strict tables, only the following five types can be used:

*   **INTEGER** (signed integer)
*   **REAL** (floating-point number)
*   **TEXT** (UTF-8/UTF-16 string)
*   **BLOB** (binary data)
*   **ANY** (explicitly specifying ANY allows for Dynamic typing for SQLite 2/3 compatibility)

What if you want to use common SQL types like `VARCHAR(255)` or `BOOLEAN`? SQLite maps these to the above five types based on its **Affinity** rules.

```sql
CREATE TABLE product (
    id INTEGER PRIMARY KEY,
    name TEXT,
    price NUMERIC,  -- In STRICT mode, NUMERIC maps to INTEGER or REAL
    is_available BOOLEAN -- In STRICT mode, BOOLEAN maps to NUMERIC (0 or 1)
) STRICT;
```

In strict mode, you cannot insert the strings `TRUE`/`FALSE` into a `BOOLEAN` type; you must insert `0` or `1` (Integer). This is a very strict rule, and you may need logic at the application layer to convert data.

### 2. Rowid and Primary Key

In Strict tables, `INTEGER PRIMARY KEY` becomes the actual Rowid, not an alias. If you use the `WITHOUT ROWID` option, `INTEGER PRIMARY KEY` will behave like a regular `NOT NULL INTEGER` column.

## Practical Application Guide

Here's an example SQL migration script for applying this to existing projects.

```sql
-- Existing flexible table (risky)
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT,
    message TEXT,
    timestamp INTEGER
);

-- Migrating to STRICT (safe)
-- 1. Backup existing table
CREATE TABLE logs_backup AS SELECT * FROM logs;

-- 2. Drop the existing table
DROP TABLE logs;

-- 3. Recreate with STRICT
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL CHECK(level IN ('INFO', 'WARN', 'ERROR')), -- Type + Constraint
    message TEXT NOT NULL,
    timestamp INTEGER NOT NULL
) STRICT;

-- 4. Restore data (if data types are mismatched, an error will occur here.
--    Developers must clean the data before proceeding)
INSERT INTO logs SELECT * FROM logs_backup;
```

## Conclusion: Using SQLite as a 'Tool', Not a 'Toy'

Developers who value type safety when using languages like Rust or Go will want that safety guaranteed within their databases as well.

`STRICT` tables are a powerful tool that ensures data integrity through table definitions alone, without requiring configuration changes. This is especially true for systems like **ZeroClaw multi-agent systems** or **monitoring dashboards** that use SQLite in local or lightweight container environments. Strict tables play a significant role in preventing "rogue data" that could lead to service outages.

Try appending `STRICT` to your schema definitions today. Your database will protect you.

### References
*   [SQLite Strict Tables Documentation](https://www.sqlite.org/stricttables.html)
*   [Hacker News Discussion: Prefer strict tables in SQLite](https://news.ycombinator.com/item?id=41029438)
```