#!/usr/bin/env python3
import sys, os, json
from datetime import datetime

class ClinicCommands:
    def __init__(self):
        self.data_dir = "data"
        os.makedirs(self.data_dir, exist_ok=True)
        
    def load_json(self, f):
        try: return json.load(open(f))
        except: return []
    
    def save_json(self, f, d):
        json.dump(d, open(f, 'w'), indent=2)
        
    def add_patient(self, name, phone):
        p = {"name": name, "phone": phone, "created": datetime.now().isoformat()}
        pts = self.load_json(f"{self.data_dir}/patients.json")
        pts.append(p)
        self.save_json(f"{self.data_dir}/patients.json", pts)
        print(f"✅ Patient '{name}' added!")
        
    def list_patients(self):
        pts = self.load_json(f"{self.data_dir}/patients.json")
        if not pts: print("📭 No patients"); return
        print("\n📋 Patients:")
        for i, p in enumerate(pts, 1): print(f"  {i}. {p['name']} | {p['phone']}")
        
    def add_appointment(self, name, date, time):
        a = {"patient": name, "date": date, "time": time, "status": "scheduled"}
        apps = self.load_json(f"{self.data_dir}/appointments.json")
        apps.append(a)
        self.save_json(f"{self.data_dir}/appointments.json", apps)
        print(f"✅ Appointment: {name} on {date} at {time}")
        
    def list_appointments(self):
        apps = self.load_json(f"{self.data_dir}/appointments.json")
        if not apps: print("📭 No appointments"); return
        print("\n📅 Appointments:")
        for i, a in enumerate(apps, 1): print(f"  {i}. {a['patient']} | {a['date']} | {a['time']}")
        
    def stats(self):
        pts = self.load_json(f"{self.data_dir}/patients.json")
        apps = self.load_json(f"{self.data_dir}/appointments.json")
        print(f"\n📊 Stats: {len(pts)} patients | {len(apps)} appointments\n")

class CLI:
    def __init__(self):
        self.cmd = ClinicCommands()
        self.cmds = {
            "1": ("Add Patient", self.add_patient),
            "2": ("List Patients", self.list_patients),
            "3": ("Add Appointment", self.add_appointment),
            "4": ("List Appointments", self.list_appointments),
            "5": ("Stats", self.stats),
            "0": ("Exit", self.exit_cli),
        }
        self.running = True
        
    def menu(self):
        print("\n" + "="*40)
        print("  🏥 ReLife Clinic OS")
        print("="*40)
        for k, (name, _) in self.cmds.items():
            print(f"  {k}. {name}")
        print("="*40)
        
    def add_patient(self):
        self.cmd.add_patient(input("Name: "), input("Phone: "))
    def list_patients(self): self.cmd.list_patients()
    def add_appointment(self):
        self.cmd.add_appointment(input("Patient: "), input("Date (YYYY-MM-DD): "), input("Time: "))
    def list_appointments(self): self.cmd.list_appointments()
    def stats(self): self.cmd.stats()
    def exit_cli(self):
        print("\n👋 Goodbye!\n")
        self.running = False
        
    def run(self):
        while self.running:
            self.menu()
            c = input("\nChoose: ").strip()
            if c in self.cmds: self.cmds[c][1]()
            else: print("❌ Invalid!")

if __name__ == "__main__":
    CLI().run()
