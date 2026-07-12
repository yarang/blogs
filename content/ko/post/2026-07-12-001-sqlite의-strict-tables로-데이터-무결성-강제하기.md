+++
title = "SQLite의 Strict Tables로 데이터 무결성 강제하기"
date = 2026-07-12T09:01:22+09:00
draft = false
tags = ["SQLite", "Database", "Data Integrity", "Strict Tables", "SQL"]
categories = ["Development"]
ShowToc = true
TocOpen = true
+++

# SQLite의 Strict Tables로 데이터 무결성 강제하기

최근 Hacker News에 흥미로운 글이 올라왔습니다. 바로 **'Prefer strict tables in SQLite'**이라는 주제입니다. SQLite은 개발자들 사이에서 '가장 사랑받는 데이터베이스'로 불리지만, 역설적으로 유연성(Flexibility) 때문에 종종 "나중에 문제가 터질 수 있는" 코드를 양산하기도 합니다.

오늘은 SQLite 3.37.0(2021년)부터 도입된 **Strict Tables** 기능을 활용하여, 가벼운 SQLite 파일 데이터베이스를 사용할 때도 엔터프라이즈 DB 수준의 엄격한 타입 검증을 수행하는 방법을 소개합니다.

## 문제 상황: SQLite의 너그러운 타입 시스템

SQLite는 전통적으로 **'Dynamic Typing'** 시스템을 사용합니다. 이는 데이터 타입이 컬럼에 있는 것이 아니라, **값(Value) 자체**에 저장된다는 뜻입니다. 이를 SQLite 문서에서는 'Manifest Typing'이라고 부릅니다.

예를 들어, `TEXT`로 정의된 컬럼에 숫자를 넣으려고 시도하면, SQLite는 에러를 내는 대신 숫자를 텍스트로 변환해서 저장해버립니다.

```sql
-- 일반적인 테이블 생성
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    account_balance INTEGER  -- 정수로 정의
);

-- 아래 INSERT는 SQLite에서 '성공'합니다.
-- 'balance'에 문자열을 넣으려고 시도했지만, SQLite는 이를 받아들입니다.
INSERT INTO users (username, account_balance) VALUES ('hacker', 'invalid_string');

-- 심지어 이렇게 다른 타입을 섞어서 넣어도 됩니다.
INSERT INTO users (username, account_balance) VALUES ('admin', 100);
``

이는 빠른 프로토타이핑에는 유용하지만, 금융 데이터나 로그 분석 시스템처럼 데이터 정합성이 중요한 경우에는 잠재적인 버그의 원인이 됩니다. Rust의 `struct`나 TypeScript의 인터페이스를 사용하다가, 데이터베이스 레벨에서는 이런 '같수패'가 발생하면 당황스러울 수밖에 없습니다.

## 해결책: STRICT 테이블 도입하기

`STRICT` 키워드를 사용하면 테이블은 강력한 타입 규칙(Strong typing rules)을 따르게 됩니다. Strict 테이블에서는 컬럼의 데이터 타입을 반드시 준수해야 하며, 그렇지 않을 경우 `SQLITE_CONSTRAINT_DATATYPE` 에러가 발생합니다.

### Strict 테이블 정의 문법

```sql
CREATE TABLE users_strict (
    id INTEGER PRIMARY KEY,
    username TEXT,
    account_balance INTEGER,
    created_at TEXT  -- 보통 ISO8601 문자열로 날짜를 관리
) STRICT;
``

위와 같이 테이블 정의 마지막에 `STRICT` 키워드만 붙이면 됩니다.

### 코드로 비교해보기

기존 테이블과 Strict 테이블의 동작 차이를 Python 코드로 확인해 보겠습니다.

```python
import sqlite3

def run_example():
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # 1. 일반 테이블 (유연함)
    cursor.execute('''
        CREATE TABLE normal_users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            age INTEGER
        )
    ''')
    
    try:
        # 에러 없이 '25' 문자열이 들어감 (내부적으로 처리됨)
        cursor.execute("INSERT INTO normal_users (name, age) VALUES (?, ?)", ('Alice', 'Twenty-Five'))
        print("[Normal Table] Inserted 'Twenty-Five' into INTEGER column. Success.")
        # 데이터 조회
        print(cursor.execute("SELECT * FROM normal_users").fetchall())
    except Exception as e:
        print(f"[Normal Table] Error: {e}")

    # 2. STRICT 테이블 (엄격함)
    cursor.execute('''
        CREATE TABLE strict_users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            age INTEGER
        ) STRICT
    ''')

    try:
        # STRICT 모드에서는 타입 불일치 시 에러 발생
        cursor.execute("INSERT INTO strict_users (name, age) VALUES (?, ?)", ('Bob', 'Thirty'))
        print("[Strict Table] Inserted 'Thirty' into INTEGER column. Success.")
    except sqlite3.IntegrityError as e:
        print(f"[Strict Table] Blocked invalid data! Error: {e}")

    # 정상적인 삽입
    cursor.execute("INSERT INTO strict_users (name, age) VALUES (?, ?)", ('Bob', 30))
    print("[Strict Table] Valid insert successful.")
    print(cursor.execute("SELECT * FROM strict_users").fetchall())

    conn.close()

if __name__ == '__main__':
    run_example()
```

