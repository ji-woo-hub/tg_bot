./bootenv/bin/python - << 'EOF'
import sqlite3

conn = sqlite3.connect("suguan.db")
cursor = conn.cursor()

cursor.execute("""
SELECT id, user_id, date, day, time_12, locale, role, language, status
FROM schedules
ORDER BY id DESC
LIMIT 5
""")

rows = cursor.fetchall()
for r in rows:
    print(r)

conn.close()
EOF
