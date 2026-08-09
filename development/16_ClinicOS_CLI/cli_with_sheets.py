#!/usr/bin/env python3
"""
ReLife Clinic OS CLI with Google Sheets Integration
"""

import sys, os, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sheets_sync import SheetsSync

# আপনার Google Sheets এর নাম
SHEET_NAME = "Relife_Clinic_OS_Database_Template_FIXED"

class ClinicWithSheets:
    def __init__(self):
        self.data_dir = "data"
        os.makedirs(self.data_dir, exist_ok=True)
        self.sheets = SheetsSync()
        self.sheets_connected = False
        self.running = True

    def load_json(self, f):
        try: return json.load(open(f))
        except: return []

    def save_json(self, f, d):
        json.dump(d, open(f, 'w'), indent=2)

    def connect_sheets(self):
        print(f"\n🔗 Connecting to: {SHEET_NAME}")
        if self.sheets.connect():
            sheet = self.sheets.get_or_create_sheet(SHEET_NAME)
            if sheet:
                self.sheets_connected = True
                print(f"✅ Connected to: {SHEET_NAME}")
                # দেখি কী কী ওয়ার্কশিট আছে
                try:
                    worksheets = sheet.worksheets()
                    print(f"   Sheets: {[w.title for w in worksheets]}")
                except:
                    pass
            else:
                print("⚠️ Could not open sheet, working offline")
        else:
            print("⚠️ Working offline")

    def sync_to_sheets(self):
        if not self.sheets_connected:
            print("❌ Not connected. Press 8 first!")
            return
        print("\n📤 Syncing...")
        pts = self.load_json(f"{self.data_dir}/patients.json")
        apps = self.load_json(f"{self.data_dir}/appointments.json")
        self.sheets.sync_patients(pts)
        self.sheets.sync_appointments(apps)
        print("✅ Done!")

    def pull_from_sheets(self):
        if not self.sheets_connected:
            print("❌ Not connected. Press 8 first!")
            return
        print("\n📥 Pulling from Google Sheets...")
        pts = self.sheets.pull_patients()
        apps = self.sheets.pull_appointments()
        self.save_json(f"{self.data_dir}/patients.json", pts)
        self.save_json(f"{self.data_dir}/appointments.json", apps)
        print(f"✅ Pulled: {len(pts)} patients, {len(apps)} appointments")

    def add_patient(self):
        name = input("  Name: ")
        phone = input("  Phone: ")
        p = {"name": name, "phone": phone, "created": datetime.now().isoformat()}
        pts = self.load_json(f"{self.data_dir}/patients.json")
        pts.append(p)
        self.save_json(f"{self.data_dir}/patients.json", pts)
        print(f"✅ '{name}' added!")
        if self.sheets_connected:
            self.sheets.sync_patients(pts)

    def list_patients(self):
        pts = self.load_json(f"{self.data_dir}/patients.json")
        if not pts: print("📭 No patients"); return
        print(f"\n📋 Patients ({len(pts)}):")
        for i, p in enumerate(pts, 1):
            print(f"  {i}. {p['name']} | 📞 {p['phone']}")

    def add_appointment(self):
        name = input("  Patient: ")
        date = input("  Date (YYYY-MM-DD): ")
        time = input("  Time (HH:MM): ")
        a = {"patient": name, "date": date, "time": time, "status": "scheduled"}
        apps = self.load_json(f"{self.data_dir}/appointments.json")
        apps.append(a)
        self.save_json(f"{self.data_dir}/appointments.json", apps)
        print(f"✅ Appointment: {name} | {date} | {time}")
        if self.sheets_connected:
            self.sheets.sync_appointments(apps)

    def list_appointments(self):
        apps = self.load_json(f"{self.data_dir}/appointments.json")
        if not apps: print("📭 No appointments"); return
        print(f"\n📅 Appointments ({len(apps)}):")
        for i, a in enumerate(apps, 1):
            print(f"  {i}. {a['patient']} | {a['date']} | {a['time']}")

    def stats(self):
        pts = self.load_json(f"{self.data_dir}/patients.json")
        apps = self.load_json(f"{self.data_dir}/appointments.json")
        print(f"\n📊 Statistics:")
        print(f"  Patients: {len(pts)}")
        print(f"  Appointments: {len(apps)}")
        print(f"  Sheets: {'✅ '+SHEET_NAME if self.sheets_connected else '❌ Offline'}")

    def menu(self):
        print(f"\n{'='*50}")
        print(f"  🏥 ReLife Clinic OS")
        print(f"  📊 {SHEET_NAME}")
        print(f"{'='*50}")
        print("  1. Add Patient")
        print("  2. List Patients")
        print("  3. Add Appointment")
        print("  4. List Appointments")
        print("  5. Statistics")
        print("  6. Sync ➡️ Google Sheets")
        print("  7. Pull ⬅️ Google Sheets")
        print("  8. Connect Google Sheets")
        print("  0. Exit")
        print(f"{'='*50}")

    def run(self):
        if os.path.exists('credentials.json') or os.path.exists('../credentials.json'):
            self.connect_sheets()

        while self.running:
            self.menu()
            c = input("\nChoose [0-8]: ").strip()
            if c == '1': self.add_patient()
            elif c == '2': self.list_patients()
            elif c == '3': self.add_appointment()
            elif c == '4': self.list_appointments()
            elif c == '5': self.stats()
            elif c == '6': self.sync_to_sheets()
            elif c == '7': self.pull_from_sheets()
            elif c == '8': self.connect_sheets()
            elif c == '0': print("\n👋 Goodbye!\n"); self.running = False
            else: print("❌ Invalid!")

if __name__ == "__main__":
    ClinicWithSheets().run()
