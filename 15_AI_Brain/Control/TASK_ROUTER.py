import sys
import json
from datetime import datetime
sys.path.append('/home/relife-clinic-os')

from Core.provider_router import ProviderRouter

class TaskRouter:
    """Task Router - Assigns tasks and routes to providers"""
    
    def __init__(self):
        self.provider_router = ProviderRouter()
        self.task_queue = []
        
    def create_task(self, task_type: str, description: str, priority: str = "normal"):
        """Create a new task and assign provider"""
        task_id = f"TASK-{len(self.task_queue)+1:03d}"
        
        # Get provider
        result = self.provider_router.route(task_id, task_type, priority)
        
        if result["status"] == "SUCCESS":
            task = {
                "task_id": task_id,
                "type": task_type,
                "description": description,
                "provider": result["selected_provider"],
                "status": "PROVIDER_ASSIGNED",
                "priority": priority,
                "created_at": datetime.now().isoformat(),
                "attempts": result["attempts"],
                "fallback_used": result.get("fallback_used", False)
            }
            self.task_queue.append(task)
            return task
        else:
            return {
                "task_id": task_id,
                "status": "FAILED",
                "error": result.get("error", "Provider routing failed")
            }
    
    def get_tasks(self):
        """Get all tasks"""
        return self.task_queue
    
    def get_task(self, task_id):
        """Get specific task"""
        for task in self.task_queue:
            if task["task_id"] == task_id:
                return task
        return None

# Test
if __name__ == "__main__":
    router = TaskRouter()
    
    print("=== TASK ROUTER TEST ===\n")
    
    # Create tasks
    tasks = [
        ("Python Coding", "Write a function to calculate BMI"),
        ("Planning", "Plan clinic schedule for next week"),
        ("Documentation", "Write API documentation"),
    ]
    
    for task_type, desc in tasks:
        task = router.create_task(task_type, desc)
        print(f"✅ {task['task_id']}: {task_type} → {task['provider']}")
    
    print(f"\n📊 Total tasks: {len(router.get_tasks())}")
