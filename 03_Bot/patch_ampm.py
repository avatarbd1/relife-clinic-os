import re

path = 'bot.py'
src = open(path, encoding='utf-8').read()

old_0 = "import config\nimport sheets\nimport roles"
new_0 = "import config\nimport sheets\nimport roles\n\n\ndef fmt_time_ampm(t):\n    \"\"\"Convert stored 'HH:MM' (24h) to 12-hour 'hh:mm AM/PM'.\"\"\"\n    if not t:\n        return t\n    t = str(t).strip()\n    if \"AM\" in t.upper() or \"PM\" in t.upper():\n        return t\n    try:\n        return datetime.strptime(t, \"%H:%M\").strftime(\"%I:%M %p\").lstrip(\"0\")\n    except ValueError:\n        return t"
if src.count(old_0) == 1:
    src = src.replace(old_0, new_0)
    print('✅ patch 1/10 applied')
else:
    print('❌ patch 1/10 FAILED (found', src.count(old_0), 'matches)')

old_1 = "status_line = f\"🟢 Check In: {record.get('Check_In')}\""
new_1 = "status_line = f\"🟢 Check In: {fmt_time_ampm(record.get('Check_In'))}\""
if src.count(old_1) == 1:
    src = src.replace(old_1, new_1)
    print('✅ patch 2/10 applied')
else:
    print('❌ patch 2/10 FAILED (found', src.count(old_1), 'matches)')

old_2 = "status_line = f\"☕ Break Out: {record.get('Break_Out')}\""
new_2 = "status_line = f\"☕ Break Out: {fmt_time_ampm(record.get('Break_Out'))}\""
if src.count(old_2) == 1:
    src = src.replace(old_2, new_2)
    print('✅ patch 3/10 applied')
else:
    print('❌ patch 3/10 FAILED (found', src.count(old_2), 'matches)')

old_3 = "status_line = f\"🔙 Break In: {record.get('Break_In')}\""
new_3 = "status_line = f\"🔙 Break In: {fmt_time_ampm(record.get('Break_In'))}\""
if src.count(old_3) == 1:
    src = src.replace(old_3, new_3)
    print('✅ patch 4/10 applied')
else:
    print('❌ patch 4/10 FAILED (found', src.count(old_3), 'matches)')

old_4 = "f\"Check In: {record.get('Check_In')}\\nCheck Out: {record.get('Check_Out')}\\n\""
new_4 = "f\"Check In: {fmt_time_ampm(record.get('Check_In'))}\\nCheck Out: {fmt_time_ampm(record.get('Check_Out'))}\\n\""
if src.count(old_4) == 1:
    src = src.replace(old_4, new_4)
    print('✅ patch 5/10 applied')
else:
    print('❌ patch 5/10 FAILED (found', src.count(old_4), 'matches)')

old_5 = "await query.edit_message_text(f\"✅ Check In হয়েছে: {time_str}\")"
new_5 = "await query.edit_message_text(f\"✅ Check In হয়েছে: {fmt_time_ampm(time_str)}\")"
if src.count(old_5) == 1:
    src = src.replace(old_5, new_5)
    print('✅ patch 6/10 applied')
else:
    print('❌ patch 6/10 FAILED (found', src.count(old_5), 'matches)')

old_6 = "await query.edit_message_text(f\"☕ Break শুরু: {time_str}\" if time_str else \"❌ আজকের রেকর্ড পাওয়া যায়নি।\")"
new_6 = "await query.edit_message_text(f\"☕ Break শুরু: {fmt_time_ampm(time_str)}\" if time_str else \"❌ আজকের রেকর্ড পাওয়া যায়নি।\")"
if src.count(old_6) == 1:
    src = src.replace(old_6, new_6)
    print('✅ patch 7/10 applied')
else:
    print('❌ patch 7/10 FAILED (found', src.count(old_6), 'matches)')

old_7 = "await query.edit_message_text(f\"🔙 Break শেষ: {time_str}\" if time_str else \"❌ আজকের রেকর্ড পাওয়া যায়নি।\")"
new_7 = "await query.edit_message_text(f\"🔙 Break শেষ: {fmt_time_ampm(time_str)}\" if time_str else \"❌ আজকের রেকর্ড পাওয়া যায়নি।\")"
if src.count(old_7) == 1:
    src = src.replace(old_7, new_7)
    print('✅ patch 8/10 applied')
else:
    print('❌ patch 8/10 FAILED (found', src.count(old_7), 'matches)')

old_8 = "f\"🚪 Check Out হয়েছে: {result['time']}\\n\""
new_8 = "f\"🚪 Check Out হয়েছে: {fmt_time_ampm(result['time'])}\\n\""
if src.count(old_8) == 1:
    src = src.replace(old_8, new_8)
    print('✅ patch 9/10 applied')
else:
    print('❌ patch 9/10 FAILED (found', src.count(old_8), 'matches)')

old_9 = "f\"🐛 {bug.get('Bug_ID', '')} — {bug.get('Date', '')} {bug.get('Time', '')}\\n\""
new_9 = "f\"🐛 {bug.get('Bug_ID', '')} — {bug.get('Date', '')} {fmt_time_ampm(bug.get('Time', ''))}\\n\""
if src.count(old_9) == 1:
    src = src.replace(old_9, new_9)
    print('✅ patch 10/10 applied')
else:
    print('❌ patch 10/10 FAILED (found', src.count(old_9), 'matches)')

open(path, 'w', encoding='utf-8').write(src)
print('Done — bot.py updated.')
