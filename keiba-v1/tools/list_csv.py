#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
os.chdir(r"Z:\KEIBA-CICD\調教データ")
files = [f for f in os.listdir('.') if f.endswith('.csv')]
for f in files:
    print(f)
