---
name: postgres-query-and-schema
description: PostgreSQL query, index, schema and migration practice. Use before writing or changing SQL, a table, column, index or constraint, a migration, or a queue or polling query, and when diagnosing slow queries, query plans, locking, connection exhaustion or bloat.
license: MIT
metadata:
  vended: opt-in
  author: supabase
  organization: Supabase
  version: "1.1.1"
---

# Postgres Query and Schema Practice

Source: https://github.com/supabase/agent-skills/tree/main/skills/supabase-postgres-best-practices (MIT; its rule files are condensed in `references/rules.md`).

Changes from the source: dropped the Supabase row level security, roles and hosting notes; condensed the rule files into one reference; added the lock-safe migration rules, expand and contract, and deferral to the repository's own query and migration tooling.

Rules are ordered by impact. Read `references/rules.md` for example SQL of each.

## The repository's own tooling comes first

- If the repository uses a query generator, an ORM or a migration tool, follow its AGENTS.md:
  where queries and migrations live, how they are numbered, which recipe regenerates code, which
  migration lint it runs. Never hand-edit generated code; change the source and regenerate, and
  commit the regenerated output with it.
- Pick the next migration number or timestamp above the highest on the default branch. Two open
  PRs can take the same number and nothing may catch it until deploy: before marking the PR ready,
  fetch the default branch, check your number is still next, and name it in the PR.
- Tests for SQL run against a real PostgreSQL (a container or the repository's test database),
  never a mock of the database.
- No personal data, credentials or real identifiers in a migration, query, fixture or doc.

## Query performance (critical)

- **Index WHERE and JOIN columns.** A sequential scan on a large table is the commonest slow
  query. Index every foreign key column too: cascades and joins scan the child otherwise.
- **Composite indexes**: equality columns first, then range or sort; a leading column serves
  prefix queries. **Partial indexes** for a hot filtered subset (`where state = 'pending'`).
  **Covering indexes** (`include`) to avoid heap fetches on a hot read. Pick the index type that
  matches the operator (btree, gin for jsonb and arrays, brin for append-ordered data).
- **Read the plan, not the query.** `EXPLAIN (ANALYZE, BUFFERS)` against realistic row counts;
  compare estimated and actual rows. Stale statistics give wrong plans: `ANALYZE` after bulk
  loads.
- Never `select *` on a wide table when the caller needs two columns.

## Access patterns

- **Eliminate N+1**: one `= any($1)` query or a join, not a query per row.
- **Keyset pagination** (`where (created_at, id) > ($1, $2) order by created_at, id limit $3`),
  never deep `OFFSET`.
- **Batch writes**: multi-row insert, `unnest` arrays or COPY; `INSERT ... ON CONFLICT DO UPDATE`
  for atomic upsert instead of select-then-write.
- **Queues and polling**: claim work with `FOR UPDATE SKIP LOCKED` in one statement; poll with a
  partial index over the runnable states and a bound, with `LISTEN`/`NOTIFY` or the job library's
  wake-up as the primary signal where one exists. Do not add a second polling loop beside an
  existing job library.

## Concurrency and locking

- **Keep transactions short.** No network call, external API call or sleep inside a transaction;
  an idle-in-transaction connection holds locks and a pool slot.
- **Lock in a consistent order** (by primary key) to prevent deadlocks. Use transaction-scoped
  advisory locks for application-level coordination and keep their scope narrow.
- **Respect the connection limit.** Every pool, worker and replica multiplies connections. Size
  pools against the server's `max_connections` minus a reserve, hold a connection only while you
  use it, and set statement and idle-in-transaction timeouts on anything new. Say in the PR which
  pool or replica count you changed.

## Schema

- `timestamptz`, not `timestamp`; `text` unless a length limit is a real rule; `numeric` for
  money; lowercase snake_case identifiers. Follow the neighbouring tables for key type and
  audit columns.
- `NOT NULL` and `CHECK` encode invariants once, at the write path.
- Never store a plaintext credential.
- Do not add row level security or database roles unless the repository already uses them;
  authorization normally lives in the application.

## Migrations

- **Expand and contract.** A migration in release N adds nullable columns, tables, indexes or enum
  values and backfills in a way both N-1 and N can read. It never drops or renames what N-1 reads;
  that waits for N+1.
- Set a `lock_timeout` for migrations (or keep the tool's default); never set it to 0.
- `CREATE INDEX` and `DROP INDEX` on an existing table: use `CONCURRENTLY`, outside a transaction.
  Do not write `CREATE INDEX CONCURRENTLY IF NOT EXISTS`: it skips an INVALID index left by a
  failed build, the migration is recorded as applied, and the index never works. Drop the invalid
  index and create it without `IF NOT EXISTS`.
- `ADD COLUMN ... NOT NULL` needs a constant `DEFAULT` (or add it nullable). A volatile default,
  serial, identity or stored generated column rewrites the table: add a new column and backfill.
- `CHECK` and `FOREIGN KEY` constraints on a populated table: add them `NOT VALID`, then
  `VALIDATE CONSTRAINT` in a later statement. PostgreSQL supports `NOT VALID` only for these two.
- `ADD UNIQUE` or `PRIMARY KEY`: build the index with `CREATE UNIQUE INDEX CONCURRENTLY` first,
  then `ADD CONSTRAINT ... USING INDEX`. For a primary key, every key column must already be
  `NOT NULL`, or attaching the key scans the table under its lock.
- `EXCLUDE` constraints have no concurrent build: declare one when the table is created, or plan
  the lock with a maintainer.
- `SET NOT NULL`: validate a `NOT VALID` check constraint (`col is not null`) first.
- `ALTER COLUMN TYPE`, table rewrites and `LOCK TABLE`: avoid; backfill into a new column.
- A bulk `UPDATE` or `DELETE` inside a migration holds row locks for its whole transaction: batch
  it outside the migration.

## Done

SQL is done when its plan was read against realistic row counts, every new foreign key and hot
filter has an index or a stated reason, migrations are lock-safe and readable by the previous
release, generated code matches its source, and the database-backed tests ran.
