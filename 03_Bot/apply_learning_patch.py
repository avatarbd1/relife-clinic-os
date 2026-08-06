# -*- coding: utf-8 -*-
"""
apply_learning_patch.py
bot.py-তে Daily Learning Engine (quiz + tip) ইন্টিগ্রেট করার প্যাচ।
রান করার আগে bot.py-এর একটা ব্যাকআপ (bot.py.bak_learning) রাখা হয়।
"""
import sys

PATH = "bot.py"
BACKUP = "bot.py.bak_learning"

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

with open(BACKUP, "w", encoding="utf-8") as f:
    f.write(content)

changes = []

# ---- Change 1: import ----
OLD1 = "import assessment_defs\nimport clinical_ai"
NEW1 = "import assessment_defs\nimport clinical_ai\nfrom learning import learning_engine"
c1 = content.count(OLD1)
if c1 == 1:
    content = content.replace(OLD1, NEW1)
    changes.append(("import learning_engine", True))
else:
    changes.append((f"import learning_engine (found {c1} matches, needed 1)", False))

# ---- Change 2: start() function ----
OLD2 = '''async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    context.user_data["staff"] = staff
    role = staff.get("Role", "")
    name = staff.get("Full_Name", "")
    await update.message.reply_text(
        f"স্বাগতম, {name}! ({role})\\nনিচের মেনু থেকে বেছে নাও 👇",
        reply_markup=_menu_keyboard(role),
    )'''

NEW2 = '''async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    context.user_data["staff"] = staff
    role = staff.get("Role", "")
    name = staff.get("Full_Name", "")
    staff_id = staff.get("Staff_ID", "")

    await update.message.reply_text(f"স্বাগতম, {name}! ({role})")

    if staff_id and not learning_engine.has_seen_quiz_today(staff_id):
        quiz = learning_engine.get_next_quiz(staff_id)
        context.user_data["pending_quiz"] = quiz
        buttons = [
            [InlineKeyboardButton(opt, callback_data=f"lquiz:{i}")]
            for i, opt in enumerate(quiz["options"])
        ]
        await update.message.reply_text(
            f"🧠 আজকের প্রশ্ন:\\n\\n{quiz['question']}",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    await _send_daily_tip_and_menu(update.message, context, staff)


async def _send_daily_tip_and_menu(message, context: ContextTypes.DEFAULT_TYPE, staff: dict):
    role = staff.get("Role", "")
    name = staff.get("Full_Name", "")
    staff_id = staff.get("Staff_ID", "")

    if not staff_id:
        await message.reply_text(
            "নিচের মেনু থেকে বেছে নাও 👇", reply_markup=_menu_keyboard(role)
        )
        return

    if learning_engine.has_seen_tip_today(staff_id):
        tip = learning_engine.get_todays_tip(staff_id, role)
    else:
        tip = learning_engine.get_next_tip(staff_id, role)
        learning_engine.record_tip_shown(staff_id, name, role, tip)

    await message.reply_text(
        f"💡 আজকের টিপ ({tip['category']}):\\n{tip['text']}\\n\\nনিচের মেনু থেকে বেছে নাও 👇",
        reply_markup=_menu_keyboard(role),
    )


async def learning_quiz_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    quiz = context.user_data.pop("pending_quiz", None)
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if quiz is None or staff is None:
        return
    selected_index = int(query.data.split(":")[1])
    role = staff.get("Role", "")
    name = staff.get("Full_Name", "")
    staff_id = staff.get("Staff_ID", "")

    correct = learning_engine.record_quiz_answer(staff_id, name, role, quiz, selected_index)
    mark = "✅ সঠিক!" if correct else "❌ ভুল।"
    chosen = quiz["options"][selected_index]
    await query.edit_message_text(
        f"🧠 {quiz['question']}\\n\\nতোমার উত্তর: {chosen}\\n{mark}\\n\\n📖 ব্যাখ্যা: {quiz['explanation']}"
    )
    await _send_daily_tip_and_menu(query.message, context, staff)'''

c2 = content.count(OLD2)
if c2 == 1:
    content = content.replace(OLD2, NEW2)
    changes.append(("start() function → quiz+tip flow", True))
else:
    changes.append((f"start() function (found {c2} matches, needed 1)", False))

# ---- Change 3: handler registration ----
OLD3 = '    app.add_handler(CommandHandler("start", start))\n    app.add_handler(CommandHandler("search", search_patient))'
NEW3 = ('    app.add_handler(CommandHandler("start", start))\n'
        '    app.add_handler(CallbackQueryHandler(learning_quiz_answer_callback, pattern="^lquiz:"))\n'
        '    app.add_handler(CommandHandler("search", search_patient))')
c3 = content.count(OLD3)
if c3 == 1:
    content = content.replace(OLD3, NEW3)
    changes.append(("CallbackQueryHandler registration", True))
else:
    changes.append((f"CallbackQueryHandler registration (found {c3} matches, needed 1)", False))

all_ok = all(ok for _, ok in changes)

if all_ok:
    with open(PATH, "w", encoding="utf-8") as f:
        f.write(content)

print("=" * 50)
for label, ok in changes:
    print(("✅ " if ok else "❌ ") + label)
print("=" * 50)

if all_ok:
    print(f"✅ সব পরিবর্তন সফল হয়েছে। bot.py আপডেট হয়েছে। (ব্যাকআপ: {BACKUP})")
    sys.exit(0)
else:
    print("❌ কিছু পরিবর্তন ব্যর্থ হয়েছে — bot.py পরিবর্তন করা হয়নি (কোনো আংশিক প্যাচ প্রয়োগ হয়নি)।")
    print("এই আউটপুটটা Claude-কে পাঠাও, ঠিক করে দেব।")
    sys.exit(1)
