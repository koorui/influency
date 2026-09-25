import time
from sqlalchemy import text
from .db import engine

for attempt in range(60):
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        print('MySQL ready')
        break
    except Exception:
        time.sleep(2)
else:
    raise SystemExit('Database did not become ready within 120 seconds')
