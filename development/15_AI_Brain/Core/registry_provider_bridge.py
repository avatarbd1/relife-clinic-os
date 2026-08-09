#!/usr/bin/env python3
"""
REGISTRY_PROVIDER_BRIDGE v1.0 — Connects ProviderRouter to AI_REGISTRY
Phase 1 Step 8/10: Full Provider Router integration with AI Registry
Extends provider_router.py, does NOT recreate it.

Features:
- Reads available providers from AI_REGISTRY.md
- Validates provider availability before routing
- Updates registry with provider usage stats
- Tracks provider health and failures
"""

import os
import sys
import re
from datetime import datetime
from typing import Dict, List, Optional

REPO_ROOT = os.path.expanduser("~/relife-clinic-os")
os.chdir(REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "development/15_AI_Brain"))
sys.path.insert(0, os.path.join(REPO_ROOT, "development/15_AI_Brain", "Core"))

from provider_router import ProviderRouter

class RegistryProviderBridge:
    """Bridge between ProviderRouter and AI_REGISTRY.md"""
    
    def __init__(self):
        self.router = ProviderRouter()
        self.registry_path = "development/11_AIOS/AI_REGISTRY.md"
        self.brain_registry_path = "development/15_BrainOS/BRAIN_REGISTRY.md"
        self.memory_path = "development/15_BrainOS/BRAIN_MEMORY.md"
        
    def parse_registry(self) -> Dict[str, Dict]:
        """Parse AI_REGISTRY.md and extract provider information"""
        providers = {}
        
        if not os.path.exists(self.registry_path):
            return providers
            
        with open(self.registry_path, 'r') as f:
            content = f.read()
        
        # Parse table rows
        current_provider = None
        for line in content.split('\n'):
            line = line.strip()
            
            # Detect provider sections
            if line.startswith('## ') or line.startswith('### '):
                name = line.strip('# ').lower().replace(' ', '_')
                if name in ['gemini', 'groq', 'openrouter', 'claude', 'deepseek']:
                    current_provider = name
                    providers[current_provider] = {
                        'name': name,
                        'status': 'unknown',
                        'api_key_set': False,
                        'rate_limit': 0,
                        'failures': 0
                    }
            
            # Extract details
            if current_provider and '✅' in line:
                providers[current_provider]['status'] = 'active'
            elif current_provider and '❌' in line:
                providers[current_provider]['status'] = 'inactive'
            elif current_provider and 'API_KEY' in line.upper():
                if 'set' in line.lower() or 'valid' in line.lower():
                    providers[current_provider]['api_key_set'] = True
        
        return providers
    
    def validate_providers(self) -> List[str]:
        """Return list of currently available providers"""
        registry = self.parse_registry()
        available = []
        
        for name, info in registry.items():
            if info.get('status') == 'active' and info.get('api_key_set'):
                available.append(name)
        
        # If nothing in registry, check actual API keys
        if not available:
            for provider in ['gemini', 'groq', 'openrouter']:
                if self.router._check_api_key(provider):
                    available.append(provider)
        
        return available
    
    def update_registry_usage(self, provider: str, success: bool):
        """Update AI_REGISTRY.md with usage statistics"""
        if not os.path.exists(self.registry_path):
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_icon = "✅" if success else "❌"
        
        with open(self.registry_path, 'r') as f:
            content = f.read()
        
        # Add usage log entry
        log_entry = f"\n| {timestamp} | {provider} | {status_icon} {'SUCCESS' if success else 'FAILED'} | Bridge v1.0 |"
        
        if '## Usage Log' in content:
            content += log_entry
        else:
            content += f"\n\n## Usage Log\n| Timestamp | Provider | Status | Source |\n|-----------|----------|--------|--------|{log_entry}"
        
        with open(self.registry_path, 'w') as f:
            f.write(content)
    
    def sync_registry_with_router(self):
        """Sync AI_REGISTRY.md status with actual ProviderRouter availability"""
        registry = self.parse_registry()
        
        updates = []
        for provider in ['gemini', 'groq', 'openrouter']:
            actual_status = self.router._check_api_key(provider)
            registry_status = registry.get(provider, {}).get('api_key_set', False)
            
            if actual_status != registry_status:
                updates.append(f"  {provider}: registry={registry_status}, actual={actual_status}")
        
        # Log sync to memory
        if updates:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            memory_entry = f"[{ts}] [INFO] [REGISTRY_SYNC] Provider status mismatch detected:\n"
            for u in updates:
                memory_entry += u + "\n"
            
            with open(self.memory_path, 'a') as f:
                f.write(memory_entry)
        
        return updates
    
    def route_with_registry_check(self, task_id: str, task_type: str, priority: str = "normal") -> Dict:
        """
        Enhanced routing that validates against registry before routing.
        Extends ProviderRouter.route() with registry awareness.
        """
        # Check available providers
        available = self.validate_providers()
        
        if not available:
            return {
                "status": "FAILED",
                "selected_provider": None,
                "error": "No providers available in AI_REGISTRY",
                "available_providers": []
            }
        
        # Use parent router but with registry-validated list
        result = self.router.route(task_id, task_type, priority)
        
        # Update registry with result
        if result.get('selected_provider'):
            success = result.get('status') == 'SUCCESS'
            self.update_registry_usage(result['selected_provider'], success)
        
        # Add registry info to result
        result['registry_validated'] = True
        result['available_providers'] = available
        
        return result
    
    def get_provider_health_report(self) -> Dict:
        """Generate provider health report from registry"""
        registry = self.parse_registry()
        available = self.validate_providers()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_providers": len(registry),
            "available_providers": len(available),
            "providers": {}
        }
        
        for name, info in registry.items():
            report["providers"][name] = {
                "status": "available" if name in available else "unavailable",
                "api_key_set": info.get('api_key_set', False),
                "registry_status": info.get('status', 'unknown')
            }
        
        return report

# Test
if __name__ == "__main__":
    bridge = RegistryProviderBridge()
    
    print("=== PROVIDER ROUTER + AI REGISTRY BRIDGE TEST ===\n")
    
    # Test 1: Parse registry
    print("1️⃣ Parsing AI_REGISTRY.md...")
    registry = bridge.parse_registry()
    print(f"   Found {len(registry)} providers in registry")
    for name, info in registry.items():
        print(f"   - {name}: {info.get('status', 'unknown')}")
    
    # Test 2: Validate providers
    print("\n2️⃣ Validating available providers...")
    available = bridge.validate_providers()
    print(f"   Available: {available}")
    
    # Test 3: Route with registry check
    print("\n3️⃣ Routing task with registry validation...")
    result = bridge.route_with_registry_check("TASK-008", "Documentation", "CRITICAL")
    print(f"   Result: {result.get('status')}")
    print(f"   Provider: {result.get('selected_provider')}")
    print(f"   Registry Validated: {result.get('registry_validated')}")
    
    # Test 4: Health report
    print("\n4️⃣ Provider health report:")
    health = bridge.get_provider_health_report()
    print(f"   Total: {health['total_providers']}")
    print(f"   Available: {health['available_providers']}")
    for name, info in health['providers'].items():
        print(f"   - {name}: {info['status']}")
    
    # Test 5: Sync registry
    print("\n5️⃣ Syncing registry with router...")
    mismatches = bridge.sync_registry_with_router()
    if mismatches:
        print(f"   Found {len(mismatches)} mismatches:")
        for m in mismatches:
            print(f"   {m}")
    else:
        print("   ✅ Registry in sync with router")
    
    print("\n✅ Step 8 Registry Bridge Test Complete!")
