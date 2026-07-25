#!/usr/bin/env python3
"""
output_validator.py — BrainOS Phase 2, Item 3: Output Validator
Relife Clinic OS
"""

import json
import subprocess
import tempfile
import py_compile
from pathlib import Path
from typing import Dict, List


class OutputValidator:
    def validate(self, content: str, target_path: str) -> Dict:
        ext = Path(target_path).suffix.lower()
        checks: List[Dict] = []
        errors: List[str] = []

        non_empty = bool(content and content.strip())
        checks.append({"name": "non_empty", "passed": non_empty})
        if not non_empty:
            errors.append("content খালি")

        if non_empty:
            if ext == ".py":
                ok, err = self._check_python(content)
                checks.append({"name": "python_syntax", "passed": ok, "detail": err})
                if not ok:
                    errors.append(f"Python syntax error: {err}")

            elif ext == ".json":
                ok, err = self._check_json(content)
                checks.append({"name": "json_parse", "passed": ok, "detail": err})
                if not ok:
                    errors.append(f"JSON parse error: {err}")

            elif ext == ".sh":
                ok, err = self._check_shell(content)
                checks.append({"name": "shell_syntax", "passed": ok, "detail": err})
                if not ok:
                    errors.append(f"Shell syntax error: {err}")

            elif ext == ".md":
                ok, err = self._check_markdown(content)
                checks.append({"name": "markdown_structure", "passed": ok, "detail": err})
                if not ok:
                    errors.append(f"Markdown structure issue: {err}")

        valid = all(c["passed"] for c in checks)

        return {
            "valid": valid,
            "target_path": target_path,
            "file_type": ext or "unknown",
            "checks": checks,
            "errors": errors,
        }

    def validate_file(self, path: str) -> Dict:
        p = Path(path)
        if not p.exists():
            return {"valid": False, "target_path": path, "errors": ["ফাইল পাওয়া যায়নি"]}
        content = p.read_text(encoding="utf-8")
        return self.validate(content, path)

    def _check_python(self, content: str):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            py_compile.compile(tmp_path, doraise=True)
            return True, None
        except py_compile.PyCompileError as e:
            return False, str(e.msg if hasattr(e, "msg") else e)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
            cache_dir = Path(tmp_path).parent / "__pycache__"
            if cache_dir.exists():
                for f in cache_dir.glob(Path(tmp_path).stem + "*"):
                    f.unlink(missing_ok=True)

    def _check_json(self, content: str):
        try:
            json.loads(content)
            return True, None
        except json.JSONDecodeError as e:
            return False, str(e)

    def _check_shell(self, content: str):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False, encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            result = subprocess.run(
                ["bash", "-n", tmp_path], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return True, None
            return False, result.stderr.strip()
        except FileNotFoundError:
            return True, "bash পাওয়া যায়নি, syntax check skip হয়েছে"
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _check_markdown(self, content: str):
        fence_count = content.count("```")
        if fence_count % 2 != 0:
            return False, "```code fence জোড়া মেলেনি (অসম সংখ্যক ```)"
        return True, None


if __name__ == "__main__":
    print("=== Output Validator Self-Test ===\n")
    v = OutputValidator()

    tests = [
        ("valid python", "print('hello')\n", "test.py", True),
        ("invalid python", "def f(:\n    pass\n", "test.py", False),
        ("valid json", '{"a": 1, "b": [1,2,3]}', "test.json", True),
        ("invalid json", '{"a": 1, "b": [1,2,3]', "test.json", False),
        ("valid markdown", "# Title\n\n```python\nprint(1)\n```\n", "test.md", True),
        ("invalid markdown", "# Title\n\n```python\nprint(1)\n", "test.md", False),
        ("empty content", "", "test.py", False),
    ]

    all_passed = True
    for name, content, path, expected_valid in tests:
        result = v.validate(content, path)
        ok = result["valid"] == expected_valid
        mark = "✅" if ok else "❌"
        print(f"{mark} {name}: valid={result['valid']} (expected {expected_valid})")
        if not ok:
            all_passed = False
            print(f"    detail: {result}")

    print(f"\n{'✅ ALL VALIDATOR SELF-TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
