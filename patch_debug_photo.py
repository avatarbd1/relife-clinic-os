path = "/data/data/com.termux/files/home/relife-clinic-os/03_Bot/bot.py"
src = open(path, encoding="utf-8").read()

old = '''    try:
        extracted = photo_extract.extract_from_photo(image_bytes)
    except Exception:
        logger.exception("photo_extract failed")
        extracted = None'''

new = '''    debug_error = None
    try:
        extracted = photo_extract.extract_from_photo(image_bytes)
    except Exception as e:
        logger.exception("photo_extract failed")
        extracted = None
        debug_error = f"{type(e).__name__}: {e}"'''

assert src.count(old) == 1, f"anchor found {src.count(old)} times"
src = src.replace(old, new, 1)

old2 = '''    if not found_lines:
        await update.message.reply_text(
            "⚠️ ছবি থেকে তথ্য পড়া যায়নি। নিজে লিখতে হবে।\\nনতুন রোগীর পূর্ণ নাম লেখো:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return REG_NAME'''

new2 = '''    if not found_lines:
        debug_line = f"\\n\\n🔧 Debug: {debug_error}" if debug_error else ""
        await update.message.reply_text(
            f"⚠️ ছবি থেকে তথ্য পড়া যায়নি। নিজে লিখতে হবে।{debug_line}\\nনতুন রোগীর পূর্ণ নাম লেখো:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return REG_NAME'''

assert src.count(old2) == 1, f"anchor2 found {src.count(old2)} times"
src = src.replace(old2, new2, 1)

open(path, "w", encoding="utf-8").write(src)
print("✅ debug info যুক্ত হয়েছে")
