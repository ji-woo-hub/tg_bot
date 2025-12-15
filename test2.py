./bootenv/bin/python - << 'EOF'
from datetime import datetime, timedelta

schedule = datetime.strptime("12-15-2025 14:30", "%m-%d-%Y %H:%M")
reminder = schedule - timedelta(hours=3)

print("Now:", datetime.now())
print("Schedule:", schedule)
print("Reminder:", reminder)
print("Reminder in future?", reminder > datetime.now())
EOF
