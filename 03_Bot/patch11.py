# -*- coding: utf-8 -*-
import sys

path = "case_study_ai.py"
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

old = '''    except Exception as e:
        return f"(রিপোর্ট ছবি বিশ্লেষণে সমস্যা হয়েছে, স্কিপ করা হলো: {e})"'''
new = '''    except Exception as e:
        import traceback
        print(f"[case_study_ai] analyze_report_images FAILED: {e}")
        traceback.print_exc()
        return f"(রিপোর্ট ছবি বিশ্লেষণে সমস্যা হয়েছে, স্কিপ করা হলো: {e})"'''
if src.count(old) != 1:
    sys.exit("ABORT: analyze_report_images except block not found exactly once.")
src = src.replace(old, new, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("case_study_ai.py: debug logging added OK")
