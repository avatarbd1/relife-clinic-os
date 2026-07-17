import re

with open('sheets.py', encoding='utf-8') as f:
    content = f.read()

fixes = {
    'add_patient': 'A1:AC1',
    'add_appointment': 'A1:I1',
    'attendance_check_in': 'A1:N1',
    'add_package': 'A1:K1',
    'add_payment': 'A1:L1',
    'add_treatment_note': 'A1:M1',
    'add_treatment_plan': 'A1:L1',
}

matches = list(re.finditer(r'\ndef (\w+)\(', content))
spans = []
for i, m in enumerate(matches):
    start = m.start()
    end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
    spans.append((m.group(1), start, end))

new_content = content
for name, table_range in fixes.items():
    for fname, start, end in spans:
        if fname == name:
            block = content[start:end]
            def repl(m):
                inner = m.group(0)
                if 'table_range' in inner:
                    return inner
                return inner[:-1] + f', table_range="{table_range}")'
            new_block = re.sub(r'ws\.append_row\([^\n]*?\)', repl, block)
            new_content = new_content.replace(block, new_block)
            break

with open('sheets.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("patched")
