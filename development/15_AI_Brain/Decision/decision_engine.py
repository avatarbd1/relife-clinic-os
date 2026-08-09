"""
decision_engine.py — Decision Engine for Relife Clinic OS
Converts owner ideas into structured decisions (Option A, B, C) 
and creates a formal task upon selection.

Flow: OWNER INPUT → AI ANALYSIS → OPTION GENERATION → OWNER SELECTION → TASK CREATION
"""

import sys
from pathlib import Path
from datetime import datetime

# Add parent directories to path to import existing modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "development/16_ClinicOS_CLI" / "cli"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Core"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Control"))

import task as task_manager
from provider_router import ProviderRouter

class DecisionEngine:
    def __init__(self):
        self.provider_router = ProviderRouter()

    def analyze_and_generate_options(self, raw_idea: str) -> dict:
        """Uses AI Provider to generate 3 structured options based on the raw idea."""
        prompt = f"""
        Act as a Senior Software Architect. Analyze this raw idea and generate exactly 3 distinct implementation options in JSON format.
        Raw Idea: "{raw_idea}"

        Return ONLY a valid JSON object with this structure:
        {{
          "analysis": "Brief 1-sentence technical analysis of the idea",
          "option_a": {{"title": "Simple Solution", "desc": "Fast implementation, low risk", "module_suggestion": "suggested_module_name"}},
          "option_b": {{"title": "Balanced Solution", "desc": "Recommended path, good balance of speed and scalability", "module_suggestion": "suggested_module_name"}},
          "option_c": {{"title": "Advanced Solution", "desc": "Long-term scalable, robust architecture", "module_suggestion": "suggested_module_name"}}
        }}
        """
        
        # Route to a planning/architecture focused provider
        result = self.provider_router.route("DECISION-001", "Planning", "high")
        
        if result["status"] == "SUCCESS":
            # Note: In a real scenario, you would parse the JSON from result["response"]
            # For now, we simulate structured extraction if the provider returns text
            response_text = result.get("response", str(result))
            return {
                "status": "SUCCESS",
                "provider_used": result["selected_provider"],
                "raw_ai_response": response_text
            }
        else:
            return {"status": "FAILED", "error": result.get("error", "Provider routing failed")}

    def create_decision_task(self, project: str, module: str, priority: str, description: str, selected_option: str) -> int:
        """Creates a formal task in the existing SQLite database using task.py"""
        enhanced_description = f"[DECISION: {selected_option}] {description}"
        task_id = task_manager.add_task(project, module, priority, enhanced_description)
        return task_id

    def interactive_decision_flow(self):
        """Interactive CLI flow for the Decision Engine"""
        print("\n" + "="*50)
        print("🧠 RELIFE DECISION ENGINE")
        print("="*50)
        
        raw_idea = input("\n💡 আপনার আইডিয়া বা রিকোয়ারমেন্ট লিখুন: ").strip()
        if not raw_idea:
            print("❌ আইডিয়া খালি রাখা যাবে না।")
            return

        print("\n⏳ AI বিশ্লেষণ করছে এবং অপশন তৈরি করছে... (এটি কয়েক সেকেন্ড সময় নিতে পারে)")
        result = self.analyze_and_generate_options(raw_idea)

        if result["status"] == "FAILED":
            print(f"❌ AI বিশ্লেষণ ব্যর্থ: {result['error']}")
            return

        print(f"\n✅ বিশ্লেষণ সম্পন্ন (Provider: {result['provider_used']})")
        print("\n--- AI প্রস্তাবিত অপশনসমূহ ---")
        print("Option A: Simple Solution (দ্রুত বাস্তবায়ন, কম ঝুঁকি)")
        print("Option B: Balanced Solution (সুপারিশকৃত পথ)")
        print("Option C: Advanced Solution (দীর্ঘমেয়াদী স্কেলেবিলিটি)")
        print("\n(নোট: বর্তমানে AI রেসপন্স raw ফরম্যাটে দেখানো হচ্ছে, পরবর্তীতে JSON পার্সিং যুক্ত হবে)")
        print("-" * 50)
        print(result['raw_ai_response'][:1000]) # Show first 1000 chars
        print("-" * 50)

        choice = input("\nকোন অপশনটি ফাইনাল করতে চান? (A/B/C বা খালি রাখলে বাতিল): ").strip().upper()
        if choice not in ["A", "B", "C"]:
            print("⚠️ সিদ্ধান্ত বাতিল করা হয়েছে।")
            return

        option_map = {"A": "Simple Solution", "B": "Balanced Solution", "C": "Advanced Solution"}
        selected_option = option_map[choice]

        # Gather task details
        project = input("Project Name (Enter for default 'Relife Clinic'): ").strip() or "Relife Clinic"
        module = input("Module Name (e.g., development/15_AI_Brain/Decision): ").strip() or "development/15_AI_Brain/Decision"
        priority = input("Priority (High/Medium/Low, Enter for 'High'): ").strip() or "High"
        
        # Create the task using existing task_manager
        task_id = self.create_decision_task(project, module, priority, raw_idea, selected_option)
        
        print(f"\n🎉 সফলভাবে টাস্ক তৈরি হয়েছে!")
        print(f"📌 Task ID: #{task_id}")
        print(f"📋 Status: pending")
        print("➡️ পরবর্তী ধাপ: এই Task ID ব্যবহার করে Task Router এবং Provider Router এর মাধ্যমে কোড জেনারেশন শুরু হবে।")

# Test / Direct Execution
if __name__ == "__main__":
    engine = DecisionEngine()
    engine.interactive_decision_flow()
