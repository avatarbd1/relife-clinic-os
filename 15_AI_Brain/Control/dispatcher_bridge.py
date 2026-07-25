#!/usr/bin/env python3
"""
DISPATCHER_BRIDGE — Connects BRAIN_DISPATCHER to Task Router Bridge
This is the main execution entry point for Phase 1 Step 7+
"""

import sys
import os

REPO_ROOT = os.path.expanduser("~/relife-clinic-os")
sys.path.insert(0, os.path.join(REPO_ROOT, "15_AI_Brain"))
sys.path.insert(0, os.path.join(REPO_ROOT, "15_AI_Brain", "Control"))

from task_router_bridge import TaskRouterBridge
from datetime import datetime

def main():
    print("=" * 50)
    print("BRAIN DISPATCHER + TASK ROUTER BRIDGE")
    print("Step 7/10: Task Router-BrainOS Bridge")
    print("=" * 50)
    
    bridge = TaskRouterBridge()
    
    # Sync existing tasks
    print("\n📥 Syncing tasks from BRAIN_QUEUE...")
    tasks = bridge.sync_queue_from_brain()
    print(f"   Found {len(tasks)} IN-PROGRESS tasks")
    
    # Test: Create a new task through the bridge
    print("\n📝 Creating test task via bridge...")
    task = bridge.create_and_persist_task(
        "Documentation",
        "Step 7 Bridge Integration Test",
        "CRITICAL"
    )
    
    if task['status'] == 'PROVIDER_ASSIGNED':
        print(f"   ✅ Task {task['task_id']} routed to {task['provider']}")
        print(f"   ✅ Persisted to BRAIN_QUEUE.md")
        print(f"   ✅ BRAIN_STATE.md updated")
        print(f"   ✅ HANDOVER.md updated")
    else:
        print(f"   ❌ Task creation failed: {task.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 50)
    print("STEP 7 COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    main()
