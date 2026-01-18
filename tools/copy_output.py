# -*- coding: utf-8 -*-
import shutil

src = 'keiba-cicd-core/tools/output_test.txt'
dst = 'Z:/KEIBA-CICD/調教データ/output_251228.txt'

shutil.copy(src, dst)
print(f'コピー完了: {dst}')
