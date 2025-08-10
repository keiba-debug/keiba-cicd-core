#!/usr/bin/env python3
"""
marker-pdfライブラリの構造を確認するテストスクリプト
"""

try:
    import marker
    print("marker をインポート成功")
    print("marker.__file__:", marker.__file__)
    
    # 利用可能なモジュールを確認
    import pkgutil
    print("\n利用可能なモジュール:")
    for importer, modname, ispkg in pkgutil.iter_modules(marker.__path__, marker.__name__ + '.'):
        print(f"  {modname}")
        
except ImportError as e:
    print(f"marker インポートエラー: {e}")

# 実際の使用方法を確認
try:
    from marker import convert_single_pdf
    print("convert_single_pdf をインポート成功")
except ImportError as e:
    print(f"convert_single_pdf インポートエラー: {e}")

try:
    from marker.convert import convert_single_pdf
    print("marker.convert.convert_single_pdf をインポート成功")
except ImportError as e:
    print(f"marker.convert.convert_single_pdf インポートエラー: {e}")

try:
    from marker.conversion import convert_single_pdf
    print("marker.conversion.convert_single_pdf をインポート成功")
except ImportError as e:
    print(f"marker.conversion.convert_single_pdf インポートエラー: {e}")

print("\nmarker-pdfの構造確認完了") 