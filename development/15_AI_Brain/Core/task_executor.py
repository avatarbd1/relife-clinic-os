#!/usr/bin/env python3
"""
task_executor.py — BrainOS Phase 2, Item 1: Task Executor
Relife Clinic OS
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REPO_ROOT = str(Path(__file__).resolve().parents[3])
os.chdir(REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "development/15_AI_Brain", "Core"))
sys.path.insert(0, os.path.join(REPO_ROOT, "development/15_AI_Brain", "Control"))

from provider_router import ProviderRouter  # noqa: E402

BLOCKED_PREFIX = "03_Bot"
DEFAULT_OUTPUT_DIR = Path("development/15_AI_Brain/Outputs")


class TaskExecutor:
    def __init__(self):
        self.router_config = ProviderRouter()
        self.timeout = 30
        self.max_retries = 1
        self.retry_delay = 2

    def _check_api_key(self, provider: str) -> bool:
        return bool(self.router_config.PROVIDERS.get(provider, {}).get("api_key"))

    def _call_provider_with_prompt(self, provider: str, prompt: str):
        import requests

        try:
            if provider == "gemini":
                api_key = self.router_config.PROVIDERS["gemini"]["api_key"]
                if not api_key:
                    return False, "Gemini API key not set"
                url = (
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    f"gemini-1.5-flash:generateContent?key={api_key}"
                )
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                resp = requests.post(url, json=payload, timeout=self.timeout)
                if resp.status_code != 200:
                    return False, f"Gemini API error {resp.status_code}: {resp.text[:200]}"
                data = resp.json()
                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
                return True, text.strip()

            elif provider == "groq":
                api_key = self.router_config.PROVIDERS["groq"]["api_key"]
                if not api_key:
                    return False, "Groq API key not set"
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}"}
                payload = {
                    "model": "openai/gpt-oss-20b",
                    "messages": [{"role": "user", "content": prompt}],
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                if resp.status_code != 200:
                    return False, f"Groq API error {resp.status_code}: {resp.text[:200]}"
                data = resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return True, text.strip()

            elif provider == "openrouter":
                api_key = self.router_config.PROVIDERS["openrouter"]["api_key"]
                if not api_key:
                    return False, "OpenRouter API key not set"
                url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}"}
                payload = {
                    "model": "openai/gpt-oss-20b",
                    "messages": [{"role": "user", "content": prompt}],
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                if resp.status_code != 200:
                    return False, f"OpenRouter API error {resp.status_code}: {resp.text[:200]}"
                data = resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return True, text.strip()

            else:
                return False, "Unknown provider"

        except Exception as e:
            logger.error(f"Provider {provider} error: {e}")
            return False, str(e)

    def _provider_order(self, task_type: str):
        return self.router_config.ROUTING_RULES.get(
            task_type, ("gemini", "openrouter", "gemini")
        )

    def execute(
        self,
        task_id: str,
        task_type: str,
        prompt: str,
        output_path: Optional[str] = None,
        persist_output: bool = True,
    ) -> Dict:
        if output_path and output_path.replace("\\", "/").startswith(BLOCKED_PREFIX):
            return {
                "status": "BLOCKED",
                "task_id": task_id,
                "error": f"output_path {BLOCKED_PREFIX}/ এর ভেতরে লেখা নিষেধ — explicit owner approval দরকার",
            }

        primary, secondary, fallback = self._provider_order(task_type)
        provider_list = [primary, secondary, fallback]

        result = {
            "status": "FAILED",
            "task_id": task_id,
            "task_type": task_type,
            "provider": None,
            "output": None,
            "error": None,
            "attempts": 0,
        }

        for idx, provider in enumerate(provider_list):
            if not self._check_api_key(provider):
                logger.warning(f"Provider {provider} missing API key, skipping")
                continue

            for attempt in range(self.max_retries + 1):
                logger.info(f"[TaskExecutor] Attempt {attempt+1} with {provider} for {task_id}")
                success, output = self._call_provider_with_prompt(provider, prompt)
                result["attempts"] += 1

                if success:
                    result["status"] = "SUCCESS"
                    result["provider"] = provider
                    result["output"] = output
                    result["fallback_used"] = idx > 0
                    break
                else:
                    result["error"] = output
                    time.sleep(self.retry_delay)

            if result["status"] == "SUCCESS":
                break

        # Dispatcher passes persist_output=False so unvalidated provider output
        # stays in memory. ConfirmGate becomes the only writer to final Outputs/.
        if result["status"] == "SUCCESS" and persist_output:
            final_path = Path(output_path) if output_path else DEFAULT_OUTPUT_DIR / f"{task_id}.md"
            final_path.parent.mkdir(parents=True, exist_ok=True)
            final_path.write_text(result["output"], encoding="utf-8")
            result["saved_to"] = str(final_path)
            logger.info(f"[TaskExecutor] Output saved to {final_path}")

        self._log_execution(result)
        return result

    def _log_execution(self, result: Dict):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            **{k: v for k, v in result.items() if k != "output"},
        }
        log_file = "development/15_AI_Brain/Logs/task_executor.log"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    executor = TaskExecutor()
    print("Testing Task Executor with a real prompt...")
    test_result = executor.execute(
        task_id="EXEC-TEST-001",
        task_type="Documentation",
        prompt="এক লাইনে বলো: BrainOS Phase 2 Task Executor কী কাজ করে?",
    )
    print(json.dumps({k: v for k, v in test_result.items() if k != "output"}, indent=2, ensure_ascii=False))
    if test_result.get("status") == "SUCCESS":
        print(f"\nOutput preview: {test_result['output'][:200]}")
