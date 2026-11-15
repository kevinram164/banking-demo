import os
import time
from sqlalchemy import text
from common.db import engine

print("diag start", flush=True)
t0 = time.time()
with engine.connect() as c:
    print("ping", c.execute(text("select 1")).scalar(), round(time.time() - t0, 2), flush=True)
    rows = c.execute(
        text(
            """
            select pid, state, wait_event_type, wait_event,
                   extract(epoch from (now()-xact_start))::int as xact_s,
                   extract(epoch from (now()-query_start))::int as query_s,
                   left(query, 120) as query
            from pg_stat_activity
            where datname = current_database()
              and pid <> pg_backend_pid()
              and (
                state = 'idle in transaction'
                or wait_event_type = 'Lock'
                or state = 'active'
              )
            order by xact_start nulls last
            """
        )
    ).fetchall()
    print("interesting_sessions", len(rows), flush=True)
    for r in rows[:40]:
        print(dict(r._mapping), flush=True)

    locks = c.execute(
        text(
            """
            select count(*) as waiting_locks
            from pg_locks where NOT granted
            """
        )
    ).scalar()
    print("ungranted_locks", locks, flush=True)

    pending = c.execute(
        text("select count(*) from transfers where status='PENDING'")
    ).scalar()
    print("pending_transfers", pending, flush=True)
