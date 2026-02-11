# -*- coding: utf-8 -*-
import subprocess

print("=== クリップボードの内容（先頭10行）===")
clip_result = subprocess.run(['powershell', '-command', 'Get-Clipboard'], 
                             capture_output=True, text=True, encoding='cp932')
lines = clip_result.stdout.strip().split('\n')
for i, line in enumerate(lines[:10]):
    print(f"  {line}")
print(f"\n  ... 合計 {len(lines)} 行")
