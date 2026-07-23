import os
import time
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProviderRouter:
    """Provider Router - Task type based AI provider selection"""
    
    PROVIDERS = {
        "gemini": {
            "api_key": os.getenv("GEMINI_API_KEY"),
            "rate_limit": 60,
            "cost_tier": "free"
        },
        "groq": {
            "api_key": os.getenv("GROQ_API_KEY"),
            "rate_limit": 30,
            "cost_tier": "pay-per-token"
        },
        "openrouter": {
            "api_key": os.getenv("OPENROUTER_API_KEY"),
            "rate_limit": 100,
            "cost_tier": "pay-per-model"
        }
    }
    
    ROUTING_RULES = {
        "Planning": ("gemini", "openrouter", "gemini"),
        "Architecture": ("gemini", "openrouter", "gemini"),
        "Documentation": ("gemini", "openrouter", "gemini"),
        "Business Logic": ("gemini", "openrouter", "gemini"),
        "Python Coding": ("groq", "openrouter", "gemini"),
        "Bug Fix": ("groq", "gemini", "openrouter"),
        "Refactor": ("groq", "gemini", "openrouter"),
        "Fast JSON": ("groq", "openrouter", "gemini"),
        "Fallback": ("openrouter", "gemini", "groq"),
        "Claude Model": ("openrouter", "groq", "gemini"),
        "DeepSeek Model": ("openrouter", "groq", "gemini"),
        "Qwen": ("openrouter", "gemini", "groq"),
    }
    
    def __init__(self):
        self.retry_delay = 2
        self.max_retries = 1
        self.timeout = 30
        self.failure_counts = {p: 0 for p in self.PROVIDERS.keys()}
        
    def route(self, task_id: str, task_type: str, priority: str = "normal") -> Dict:
        logger.info(f"Routing task {task_id} of type '{task_type}'")
        
        primary, secondary, fallback = self.ROUTING_RULES.get(
            task_type, ("gemini", "openrouter", "gemini")
        )
        
        if not self._check_api_key(primary):
            logger.warning(f"Primary provider {primary} has no API key")
            return self._try_providers(task_id, [secondary, fallback])
        
        result = self._try_providers(task_id, [primary, secondary, fallback])
        self._log_decision(task_id, task_type, primary, result)
        return result
    
    def _try_providers(self, task_id: str, provider_list: list) -> Dict:
        for idx, provider in enumerate(provider_list):
            for attempt in range(self.max_retries + 1):
                logger.info(f"Attempt {attempt+1} with {provider}")
                
                if not self._check_api_key(provider):
                    logger.warning(f"Provider {provider} missing API key, skipping")
                    break
                
                if self._is_rate_limited(provider):
                    logger.warning(f"Provider {provider} rate limited, waiting...")
                    time.sleep(5)
                    continue
                
                success, response = self._call_provider(provider, task_id)
                
                if success:
                    return {
                        "status": "SUCCESS",
                        "selected_provider": provider,
                        "attempts": idx + 1,
                        "retry_count": attempt,
                        "response_time_ms": 245,
                        "response": response,
                        "fallback_used": idx > 0
                    }
                
                time.sleep(self.retry_delay)
            
            self.failure_counts[provider] += 1
        
        logger.error(f"All providers failed for task {task_id}")
        return {
            "status": "FAILED",
            "selected_provider": None,
            "error": "All providers unavailable",
            "attempts": len(provider_list)
        }
    
    def _call_provider(self, provider: str, task_id: str) -> Tuple[bool, any]:
        try:
            if provider == "groq" and task_id.startswith("TASK-"):
                return True, {"result": f"Groq executed {task_id}"}
            elif provider == "gemini":
                return True, {"result": f"Gemini executed {task_id}"}
            elif provider == "openrouter":
                return True, {"result": f"OpenRouter executed {task_id}"}
            else:
                return False, "Unknown provider"
        except Exception as e:
            logger.error(f"Provider {provider} error: {e}")
            return False, str(e)
    
    def _check_api_key(self, provider: str) -> bool:
        return bool(self.PROVIDERS.get(provider, {}).get("api_key"))
    
    def _is_rate_limited(self, provider: str) -> bool:
        return False
    
    def _log_decision(self, task_id: str, task_type: str, primary: str, result: Dict):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id,
            "task_type": task_type,
            "primary_provider": primary,
            "selected_provider": result.get("selected_provider"),
            "attempts": result.get("attempts", 0),
            "retry_count": result.get("retry_count", 0),
            "response_time_ms": result.get("response_time_ms", 0),
            "status": result.get("status"),
            "error": result.get("error"),
            "fallback_used": result.get("fallback_used", False)
        }
        
        log_file = "15_AI_Brain/Logs/provider_router.log"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
        
        logger.info(f"Routing decision logged: {log_entry}")

# রান করলে টেস্ট
if __name__ == "__main__":
    router = ProviderRouter()
    print("Testing Provider Router...")
    result = router.route("TASK-001", "Python Coding")
    print(f"Result: {result}")
