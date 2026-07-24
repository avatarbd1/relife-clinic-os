#!/usr/bin/env python3
"""Google Sheets Sync - আপনার spreadsheet এর জন্য কাস্টমাইজড"""
import json, os, gspread
from oauth2client.service_account import ServiceAccountCredentials

class SheetsSync:
    def __init__(self):
        self.scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        self.credentials_file = None
        self.client = None
        self.spreadsheet = None
        # আপনার spreadsheet এর শিট নেইম
        self.PATIENTS_SHEET = "02_Patients"
        self.APPOINTMENTS_SHEET = "04_Appointments"
        self.find_credentials()
        
    def find_credentials(self):
        paths = ['credentials.json', '../credentials.json', '../../credentials.json']
        for p in paths:
            if os.path.exists(p):
                self.credentials_file = p
                print(f"✅ Found: {p}")
                return
        print("⚠️ No credentials found")
        
    def connect(self):
        if not self.credentials_file: return False
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.credentials_file, self.scope)
            self.client = gspread.authorize(creds)
            print("✅ Connected!")
            return True
        except Exception as e:
            print(f"❌ Connect failed: {e}")
            return False
    
    def get_or_create_sheet(self, sheet_name="ClinicOS"):
        if not self.client:
            print("❌ Not connected")
            return None
        try:
            all_sheets = self.client.list_spreadsheet_files()
            for s in all_sheets:
                if s['name'] == sheet_name:
                    self.spreadsheet = self.client.open_by_key(s['id'])
                    print(f"✅ Using: {sheet_name}")
                    return self.spreadsheet
            print(f"Creating: {sheet_name}...")
            self.spreadsheet = self.client.create(sheet_name)
            print(f"✅ Created: {sheet_name}")
            return self.spreadsheet
        except Exception as e:
            error_msg = str(e)
            if "quota" in error_msg.lower():
                print("❌ Google Drive FULL! Free up space:")
                print("   https://drive.google.com/drive/quota")
            else:
                print(f"❌ Error: {e}")
            return None
    
    def sync_patients(self, data):
        """Sync patients to 02_Patients sheet"""
        if not self.spreadsheet: return
        try:
            ws = self.spreadsheet.worksheet(self.PATIENTS_SHEET)
        except:
            ws = self.spreadsheet.add_worksheet(self.PATIENTS_SHEET, 1000, 10)
        
        # Get existing data to preserve headers
        existing = ws.get_all_values()
        headers = existing[0] if existing else ["Name", "Phone", "Created"]
        
        ws.clear()
        ws.append_row(headers)
        for p in data:
            ws.append_row([p.get('name',''), p.get('phone',''), p.get('created','')])
        print(f"✅ {len(data)} patients synced to {self.PATIENTS_SHEET}!")
    
    def sync_appointments(self, data):
        """Sync appointments to 04_Appointments sheet"""
        if not self.spreadsheet: return
        try:
            ws = self.spreadsheet.worksheet(self.APPOINTMENTS_SHEET)
        except:
            ws = self.spreadsheet.add_worksheet(self.APPOINTMENTS_SHEET, 1000, 10)
        
        existing = ws.get_all_values()
        headers = existing[0] if existing else ["Patient", "Date", "Time", "Status"]
        
        ws.clear()
        ws.append_row(headers)
        for a in data:
            ws.append_row([a.get('patient',''), a.get('date',''), a.get('time',''), a.get('status','')])
        print(f"✅ {len(data)} appointments synced to {self.APPOINTMENTS_SHEET}!")
    
    def pull_patients(self):
        """Pull patients from 02_Patients sheet"""
        if not self.spreadsheet: return []
        try:
            ws = self.spreadsheet.worksheet(self.PATIENTS_SHEET)
            records = ws.get_all_records()
            patients = []
            for row in records:
                patients.append({
                    'name': row.get('Name', row.get('Patient Name', '')),
                    'phone': row.get('Phone', row.get('Contact', '')),
                    'created': row.get('Created', row.get('Date', ''))
                })
            print(f"✅ Pulled {len(patients)} patients from {self.PATIENTS_SHEET}")
            return patients
        except Exception as e:
            print(f"❌ Pull patients failed: {e}")
            return []
    
    def pull_appointments(self):
        """Pull appointments from 04_Appointments sheet"""
        if not self.spreadsheet: return []
        try:
            ws = self.spreadsheet.worksheet(self.APPOINTMENTS_SHEET)
            records = ws.get_all_records()
            appointments = []
            for row in records:
                appointments.append({
                    'patient': row.get('Patient', row.get('Patient Name', '')),
                    'date': row.get('Date', ''),
                    'time': row.get('Time', ''),
                    'status': row.get('Status', 'scheduled')
                })
            print(f"✅ Pulled {len(appointments)} appointments from {self.APPOINTMENTS_SHEET}")
            return appointments
        except Exception as e:
            print(f"❌ Pull appointments failed: {e}")
            return []
    
    def get_all_sheets(self):
        """List all worksheets"""
        if self.spreadsheet:
            return [w.title for w in self.spreadsheet.worksheets()]
        return []
