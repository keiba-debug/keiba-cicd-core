#!/usr/bin/env python3
"""
競馬ブックスクレイピングシステム エントリーポイント

このファイルは、src/keibabook/main.pyへの簡潔なエントリーポイントです。
"""

import sys
import subprocess
from pathlib import Path

def main():
    """
    メイン処理をsrc/keibabook/main.pyに委譲する
    """
    # プロジェクトルート
    project_root = Path(__file__).parent
    main_script = project_root / "src" / "keibabook" / "main.py"
    
    # 引数をそのまま渡してスクリプトを実行
    try:
        result = subprocess.run([sys.executable, str(main_script)] + sys.argv[1:], 
                               cwd=str(project_root))
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n[INFO] ユーザーによって中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 実行中にエラーが発生しました: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 