#!/usr/bin/env python3
"""ReLife Clinic OS - Main CLI Interface"""

import sys
import os
from datetime import datetime

class ClinicCLI:
    def __init__(self):
        self.version = "1.0.0"
        self.commands = {
            "help": self.show_help,
            "status": self.show_status,
            "version": self.show_version,
            "exit": self.exit_cli,
            "quit": self.exit_cli,
        }
        self.running = True
        
    def show_banner(self):
        print(f"""
╔══════════════════════════════════════════╗
║         ReLife Clinic OS CLI              ║
║         Clinic Management System          ║
║         Version: {self.version}                    ║
╚══════════════════════════════════════════╝
        """)
        
    def show_help(self):
        print("\n📋 Available Commands:")
        print("  help     - Show this help")
        print("  status   - Show system status")
        print("  version  - Show CLI version")
        print("  exit     - Exit CLI\n")
        
    def show_status(self):
        print(f"\n📊 System Status:")
        print(f"  Date: {datetime.now().strftime('%Y-%m-%d')}")
        print(f"  Time: {datetime.now().strftime('%H:%M:%S')}")
        print("  Status: ✅ Online\n")
        
    def show_version(self):
        print(f"\n🔢 ReLife Clinic OS CLI v{self.version}\n")
        
    def exit_cli(self):
        print("\n👋 Goodbye!")
        self.running = False
        
    def run(self):
        self.show_banner()
        print("Type 'help' for commands.\n")
        
        while self.running:
            try:
                command = input("clinic-os> ").strip().lower()
                if command in self.commands:
                    self.commands[command]()
                elif command == "":
                    continue
                else:
                    print(f"❌ Unknown: {command}")
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break

if __name__ == "__main__":
    cli = ClinicCLI()
    cli.run()
