import re

with open("bot.py", "r", encoding="utf-8") as f:
    content = f.read()

helper_name = "_restart_via_start"
if helper_name not in content:
    helper_code = (
        "\n"
        "async def _restart_via_start(update, context):\n"
        "    # /start chaple je conversation theke ber kore mul menute firiye ane\n"
        "    context.user_data.clear()\n"
        "    await start(update, context)\n"
        "    return ConversationHandler.END\n"
        "\n"
    )
    m = re.search(r"\ndef main\(\):", content)
    if m:
        pos = m.start()
        content = content[:pos] + helper_code + content[pos:]
    else:
        content += helper_code
    print("helper added")
else:
    print("helper already exists, skipped")

conv_names = ["reg_conv", "apt_conv", "pay_conv", "treat_conv", "hist_conv"]
for name in conv_names:
    pattern = re.compile(
        r"(" + name + r"\s*=\s*ConversationHandler\(.*?fallbacks\s*=\s*\[)(.*?)(\]\s*,?\s*\n\s*\))",
        re.DOTALL,
    )
    def repl(m, name=name):
        head, body, tail = m.group(1), m.group(2), m.group(3)
        if '"start"' in body or "'start'" in body:
            print(name + ": start fallback already exists, skipped")
            return m.group(0)
        new_body = body.rstrip()
        if new_body and not new_body.endswith(","):
            new_body += ","
        new_body += "\n            CommandHandler(\"start\", _restart_via_start),"
        print(name + ": start fallback added")
        return head + new_body + tail
    content = pattern.sub(repl, content, count=1)

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(content)

print("DONE")
