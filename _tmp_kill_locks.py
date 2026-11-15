from sqlalchemy import text
from common.db import engine

KILL_SQL = """
SELECT pg_terminate_backend(pid), pid, state,
       extract(epoch from (now()-xact_start))::int as xact_s,
       left(query, 100) as query
FROM pg_stat_activity
WHERE datname = current_database()
  AND pid <> pg_backend_pid()
  AND (
    state = 'idle in transaction'
    OR (state = 'active' AND wait_event_type = 'Lock')
  );
"""

with engine.connect() as c:
    rows = c.execute(text(KILL_SQL)).fetchall()
    c.commit()
    print("terminated", len(rows), flush=True)
    for r in rows:
        print(dict(r._mapping), flush=True)
