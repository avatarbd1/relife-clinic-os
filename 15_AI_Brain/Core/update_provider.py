# এই কোড provider_router.py-এর _call_provider মেথড আপডেট করবে
import re

with open('provider_router.py', 'r') as f:
    content = f.read()

# পুরানো _call_provider মেথড রিপ্লেস করুন
new_method = '''
    def _call_provider(self, provider: str, task_id: str) -> Tuple[bool, any]:
        """Real API calls to providers"""
        try:
            if provider == "gemini":
                import google.generativeai as genai
                genai.configure(api_key=self.PROVIDERS["gemini"]["api_key"])
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content(f"Execute task {task_id}")
                return True, {"result": response.text}
                
            elif provider == "groq":
                from groq import Groq
                client = Groq(api_key=self.PROVIDERS["groq"]["api_key"])
                response = client.chat.completions.create(
                    model="mixtral-8x7b-32768",
                    messages=[{"role": "user", "content": f"Execute task {task_id}"}]
                )
                return True, {"result": response.choices[0].message.content}
                
            elif provider == "openrouter":
                import openai
                client = openai.OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.PROVIDERS["openrouter"]["api_key"]
                )
                response = client.chat.completions.create(
                    model="anthropic/claude-3.5-sonnet",
                    messages=[{"role": "user", "content": f"Execute task {task_id}"}]
                )
                return True, {"result": response.choices[0].message.content}
                
            else:
                return False, "Unknown provider"
                
        except Exception as e:
            logger.error(f"Provider {provider} error: {e}")
            return False, str(e)
'''

# রিপ্লেস করুন (সাবধান! ব্যাকআপ আছে)
# ম্যানুয়ালি এডিট করা ভালো
print("Please manually update _call_provider method in provider_router.py")
print("Or use a code editor to replace the method")
