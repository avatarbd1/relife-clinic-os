# -*- coding: utf-8 -*-
import sys

# ---------- case_study_ai.py: vision analysis ফাংশন যোগ করা ----------
path1 = "case_study_ai.py"
with open(path1, "r", encoding="utf-8") as f:
    src1 = f.read()

if "analyze_report_images" in src1:
    print("case_study_ai.py: already patched — skip")
else:
    vision_addition = '''

VISION_MODEL = "google/gemma-4-31b-it:free"


def analyze_report_images(image_data_list: list) -> str:
    """রিপোর্টের ছবি (X-ray/MRI/অন্য রিপোর্ট) বিশ্লেষণ করে সংক্ষিপ্ত ফাইন্ডিংস ফেরত দেয়।
    image_data_list: [{"base64": str, "mime_type": str, "file_name": str}, ...]
    ফ্রি ভিশন মডেল ব্যবহার করে (OpenRouter :free) — লিমিটেড রেট, তাই রোগী প্রতি সীমিত ছবি পাঠানো হয়।"""
    if not OPENROUTER_API_KEY or not image_data_list:
        return ""

    content = [{
        "type": "text",
        "text": (
            "তুমি একজন Physiotherapy Clinical Tutor। নিচের রিপোর্ট/ইমেজগুলো দেখে "
            "প্রতিটার জন্য সংক্ষেপে (২-৩ লাইন) কী Finding দেখা যাচ্ছে লিখো। "
            "নিশ্চিত না হলে স্পষ্ট বলো 'স্পষ্ট বোঝা যাচ্ছে না'। কিছু বানিয়ে লিখো না। "
            "মেডিক্যাল Terminology ইংরেজিতে রাখো, বাকিটা বাংলায়।"
        ),
    }]
    for img in image_data_list:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{img.get('mime_type', 'image/jpeg')};base64,{img.get('base64', '')}"},
        })

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": VISION_MODEL,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": 700,
            },
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"(রিপোর্ট ছবি বিশ্লেষণে সমস্যা হয়েছে, স্কিপ করা হলো: {e})"
'''
    src1 = src1 + vision_addition
    with open(path1, "w", encoding="utf-8") as f:
        f.write(src1)
    print("case_study_ai.py: patched OK")

# ---------- bot.py: টেলিগ্রাম থেকে ছবি ডাউনলোড + কেস টেক্সটে জোড়া ----------
path2 = "bot.py"
with open(path2, "r", encoding="utf-8") as f:
    src2 = f.read()

if "_download_report_images" in src2:
    sys.exit("bot.py already patched (_download_report_images exists) — nothing to do.")

if "import base64" not in src2:
    src2 = src2.replace("import os\n", "import os\nimport base64\n", 1)

anchor = "async def casestudy_extra_receive(update, context):"
if src2.count(anchor) != 1:
    sys.exit("ABORT: casestudy_extra_receive anchor not found once — check with: grep -n 'async def casestudy_extra_receive' bot.py")

helper = '''async def _download_report_images(context, patient_id: str, limit: int = 2) -> list:
    """রোগীর সাম্প্রতিক ছবি-রিপোর্ট (X-ray/MRI ইত্যাদি) টেলিগ্রাম থেকে সরাসরি ডাউনলোড করে
    (Drive-এর দরকার নেই, File_Telegram_ID দিয়েই হয়)। সর্বোচ্চ `limit` টা ছবি নেয়
    (ফ্রি ভিশন মডেলের রেট-লিমিট বাঁচাতে)।"""
    reports = sheets.get_reports_for_patient(patient_id)
    image_reports = [r for r in reports if str(r.get("File_Type", "")).lower().startswith("image")]
    image_reports = image_reports[-limit:]
    out = []
    for r in image_reports:
        file_id = r.get("File_Telegram_ID", "")
        if not file_id:
            continue
        try:
            file_obj = await context.bot.get_file(file_id)
            file_bytes = await file_obj.download_as_bytearray()
            b64 = base64.b64encode(bytes(file_bytes)).decode("utf-8")
            out.append({
                "base64": b64,
                "mime_type": r.get("File_Type") or "image/jpeg",
                "file_name": r.get("File_Name", ""),
            })
        except Exception:
            continue
    return out


'''
src2 = src2.replace(anchor, helper + anchor, 1)

start_fn = "async def casestudy_extra_receive(update, context):"
end_fn = "async def casestudy_lesson_callback(update, context):"
si = src2.find(start_fn)
ei = src2.find(end_fn)
if si == -1 or ei == -1 or ei <= si:
    sys.exit("ABORT: casestudy_extra_receive/casestudy_lesson_callback boundary not found.")

new_fn = '''async def casestudy_extra_receive(update, context):
    text = update.message.text.strip()
    case_context = context.user_data.get("cs_case_context", "")
    extra = "" if text in ("না", "না।", "no", "No", "No.") else text
    case_text = case_context + (f"\\n\\nবাড়তি তথ্য: {extra}" if extra else "")

    patient_id = context.user_data.get("cs_patient_id", "")
    images = await _download_report_images(context, patient_id, limit=2)
    if images:
        await update.message.reply_text("\\U0001F50D রিপোর্টের ছবি দেখছি...")
        vision_notes = case_study_ai.analyze_report_images(images)
        if vision_notes:
            case_text += f"\\n\\nরিপোর্ট ছবি বিশ্লেষণ (AI Vision):\\n{vision_notes}"

    context.user_data["cs_case_text"] = case_text
    context.user_data["cs_lesson"] = 1
    await update.message.reply_text("\\U0001F914 কেস বিশ্লেষণ করছি, Lesson 1 তৈরি হচ্ছে...")
    answer = case_study_ai.answer_case_lesson(case_text, 1)
    staff = context.user_data.get("staff", {})
    try:
        sheets.add_case_study_lesson(
            context.user_data.get("cs_session_id", ""),
            context.user_data.get("cs_patient_id", ""),
            context.user_data.get("cs_patient_name", ""),
            1,
            case_study_ai.LESSON_TITLES[0],
            answer,
            staff.get("Full_Name") or staff.get("Name") or str(staff.get("Staff_ID", "")),
        )
    except Exception:
        pass
    await update.message.reply_text(answer, reply_markup=_cslesson_next_keyboard())
    return CASESTUDY_LESSON


'''
src2 = src2[:si] + new_fn + src2[ei:]

with open(path2, "w", encoding="utf-8") as f:
    f.write(src2)
print("bot.py: patched OK")
print("DONE")
