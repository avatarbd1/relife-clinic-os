# -*- coding: utf-8 -*-
import sys, re

# ---------- drive.py: ডাউনলোড ফাংশন যোগ করা ----------
path0 = "drive.py"
with open(path0, "r", encoding="utf-8") as f:
    src0 = f.read()

if "download_file_from_drive" in src0:
    print("drive.py: already patched — skip")
else:
    if "from googleapiclient.http import MediaFileUpload" in src0 and "MediaIoBaseDownload" not in src0:
        src0 = src0.replace(
            "from googleapiclient.http import MediaFileUpload",
            "from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload",
            1,
        )
    if "import io" not in src0:
        src0 = "import io\n" + src0

    download_fn = '''

def download_file_from_drive(file_id: str) -> bytes | None:
    """Drive থেকে file_id দিয়ে ফাইলের raw bytes ডাউনলোড করে।"""
    try:
        service = get_drive_service()
        request = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _status, done = downloader.next_chunk()
        return buf.getvalue()
    except Exception:
        return None
'''
    src0 = src0 + download_fn
    with open(path0, "w", encoding="utf-8") as f:
        f.write(src0)
    print("drive.py: patched OK")

# ---------- bot.py: Drive-কে প্রধান সোর্স বানানো, Telegram file_id ফলব্যাক ----------
path2 = "bot.py"
with open(path2, "r", encoding="utf-8") as f:
    src2 = f.read()

if "_extract_drive_file_id" in src2:
    sys.exit("bot.py already patched (_extract_drive_file_id exists) — nothing to do.")

if "import drive" not in src2 and "import drive as drive_module" not in src2:
    sys.exit("ABORT: bot.py-তে drive module import লাইন খুঁজে পাইনি. Run: grep -n '^import drive\\|drive_module' bot.py")

old_helper_start = "async def _download_report_images(context, patient_id: str, limit: int = 4) -> list:"
if src2.count(old_helper_start) != 1:
    sys.exit("ABORT: _download_report_images signature not found exactly once (check limit value).")

old_fn_start = old_helper_start
old_fn_end = "async def casestudy_extra_receive(update, context):"
si = src2.find(old_fn_start)
ei = src2.find(old_fn_end)
if si == -1 or ei == -1 or ei <= si:
    sys.exit("ABORT: _download_report_images function boundary not found.")

new_fn = '''def _extract_drive_file_id(drive_link: str) -> str:
    """Google Drive webViewLink থেকে raw file ID বের করে (যেমন
    https://drive.google.com/file/d/XXXX/view -> XXXX)।"""
    if not drive_link:
        return ""
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", drive_link)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", drive_link)
    if m:
        return m.group(1)
    return ""


async def _download_report_images(context, patient_id: str, limit: int = 4) -> list:
    """রোগীর সাম্প্রতিক ছবি-রিপোর্ট (X-ray/MRI ইত্যাদি) ডাউনলোড করে।
    আগে Google Drive থেকে চেষ্টা করে (স্থায়ী, প্রোডাকশনে reliable), Drive লিংক না থাকলে
    বা ফেইল করলে Telegram file_id দিয়ে ফলব্যাক করে। সর্বোচ্চ `limit` টা ছবি নেয়
    (ফ্রি ভিশন মডেলের রেট-লিমিট বাঁচাতে)।"""
    reports = sheets.get_reports_for_patient(patient_id)
    image_reports = [r for r in reports if str(r.get("File_Type", "")).lower().startswith("image")]
    image_reports = image_reports[-limit:]
    out = []
    for r in image_reports:
        img_bytes = None

        drive_link = r.get("File_Drive_Link", "")
        drive_file_id = _extract_drive_file_id(drive_link)
        if drive_file_id:
            img_bytes = drive_module.download_file_from_drive(drive_file_id)

        if img_bytes is None:
            file_id = r.get("File_Telegram_ID", "")
            if file_id:
                try:
                    file_obj = await context.bot.get_file(file_id)
                    file_bytes = await file_obj.download_as_bytearray()
                    img_bytes = bytes(file_bytes)
                except Exception:
                    img_bytes = None

        if img_bytes is None:
            continue

        b64 = base64.b64encode(img_bytes).decode("utf-8")
        out.append({
            "base64": b64,
            "mime_type": r.get("File_Type") or "image/jpeg",
            "file_name": r.get("File_Name", ""),
        })
    return out


'''
src2 = src2[:si] + new_fn + src2[ei:]

if "\nimport re\n" not in src2 and not src2.startswith("import re\n"):
    src2 = src2.replace("import os\n", "import os\nimport re\n", 1)

with open(path2, "w", encoding="utf-8") as f:
    f.write(src2)
print("bot.py: patched OK")
print("DONE")
