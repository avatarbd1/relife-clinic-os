import os,sys,unittest
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
