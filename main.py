#!/usr/bin/env python3
"""
競馬ブックスクレイピングシステム エントリーポイント

このファイルは、KeibaCICD.keibabook/src/keibabook/main.pyへの簡潔なエントリーポイントです。
"""

import sys
import subprocess
from pathlib import Path
import os

def main():
    """
    メイン処理をKeibaCICD.keibabook/src/keibabook/main.pyに委譲する
    """
    # プロジェクトルート
    project_root = Path(__file__).parent
    keibabook_src = project_root / "KeibaCICD.keibabook" / "src"
    main_script = keibabook_src / "main.py"
    
    # PYTHONPATHを設定
    env = os.environ.copy()
    env['PYTHONPATH'] = str(keibabook_src)
    
    # スクリプトとして実行
    try:
        result = subprocess.run([sys.executable, str(main_script)] + sys.argv[1:], 
                               cwd=str(project_root), env=env)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n[INFO] ユーザーによって中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 実行中にエラーが発生しました: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 