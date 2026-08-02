# -*- coding: utf-8 -*-
import sys

path1 = "case_study_ai.py"
with open(path1, "r", encoding="utf-8") as f:
    src1 = f.read()

old_lang_line = '''- বাংলায় শেখাও, Medical Terms ইংরেজিতে রাখো।'''
new_lang_line = '''- ভাষার নিয়ম কড়াভাবে মানো: রোগীর সাথে সরাসরি সম্পর্কিত অংশ — History taking-এ কী প্রশ্ন করবে, Chief Complaint নেওয়া, রোগীকে কী বলবে — এগুলো স্বাভাবিক সহজ বাংলায় লিখো। কিন্তু সব মেডিক্যাল Terminology, Test-এর নাম, Condition-এর নাম, Muscle/Joint/Nerve-এর নাম ইংরেজিতেই রাখো, বাংলায় অনুবাদ কোরো না (যেমন "bowel", "ROM", "MMT", "dermatome", "hamstring" — এগুলো ইংরেজিতেই লিখবে, বাংলা প্রতিশব্দ বানিয়ে লিখবে না)। বাকি ব্যাখ্যা/বর্ণনা বাংলায় লিখো।'''
if old_lang_line not in src1:
    sys.exit("ABORT: language line not found in LESSON_SYSTEM_PROMPT — file drift, check manually.")
src1 = src1.replace(old_lang_line, new_lang_line, 1)

old_curr_note = '''5. কেস অস্পষ্ট/অসম্পূর্ণ মনে হলেও, যতটুকু তথ্য আছে তা দিয়ে best-guess উত্তর দাও — প্রশ্ন করে সময় নষ্ট কোরো না।"""'''
new_curr_note = '''5. কেস অস্পষ্ট/অসম্পূর্ণ মনে হলেও, যতটুকু তথ্য আছে তা দিয়ে best-guess উত্তর দাও — প্রশ্ন করে সময় নষ্ট কোরো না।
6. ভাষা: সাধারণ ব্যাখ্যা বাংলায় লিখবে, কিন্তু মেডিক্যাল Terminology (Test নাম, Condition নাম, Muscle/Joint/Nerve নাম) ইংরেজিতেই রাখবে, বাংলা অনুবাদ কোরো না।"""'''
if old_curr_note not in src1:
    sys.exit("ABORT: CURRICULUM_CONTEXT closing note not found — file drift, check manually.")
src1 = src1.replace(old_curr_note, new_curr_note, 1)

with open(path1, "w", encoding="utf-8") as f:
    f.write(src1)
print("case_study_ai.py: language rule patched OK")
