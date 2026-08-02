# -*- coding: utf-8 -*-
import sys

path = "case_study_ai.py"
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

old_prompt = '''    content = [{
        "type": "text",
        "text": (
            "তুমি একজন Physiotherapy Clinical Tutor। নিচের রিপোর্ট/ইমেজগুলো দেখে "
            "প্রতিটার জন্য সংক্ষেপে (২-৩ লাইন) কী Finding দেখা যাচ্ছে লিখো। "
            "নিশ্চিত না হলে স্পষ্ট বলো 'স্পষ্ট বোঝা যাচ্ছে না'। কিছু বানিয়ে লিখো না। "
            "মেডিক্যাল Terminology ইংরেজিতে রাখো, বাকিটা বাংলায়।"
        ),
    }]'''

new_prompt = '''    content = [{
        "type": "text",
        "text": (
            "তুমি একজন Physiotherapy Clinical Tutor, এবং ব্যবহারকারী একজন অভিজ্ঞ Physiotherapist "
            "যিনি নিজেই X-ray/MRI film পড়তে অভ্যস্ত। নিচের রিপোর্ট/ইমেজগুলো দেখে প্রতিটার জন্য "
            "সংক্ষেপে (৩-৪ লাইন) যা কিছু চোখে পড়ছে তা নির্দিষ্টভাবে লিখো — যেমন vertebral level "
            "marker, visible hardware/implant, gross alignment/curvature, disc space narrowing, "
            "বা অন্য কোনো visible abnormality। যতটা স্পষ্ট ততটা specific ভাষায় বলো, কিন্তু কোনো "
            "চূড়ান্ত Diagnosis নিজে থেকে ঘোষণা কোরো না — এটা AI-এর প্রাথমিক পর্যবেক্ষণ মাত্র, "
            "চূড়ান্ত সিদ্ধান্ত therapist নিজের clinical film-reading দিয়ে নেবেন। কিছু বানিয়ে লিখো না — "
            "ছবির মান/angle-এর কারণে কোনো অংশ বোঝা না গেলে সেটা স্পষ্টভাবে উল্লেখ করো। "
            "মেডিক্যাল Terminology ইংরেজিতে রাখো, বাকিটা বাংলায়।"
        ),
    }]'''

if src.count(old_prompt) != 1:
    sys.exit("ABORT: vision content prompt block not found exactly once (already patched or text mismatch).")
src = src.replace(old_prompt, new_prompt, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("case_study_ai.py: patch18 applied OK (therapist-oriented specific-but-honest vision prompt)")
