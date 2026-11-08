# Postgres rules with examples

Condensed from https://github.com/supabase/agent-skills/tree/main/skills/supabase-postgres-best-practices/references
without the row level security rules. Table and column names are illustrative.

## Query performance

Index WHERE and JOIN columns:

```sql
/* slow: sequential scan on a large table */
select id from runs where account_id = $1 and status = 'running';
/* fix: a composite index, equality columns first */
create index concurrently runs_account_status_idx on runs (account_id, status);
```

Partial index for a hot subset, covering index to avoid heap fetches:

```sql
create index concurrently runs_active_idx on runs (account_id, created_at) where status = 'running';
create index concurrently devices_kind_idx on devices (account_id, kind) include (name);
```

Index every foreign key column: the parent's delete or update scans the child without it.

Index type by operator: btree for equality and range, gin for jsonb containment and arrays, gist
for ranges, brin for large append-ordered tables, hash only for pure equality.

## Access patterns

N+1 to one statement:

```sql
select id, name from devices where account_id = $1 and id = any($2::uuid[]);
```

Keyset pagination:

```sql
select id, created_at from events
where account_id = $1 and (created_at, id) > ($2, $3)
order by created_at, id limit $4;
```

Upsert, atomic and race-free:

```sql
insert into settings (account_id, key, value)
values ($1, $2, $3)
on conflict (account_id, key) do update set value = excluded.value;
```

Batch inserts: multi-row `values`, `insert ... select from unnest($1::text[], $2::text[])`, or
COPY for bulk loads; never one round trip per row.

## Concurrency and locking

Claim work without blocking other workers:

```sql
update jobs set state = 'running', started_at = now()
where id = (select id from jobs where state = 'pending' order by created_at limit 1 for update skip locked)
returning *;
```

Short transactions: do reads and external calls first, then open the transaction for the writes.
Lock rows in a consistent order (`order by id for update`) so two transactions cannot deadlock.
Advisory locks (`pg_advisory_xact_lock`) coordinate application-level work without row locks;
prefer the transaction-scoped form so a lost connection cannot leak the lock.

## Connections

Use a pool rather than a connection per request. With a transaction-mode pooler in front of the
server, session state (prepared statements, `SET`, advisory session locks, `LISTEN`) does not
survive between transactions: disable named prepared statements or use session mode for those
clients. Set `idle_in_transaction_session_timeout` so an abandoned transaction releases its locks.

## Schema design

- Data types: `timestamptz` not `timestamp`, `uuid` or `bigint` keys, `text` not `varchar(n)`
  without a reason, `numeric` for money, `boolean` not a 0/1 integer.
- Primary keys: follow the neighbouring tables; a random uuid key spreads inserts across the
  index, so do not also sort by it for pagination (add a timestamp).
- Lowercase snake_case identifiers; quoted mixed-case names break tools and generated code.
- Constraints: `NOT NULL` and `CHECK` encode invariants once. Add them to a populated table as
  `NOT VALID` then `VALIDATE CONSTRAINT`.
- Partition only a table that is both large and time-bound with a retention plan; partitioning
  adds planning cost and constraint rules.

## Monitoring and diagnostics

- `EXPLAIN (ANALYZE, BUFFERS)` shows actual rows, loops and buffer hits. A large gap between
  estimated and actual rows means stale or missing statistics. `ANALYZE` after a bulk load.
- `pg_stat_statements` ranks statements by total time and calls; read the top by total time, not
  by single-call latency.
- Autovacuum keeps statistics and bloat in check; a table with heavy churn (queue rows, progress
  updates) may need per-table autovacuum settings, set in a migration.

## Advanced

- Full-text search: a stored `tsvector` column with a gin index, not `ILIKE '%x%'`.
- jsonb: index the access path (`gin (payload jsonb_path_ops)` for containment, or an expression
  index on the extracted key). Prefer real columns for fields every query filters on.
