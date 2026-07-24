#!/usr/bin/env python3
"""Advanced Commands for ClinicOS CLI"""

import json
import os
from datetime import datetime

class ClinicCommands:
    def __init__(self):
        self.data_dir = "data"
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
    def add_patient(self, name, phone, age=None, gender=None):
        patient = {
            "name": name,
            "phone": phone,
            "age": age,
            "gender": gender,
            "created_at": datetime.now().isoformat(),
            "visits": []
        }
        filename = f"{self.data_dir}/patients.json"
        patients = self.load_json(filename)
        patients.append(patient)
        self.save_json(filename, patients)
        print(f"✅ Patient '{name}' added!")
        return patient
    
    def list_patients(self):
        filename = f"{self.data_dir}/patients.json"
        patients = self.load_json(filename)
        if not patients:
            print("📭 No patients found.")
            return []
        print("\n📋 Patient List:")
        print("-" * 50)
        for i, p in enumerate(patients, 1):
            print(f"{i}. {p['name']} | 📞 {p['phone']} | 🗓 {p['created_at'][:10]}")
        print("-" * 50)
        return patients
    
    def add_appointment(self, patient_name, date, time, doctor="Dr. Default"):
        appointment = {
            "patient": patient_name,
            "date": date,
            "time": time,
            "doctor": doctor,
            "status": "scheduled",
            "created_at": datetime.now().isoformat()
        }
        filename = f"{self.data_dir}/appointments.json"
        appointments = self.load_json(filename)
        appointments.append(appointment)
        self.save_json(filename, appointments)
        print(f"✅ Appointment for '{patient_name}' on {date} at {time} added!")
        return appointment
    
    def list_appointments(self):
        filename = f"{self.data_dir}/appointments.json"
        appointments = self.load_json(filename)
        if not appointments:
            print("📭 No appointments found.")
            return []
        print("\n📅 Appointment List:")
        print("-" * 60)
        for i, a in enumerate(appointments, 1):
            icon = "✅" if a['status'] == 'scheduled' else "❌"
            print(f"{i}. {a['patient']} | {a['date']} | {a['time']} | {a['doctor']} {icon}")
        print("-" * 60)
        return appointments
    
    def load_json(self, filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def save_json(self, filename, data):
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

    def get_stats(self):
        patients = self.load_json(f"{self.data_dir}/patients.json")
        appointments = self.load_json(f"{self.data_dir}/appointments.json")
        today = datetime.now().strftime('%Y-%m-%d')
        today_appts = [a for a in appointments if a['date'] == today]
        print("\n📊 Clinic Statistics:")
        print(f"  Total Patients: {len(patients)}")
        print(f"  Total Appointments: {len(appointments)}")
        print(f"  Today's Appointments: {len(today_appts)}\n")
