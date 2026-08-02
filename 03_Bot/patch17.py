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

# ২) Error handling ঠিক করা — raw exception case_text-এ না ঢুকিয়ে safe message দেওয়া
old_except = '''    except Exception as e:
        import traceback
        print(f"[case_study_ai] analyze_report_images FAILED: {e}")
        traceback.print_exc()
        return f"(রিপোর্ট ছবি বিশ্লেষণে সমস্যা হয়েছে, স্কিপ করা হলো: {e})"'''

new_except = '''    except Exception as e:
        import traceback
        print(f"[case_study_ai] analyze_report_images FAILED: {e}")
        traceback.print_exc()
        # raw error message case_text-এ ঢুকিয়ে AI-কে বিভ্রান্ত করা ঠিক না —
        # তাই শুধু একটা safe, informative note দেওয়া হচ্ছে, technical error না।
        return "(এই ছবি/রিপোর্ট থেকে এই মুহূর্তে বিশ্লেষণ সম্ভব হয়নি। রোগীর লিখিত/জানানো তথ্যের ভিত্তিতেই এগোনো হচ্ছে।)"'''

if src.count(old_except) != 1:
    sys.exit("ABORT: analyze_report_images except block not found exactly once.")
src = src.replace(old_except, new_except, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("case_study_ai.py: patch17 applied OK (vision model -> gpt-4o-mini, safe error message)")
