from pathlib import Path

p = Path('server/koko_task_helpers.py')
text = p.read_text(encoding='utf-8')

replacements = [
    ('content = "【{}】\n{}".format', 'content = "【{}】\\n{}".format'),
    ('blocks.append("任务 #{}\n{}".format(', 'blocks.append("任务 #{}\\n{}".format('),
    ('"\n".join("{}: {}".format', '"\\n".join("{}: {}".format'),
    ('body = "本次扫描到 {} 条新充值任务：\n\n{}".format(len(rows), "\n\n".join(blocks))',
     'body = "本次扫描到 {} 条新充值任务：\\n\\n{}".format(len(rows), "\\n\\n".join(blocks))'),
]

for old, new in replacements:
    if old not in text:
        raise RuntimeError('expected generated string literal not found: ' + repr(old))
    text = text.replace(old, new, 1)

p.write_text(text, encoding='utf-8')
print('WECOM_PYTHON_STRINGS_FIXED')
