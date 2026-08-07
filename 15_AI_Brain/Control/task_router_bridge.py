#!/usr/bin/env python3
"""
TASK_ROUTER_BRIDGE v1.0 — Connects TaskRouter to BrainOS
Phase 1 Step 7/10: Task Router-BrainOS bridge
Extends TASK_ROUTER.py, does NOT recreate it.

Integration points:
- Reads from BRAIN_QUEUE.md
- Writes to BRAIN_QUEUE.md, BRAIN_STATE.md, HANDOVER.md
- Updates AI_REGISTRY.md for worker tracking
"""

import os
import re
import sys
from datetime import datetime

REPO_ROOT = os.path.expanduser("~/relife-clinic-os")
os.chdir(REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "15_AI_Brain"))
sys.path.insert(0, os.path.join(REPO_ROOT, "15_AI_Brain", "Control"))

from TASK_ROUTER import TaskRouter

class TaskRouterBridge:
    """Bridge between TaskRouter and BrainOS file system"""
    
    def __init__(self):
        self.router = TaskRouter()
        self.brain_queue_path = "15_BrainOS/BRAIN_QUEUE.md"
        self.brain_state_path = "15_BrainOS/BRAIN_STATE.md"
        self.handover_path = "12_Handover/HANDOVER.md"
        self.registry_path = "11_AIOS/AI_REGISTRY.md"
        
    def sync_queue_from_brain(self):
        """Read BRAIN_QUEUE.md and load tasks into TaskRouter"""
        if not os.path.exists(self.brain_queue_path):
            return []
        
        tasks_loaded = []
        with open(self.brain_queue_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('|') and 'IN-PROGRESS' in line:
                    parts = [p.strip() for p in line.split('|') if p.strip()]
                    if len(parts) >= 6:
                        task_id, task_type, priority, status, assigned, created = parts[:6]
                        # Load into router
                        task = self.router.create_task(task_type, task_id, priority)
                        if task['status'] == 'PROVIDER_ASSIGNED':
                            tasks_loaded.append(task)
        
        return tasks_loaded
    
    def persist_task_to_queue(self, task, status="QUEUED"):
        """Write a task back to BRAIN_QUEUE.md"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        provider = task.get('provider', 'unassigned')
        
        new_entry = f"| {task['task_id']} | {task['type']} | {task['priority']} | {status} | {provider} | {timestamp} |\n"
        
        # Read existing queue
        with open(self.brain_queue_path, 'r') as f:
            content = f.read()
        
        # Add to Active Queue section
        if '## Active Queue' in content:
            # Insert after the table header
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if '| TASK_ID | Type | Priority | Status' in line:
                    # Insert new entry after header separator
                    insert_at = i + 3  # header + separator + first data
                    lines.insert(insert_at, new_entry.rstrip('\n'))
                    break
            content = '\n'.join(lines)
        else:
            # Append to end
            content += f"\n## Active Queue\n\n| TASK_ID | Type | Priority | Status | Assigned | Created |\n|---------|------|----------|--------|----------|----------|\n{new_entry}"
        
        with open(self.brain_queue_path, 'w') as f:
            f.write(content)
        
        return True
    
    def update_brain_state(self, active_task_id):
        """Update BRAIN_STATE.md with current active task"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        state_update = f"""
## Current Task
- Active Task: {active_task_id}
- Status: IN-PROGRESS
- Last Updated: {timestamp}
"""
        
        with open(self.brain_state_path, 'r') as f:
            content = f.read()
        
        # Update the Current Task section
        if '## Current Task' in content:
            # Replace existing section
            parts = content.split('## Current Task')
            before = parts[0]
            after_parts = parts[1].split('##', 1)
            after = '##' + after_parts[1] if len(after_parts) > 1 else ''
            content = before + state_update + after
        else:
            # Add new section
            content += state_update
        
        with open(self.brain_state_path, 'w') as f:
            f.write(content)
        
        return True
    
    def update_handover(self, task_id, status, details=""):
        """Update HANDOVER.md with task progress"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n| {task_id} - {status} | Bridge v1.0 | {timestamp} | {details} |"
        
        with open(self.handover_path, 'a') as f:
            f.write(entry)
        
        return True
    
    def create_and_persist_task(self, task_type, description, priority="normal"):
        """Create task via TaskRouter AND persist to BrainOS"""
        # Create task using existing TaskRouter
        task = self.router.create_task(task_type, description, priority)
        
        if task['status'] == 'PROVIDER_ASSIGNED':
            # Persist to BRAIN_QUEUE
            self.persist_task_to_queue(task)
            
            # Update BRAIN_STATE
            self.update_brain_state(task['task_id'])
            
            # Update HANDOVER
            self.update_handover(task['task_id'], 'CREATED', f"Type: {task_type}, Provider: {task['provider']}")
            
            # Log to BRAIN_MEMORY
            memory_path = "15_BrainOS/BRAIN_MEMORY.md"
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            memory_entry = f"[{ts}] [INFO] [BRIDGE] Task {task['task_id']} created and persisted to BrainOS\n"
            with open(memory_path, 'a') as f:
                f.write(memory_entry)
        
        return task

    # ------------------------------------------------------------------
    # Step 10/10: Full autonomous loop support
    # These helpers let dispatcher_bridge.py pick up REAL rows already
    # sitting in BRAIN_QUEUE.md's "## Active Queue" table (instead of
    # only creating a brand new hardcoded test task each run) and move
    # them through IN-PROGRESS -> DONE/FAILED as they're actually
    # dispatched and executed.
    # ------------------------------------------------------------------

    def get_active_queue_rows(self):
        """Parse the '## Active Queue' table into structured rows.
        Each row keeps its exact `raw_line` text so callers can find
        and replace/move that specific line later (BRAIN_QUEUE.md has
        had duplicate task_ids from earlier manual tests, so matching
        on the literal line is more reliable than matching on task_id
        alone)."""
        if not os.path.exists(self.brain_queue_path):
            return []

        with open(self.brain_queue_path, 'r') as f:
            content = f.read()

        rows = []
        in_section = False
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('## Active Queue'):
                in_section = True
                continue
            if in_section and stripped.startswith('##'):
                break
            if not in_section or not stripped.startswith('|'):
                continue
            if 'TASK_ID' in stripped or stripped.replace('|', '').strip().startswith('-'):
                continue
            parts = [p.strip() for p in stripped.split('|') if p.strip()]
            if len(parts) >= 6:
                task_id, task_type, priority, status, assigned, created = parts[:6]
                rows.append({
                    "raw_line": line,
                    "task_id": task_id,
                    "type": task_type,
                    "priority": priority,
                    "status": status,
                    "assigned": assigned,
                    "created": created,
                    "target_file": self._load_target_file(task_id),
                })
        return rows

    def _load_target_file(self, task_id):
        """TASK_DESCRIPTIONS.json থেকে এই task_id-এর target_file পড়ে (থাকলে)।"""
        import json
        desc_path = os.path.join(REPO_ROOT, "15_BrainOS", "TASK_DESCRIPTIONS.json")
        if not os.path.exists(desc_path):
            return ""
        try:
            with open(desc_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(task_id, {}).get("target_file", "")
        except Exception:
            return ""

    def set_queue_row_status(self, raw_line, new_status):
        """Update just the status field of a row still inside Active Queue
        (e.g. QUEUED -> IN-PROGRESS). Returns the new line text so the
        caller can track this row through subsequent moves."""
        parts = [p.strip() for p in raw_line.strip().split('|') if p.strip()]
        task_id, task_type, priority, _old_status, assigned, created = parts[:6]
        new_line = f"| {task_id} | {task_type} | {priority} | {new_status} | {assigned} | {created} |"

        with open(self.brain_queue_path, 'r') as f:
            content = f.read()
        content = content.replace(raw_line, new_line, 1)
        with open(self.brain_queue_path, 'w') as f:
            f.write(content)
        return new_line

    def move_queue_row(self, raw_line, new_status, section, provider=None):
        """Remove raw_line from Active Queue and append an updated row
        under the given section heading ('Completed' or 'Failed / Blocked')."""
        parts = [p.strip() for p in raw_line.strip().split('|') if p.strip()]
        task_id, task_type, priority, _old_status, assigned, created = parts[:6]
        if provider:
            assigned = provider
        new_line = f"| {task_id} | {task_type} | {priority} | {new_status} | {assigned} | {created} |"

        with open(self.brain_queue_path, 'r') as f:
            content = f.read()
        lines = content.split('\n')

        if raw_line in lines:
            lines.remove(raw_line)

        header = f"## {section}"
        inserted = False
        for i, line in enumerate(lines):
            if line.strip() == header:
                lines.insert(i + 1, new_line)
                inserted = True
                break
        if not inserted:
            lines.append(header)
            lines.append(new_line)

        with open(self.brain_queue_path, 'w') as f:
            f.write('\n'.join(lines))
        return new_line

    def get_lock_token(self):
        """Read '- Lock Token: FREE/BUSY' from BRAIN_STATE.md (defaults to FREE if missing)."""
        with open(self.brain_state_path, 'r') as f:
            content = f.read()
        m = re.search(r"Lock Token:\s*(\S+)", content)
        return m.group(1) if m else "FREE"

    def set_lock_token(self, value):
        """Set the Lock Token field in BRAIN_STATE.md."""
        with open(self.brain_state_path, 'r') as f:
            content = f.read()
        if re.search(r"Lock Token:\s*\S+", content):
            content = re.sub(r"(Lock Token:\s*)\S+", r"\1" + value, content, count=1)
        with open(self.brain_state_path, 'w') as f:
            f.write(content)

    def log_memory(self, message, level="INFO", source="AUTO_LOOP"):
        """Append a timestamped line to BRAIN_MEMORY.md (same format the
        rest of the bridges already use)."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("15_BrainOS/BRAIN_MEMORY.md", 'a') as f:
            f.write(f"[{ts}] [{level}] [{source}] {message}\n")

# Test bridge
if __name__ == "__main__":
    bridge = TaskRouterBridge()
    
    print("=== TASK ROUTER - BRAINOS BRIDGE TEST ===\n")
    
    # Test 1: Create and persist a task
    task = bridge.create_and_persist_task(
        "Documentation", 
        "Write API documentation for BrainOS bridge",
        "CRITICAL"
    )
    print(f"✅ Task created: {task}")
    
    # Test 2: Sync from BRAIN_QUEUE
    tasks = bridge.sync_queue_from_brain()
    print(f"\n📊 Tasks synced from BRAIN_QUEUE: {len(tasks)}")
    for t in tasks:
        print(f"  - {t['task_id']}: {t['type']} → {t['provider']}")
    
    print("\n✅ Step 7 Bridge Test Complete!")