**실행 결과:**
```
[Normal Table] Inserted 'Twenty-Five' into INTEGER column. Success.
[(1, 'Alice', 'Twenty-Five')]
[Strict Table] Blocked invalid data! Error: datatype mismatch
[Strict Table] Valid insert successful.
[(1, 'Bob', 30)]
```

보시다시피 Strict 테이블은 잘못된 타입의 데이터가 들어오는 즉시 에러를 반환하여 시스템의 신뢰성을 높여줍니다.

## Strict 테이블의 제약사항과 지원 타입

Strict 테이블을 사용할 때는 몇 가지 규칙을 염두에 두어야 합니다.

### 1. 허용되는 데이터 타입

Strict 테이블에서는 다음 5가지 타입만 사용할 수 있습니다.

*   **INTEGER** (부호 있는 정수)
*   **REAL** (부동 소수점)
*   **TEXT** (UTF-8/UTF-16 문자열)
*   **BLOB** (이진 데이터)
*   **ANY** (명시적으로 ANY를 지정하면 SQLite 2/3 호환성을 위해 Dynamic typing을 허용)

`VARCHAR(255)`나 `BOOLEAN` 같은 일반적인 SQL 타입을 쓰고 싶다면 어떻게 해야 할까요? SQLite는 이를 **Affinity(친화성)** 규칙에 따라 위 5가지 타입으로 매핑합니다.

```sql
CREATE TABLE product (
    id INTEGER PRIMARY KEY,
    name TEXT,
    price NUMERIC,  -- STRICT 모드에서는 NUMERIC -> INTEGER 또는 REAL로 매핑됨
    is_available BOOLEAN -- STRICT 모드에서는 BOOLEAN -> NUMERIC (0 또는 1)으로 매핑됨
) STRICT;
```

Strict 모드에서는 `BOOLEAN` 타입에 `TRUE`/`FALSE` 문자열을 넣을 수 없고, 반드시 `0` 또는 `1`(Integer)을 넣어야 합니다. 이는 매우 엄격한 규칙이므로, 애플리케이션 계층에서 데이터를 변환해주는 로직이 필요할 수 있습니다.

### 2. Rowid와 Primary Key

Strict 테이블에서 `INTEGER PRIMARY KEY`는 반드시 별칭(Alias)이 아닌 진짜 Rowid가 됩니다. 만약 `WITHOUT ROWID` 옵션을 사용한다면 `INTEGER PRIMARY KEY`는 단순한 `NOT NULL INTEGER` 컬럼처럼 동작합니다.

## 실무 적용 가이드

기존 프로젝트에 적용하기 위한 SQL 마이그레이션 스크립트 예시입니다.

```sql
-- 기존 유연한 테이블 (위험)
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT,
    message TEXT,
    timestamp INTEGER
);

-- STRICT로 마이그레이션 (안전)
-- 1. 기존 테이블 백업
CREATE TABLE logs_backup AS SELECT * FROM logs;

-- 2. 기존 테이블 삭제
DROP TABLE logs;

-- 3. STRICT로 재생성
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL CHECK(level IN ('INFO', 'WARN', 'ERROR')), -- 타입 + 제약조건
    message TEXT NOT NULL,
    timestamp INTEGER NOT NULL
) STRICT;

-- 4. 데이터 복구 (데이터 타입이 안 맞는다면 여기서 에러가 발생하므로,
--    개발자가 데이터 정제 후 진행해야 함)
INSERT INTO logs SELECT * FROM logs_backup;
```

## 결론: SQLite을 'Toy'가 아닌 'Tool'로 사용하려면

Rust나 Go 같은 언어를 사용하며 타입 안전성(Type Safety)을 중요하게 생각하는 개발자라면, 데이터베이스 내부에서도 그 안전성이 보장되길 원할 것입니다.

`STRICT` 테이블은 설정 변경 없이 테이블 정의만으로 데이터 무결성을 보장해주는 강력한 도구입니다. 특히 **ZeroClaw와 같은 멀티 에이전트 시스템**이나 **모니터링 대시보드**처럼 로컬 환경이나 경량 컨테이너 환경에서 SQLite를 사용하는 경우, 서비스 장애로 이어질 수 있는 '엉뚱한 데이터'를 사전에 차단하는 데 큰 역할을 할 것입니다.

지금 바로 여러분의 스키마 정의 뒤에 `STRICT`를 붙여보세요. 데이터베이스가 여러분을 지켜줄 것입니다.

### 참고 자료
*   [SQLite Strict Tables Documentation](https://www.sqlite.org/stricttables.html)
*   [Hacker News Discussion: Prefer strict tables in SQLite](https://news.ycombinator.com/item?id=41029438)