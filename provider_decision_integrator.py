#!/usr/bin/env python3
"""
Provider Router + Decision Engine Integration
ReLife Clinic OS - Phase 1 Integration Module
"""

import json
import os
from datetime import datetime
from pathlib import Path

class DecisionRouter:
    """AI Decision Router for provider selection"""
    
    def __init__(self):
        self.providers = {
            "groq": {"status": "active", "priority": 1},
            "deepseek": {"status": "active", "priority": 2},
            "openai": {"status": "active", "priority": 3},
            "gemini": {"status": "active", "priority": 4}
        }
        self.decision_log = []
        
    def select_provider(self, task_type, task_complexity):
        """Select best provider based on task type and complexity"""
        decision = {
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            "complexity": task_complexity,
            "provider": None,
            "reason": ""
        }
        
        # Basic routing logic
        if task_complexity == "high":
            decision["provider"] = "deepseek"
            decision["reason"] = "DeepSeek for complex reasoning"
        elif task_type == "code_generation":
            decision["provider"] = "groq"
            decision["reason"] = "Groq for fast code generation"
        elif task_type == "analysis":
            decision["provider"] = "openai"
            decision["reason"] = "OpenAI for analysis"
        else:
            decision["provider"] = "gemini"
            decision["reason"] = "Gemini as default"
            
        self.decision_log.append(decision)
        return decision
    
    def get_stats(self):
        """Get routing statistics"""
        stats = {}
        for log in self.decision_log:
            provider = log["provider"]
            stats[provider] = stats.get(provider, 0) + 1
        return stats
    
    def save_log(self, filename="decision_log.json"):
        """Save decision log to file"""
        with open(filename, "w") as f:
            json.dump(self.decision_log, f, indent=2)
            
# Initialize router
router = DecisionRouter()
print("Decision Router initialized successfully")
print(f"Available providers: {list(router.providers.keys())}")
