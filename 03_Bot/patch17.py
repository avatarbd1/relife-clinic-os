# -*- coding: utf-8 -*-
import sys

path = "case_study_ai.py"
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

# ১) VISION_MODEL বদলানো
old_vm = 'VISION_MODEL = "google/gemma-4-31b-it:free"'
new_vm = 'VISION_MODEL = "openai/gpt-4o-mini"'
if src.count(old_vm) != 1:
    sys.exit("ABORT: VISION_MODEL line not found exactly once.")
src = src.replace(old_vm, new_vm, 1)

# ২) Vision prompt আপডেট — physiotherapist নিজে film পড়েন, তাই AI-কে সহায়ক
# দ্বিতীয় পর্যবেক্ষণ দিতে বলা হচ্ছে, শুধু "স্পষ্ট না হলে চুপ" না বলে।
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
    sys.exit("ABORT: vision content prompt block not found exactly once.")
src = src.replace(old_prompt, new_prompt, 1)

# ৩) Error handling ঠিক করা — raw exception case_text-এ না ঢুকিয়ে safe message দেওয়া
old_except = '''    except Exception as e:
        import traceback
        print(f"[case_study_ai] analyze_report_images FAILED: {e}")
        traceback.print_exc()
        return f"(রিপোর্ট ছবি বিশ্লেষণে সমস্যা হয়েছে, স্কিপ করা হলো: {e})"'''

new_except = '''    except Exception as e:
        import traceback
        print(f"[case_study_ai] analyze_report_images FAILED: {e}")
        traceback.print_exc()
        return "(এই ছবি/রিপোর্ট থেকে এই মুহূর্তে বিশ্লেষণ সম্ভব হয়নি। রোগীর লিখিত/জানানো তথ্যের ভিত্তিতেই এগোনো হচ্ছে।)"'''

if src.count(old_except) != 1:
    sys.exit("ABORT: analyze_report_images except block not found exactly once.")
src = src.replace(old_except, new_except, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("case_study_ai.py: patch17 applied OK (vision model -> gpt-4o-mini, therapist-oriented prompt, safe error message)")
