# -*- coding: utf-8 -*-
"""一括PCI分析スクリプト"""

import glob
import os
from analyze_class_pci import analyze_class_pci

def main():
    # Y:/TXT のCSVファイル一覧取得
    files = sorted(glob.glob('Y:/TXT/*.csv'))
    
    # PCIファイルのみ抽出
    pci_files = [f for f in files if 'PCI' in os.path.basename(f)]
    
    for f in pci_files:
        print("=" * 70)
        analyze_class_pci(f)
        print()

if __name__ == "__main__":
    main()
