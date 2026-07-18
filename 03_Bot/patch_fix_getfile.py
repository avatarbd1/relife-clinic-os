with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_line = '            await context.bot.send_document(chat_id=query.message.chat_id, document=tg_id, caption=caption)'
new_line = '''            if str(record.get("File_Type", "")).strip() == "Photo":
                await context.bot.send_photo(chat_id=query.message.chat_id, photo=tg_id, caption=caption)
            else:
                await context.bot.send_document(chat_id=query.message.chat_id, document=tg_id, caption=caption)'''

if old_line in content:
    content = content.replace(old_line, new_line, 1)
    print("✅ প্যাচ হয়েছে")
else:
    print("⚠️ অ্যাঙ্কর মেলেনি")

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)
