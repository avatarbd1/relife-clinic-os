#!/usr/bin/env python3
"""Route Dental staff data to the dedicated Dental spreadsheet."""
from pathlib import Path

ROOT=Path.home()/"relife-clinic-os"
CFG=ROOT/"03_Bot"/"config.py"
SHEETS=ROOT/"03_Bot"/"sheets.py"
BOT=ROOT/"03_Bot"/"bot.py"
SCOPE=ROOT/"03_Bot"/"sheet_scope.py"
TEST=ROOT/"07_Testing"/"test_two_sheet_router.py"

def edit(path,old,new,label):
    text=path.read_text(encoding="utf-8")
    if new in text:
        print(label+": ✅ already applied"); return
    if text.count(old)!=1:
        raise SystemExit(f"❌ {label}: anchor count {text.count(old)}")
    path.write_text(text.replace(old,new,1),encoding="utf-8")
    print(label+": ✅ applied")

scope='''"""Request-local data spreadsheet selection."""
from contextlib import contextmanager
from contextvars import ContextVar

_sheet_override = ContextVar("relife_data_sheet_override", default=None)

def current_sheet_override():
    return _sheet_override.get()

def bind_sheet(sheet_id: str):
    if not str(sheet_id or "").strip():
        raise ValueError("sheet_id is required")
    return _sheet_override.set(str(sheet_id).strip())

@contextmanager
def use_sheet(sheet_id: str):
    token=bind_sheet(sheet_id)
    try:
        yield
    finally:
        _sheet_override.reset(token)
'''
SCOPE.write_text(scope,encoding="utf-8")

edit(CFG,'GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")\n','GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")\nDENTAL_GOOGLE_SHEET_ID = os.getenv("DENTAL_GOOGLE_SHEET_ID")\n',"config dental id")
edit(SHEETS,'import department_access\n','import department_access\nimport sheet_scope\n',"sheets scope import")
edit(SHEETS,'''def _active_sheet_id() -> str:
    if config.MULTITENANT_ENABLED:
        return current_tenant().sheet_id
    return config.GOOGLE_SHEET_ID
''','''def _active_sheet_id() -> str:
    override = sheet_scope.current_sheet_override()
    if override:
        return override
    if config.MULTITENANT_ENABLED:
        return current_tenant().sheet_id
    return config.GOOGLE_SHEET_ID
''',"active sheet override")

old='''def get_staff_by_telegram_id(telegram_id: int) -> dict | None:
    ws = _worksheet(config.SHEET_STAFF)
    records = safe_get_all_records(ws)
    for row in records:
        if str(row.get("Telegram_ID", "")).strip() == str(telegram_id):
            if str(row.get("Status", "")).strip().lower() == "inactive":
                return None
            return row
    return None
'''
new='''def get_staff_by_telegram_id(telegram_id: int) -> dict | None:
    # 08_Staff on the Physio workbook is the common staff registry.
    with sheet_scope.use_sheet(config.GOOGLE_SHEET_ID):
        ws = _worksheet(config.SHEET_STAFF)
        records = safe_get_all_records(ws)
    for row in records:
        if str(row.get("Telegram_ID", "")).strip() == str(telegram_id):
            if str(row.get("Status", "")).strip().lower() == "inactive":
                return None
            return row
    return None
'''
edit(SHEETS,old,new,"common staff lookup")

old='''    records = safe_get_all_records(_worksheet(config.SHEET_STAFF))
    target = str(staff_id or "").strip()
'''
new='''    with sheet_scope.use_sheet(config.GOOGLE_SHEET_ID):
        records = safe_get_all_records(_worksheet(config.SHEET_STAFF))
    target = str(staff_id or "").strip()
'''
edit(SHEETS,old,new,"common department lookup")
edit(BOT,'import sheets\n','import sheets\nimport sheet_scope\n',"bot scope import")
old='''        staff["_Department_Mappings"] = mappings
        staff["_Department_Role_Assignments"] = assignments

    context.user_data["staff"] = staff
'''
new='''        staff["_Department_Mappings"] = mappings
        staff["_Department_Role_Assignments"] = assignments
        departments = {assignment.department for assignment in assignments}
        if departments == {department_access.Department.DENTAL}:
            if not config.DENTAL_GOOGLE_SHEET_ID:
                await update.effective_message.reply_text(
                    "⛔ Dental Sheet ID সেট করা নেই। Owner-কে জানাও।"
                )
                return None
            sheet_scope.bind_sheet(config.DENTAL_GOOGLE_SHEET_ID)
        else:
            sheet_scope.bind_sheet(config.GOOGLE_SHEET_ID)

    context.user_data["staff"] = staff
'''
edit(BOT,old,new,"bind staff data sheet")

test='''import os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"03_Bot"))
os.environ.setdefault("BOT_TOKEN","test")
os.environ.setdefault("GOOGLE_SHEET_ID","physio")
os.environ.setdefault("DENTAL_GOOGLE_SHEET_ID","dental")
cred=ROOT/"credentials.json"; made=not cred.exists()
if made: cred.write_text("{}")
import config,sheet_scope,sheets
def tearDownModule():
    if made: cred.unlink(missing_ok=True)
class RouterTests(unittest.TestCase):
    def tearDown(self): sheet_scope._sheet_override.set(None)
    def test_default_is_physio(self): self.assertEqual(sheets._active_sheet_id(),"physio")
    def test_dental_override(self):
        sheet_scope.bind_sheet("dental")
        self.assertEqual(sheets._active_sheet_id(),"dental")
    def test_registry_scope_restores_dental(self):
        sheet_scope.bind_sheet("dental")
        with sheet_scope.use_sheet("physio"):
            self.assertEqual(sheets._active_sheet_id(),"physio")
        self.assertEqual(sheets._active_sheet_id(),"dental")
if __name__=="__main__": unittest.main()
'''
TEST.write_text(test,encoding="utf-8")
print("test_two_sheet_router.py: ✅ created")
print("\nRun:")
print("python3 -m py_compile 03_Bot/config.py 03_Bot/sheet_scope.py 03_Bot/sheets.py 03_Bot/bot.py")
print("python3 -m unittest 07_Testing/test_two_sheet_router.py 07_Testing/test_staff_single_source.py 07_Testing/test_department_access.py -v")
print("git add 03_Bot/config.py 03_Bot/sheet_scope.py 03_Bot/sheets.py 03_Bot/bot.py 07_Testing/test_two_sheet_router.py relife_patch10.py")
print("git commit -m 'Route Dental staff to dedicated spreadsheet' && git push")
