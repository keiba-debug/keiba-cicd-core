#!/usr/bin/env python3
"""
設定管理ツール

データ保存ディレクトリの設定変更と確認を行います。
"""

import argparse
import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# .envファイルの読み込み
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[INFO] .envファイルを読み込みました: {env_path}")
    else:
        print(f"[WARNING] .envファイルが見つかりません: {env_path}")
except ImportError:
    print("[WARNING] python-dotenvがインストールされていません。環境変数を手動で設定してください。")

from src.keibabook.utils.config import Config
from src.keibabook.utils.logger import setup_logger


class ConfigManager:
    """設定管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.logger = setup_logger("config_manager", level="INFO")
    
    def show_current_config(self) -> None:
        """現在の設定を表示する"""
        self.logger.info("=== 現在の設定 ===")
        
        config_summary = Config.get_current_config_summary()
        
        for key, value in config_summary.items():
            self.logger.info(f"{key}: {value}")
        
        # ディレクトリの存在確認
        self.logger.info("\n=== ディレクトリ存在確認 ===")
        directories = {
            "data_dir": Config.get_data_dir(),
            "keibabook_dir": Config.get_keibabook_dir(),
            "seiseki_dir": Config.get_seiseki_dir(),
            "shutsuba_dir": Config.get_shutsuba_dir(),
            "debug_dir": Config.get_debug_dir(),
            "log_dir": Config.get_log_dir()
        }
        
        for name, path in directories.items():
            exists = "✅" if path.exists() else "❌"
            self.logger.info(f"{name}: {exists} {path}")
    
    def show_environment_variables(self) -> None:
        """設定可能な環境変数を表示する"""
        self.logger.info("=== 設定可能な環境変数 ===")
        
        env_vars = [
            ("KEIBA_DATA_ROOT_DIR", "データルートディレクトリ", "data/"),
            ("KEIBA_DATA_DIR", "メインデータディレクトリ", "data/"),
            ("KEIBA_KEIBABOOK_DIR", "競馬ブックデータディレクトリ", "data/keibabook/"),
            ("KEIBA_SEISEKI_DIR", "成績データディレクトリ", "data/keibabook/seiseki/"),
            ("KEIBA_SHUTSUBA_DIR", "出馬表データディレクトリ", "data/keibabook/shutsuba/"),
            ("KEIBA_DEBUG_DIR", "デバッグデータディレクトリ", "data/debug/"),
            ("KEIBA_LOG_DIR", "ログディレクトリ", "logs/"),
            ("LOG_LEVEL", "ログレベル", "INFO"),
            ("DEBUG", "デバッグモード", "false"),
            ("HEADLESS", "ヘッドレスモード", "true"),
        ]
        
        for var_name, description, default in env_vars:
            current_value = os.getenv(var_name, "未設定")
            self.logger.info(f"{var_name}")
            self.logger.info(f"  説明: {description}")
            self.logger.info(f"  デフォルト: {default}")
            self.logger.info(f"  現在値: {current_value}")
            self.logger.info("")
    
    def create_directories(self) -> None:
        """必要なディレクトリを作成する"""
        self.logger.info("=== ディレクトリ作成 ===")
        
        try:
            Config.ensure_directories()
            self.logger.info("✅ 必要なディレクトリを作成しました")
            
            # 作成されたディレクトリを確認
            directories = {
                "data_dir": Config.get_data_dir(),
                "keibabook_dir": Config.get_keibabook_dir(),
                "seiseki_dir": Config.get_seiseki_dir(),
                "shutsuba_dir": Config.get_shutsuba_dir(),
                "debug_dir": Config.get_debug_dir(),
                "log_dir": Config.get_log_dir()
            }
            
            for name, path in directories.items():
                self.logger.info(f"  {name}: {path}")
                
        except Exception as e:
            self.logger.error(f"❌ ディレクトリ作成に失敗しました: {e}")
    
    def test_config_with_custom_path(self, custom_data_dir: str) -> None:
        """カスタムパスでの設定をテストする"""
        self.logger.info(f"=== カスタムパステスト: {custom_data_dir} ===")
        
        # 環境変数を一時的に設定
        original_value = os.getenv("KEIBA_DATA_DIR")
        os.environ["KEIBA_DATA_DIR"] = custom_data_dir
        
        try:
            # 設定を表示
            self.logger.info("カスタム設定での各ディレクトリ:")
            self.logger.info(f"  data_dir: {Config.get_data_dir()}")
            self.logger.info(f"  keibabook_dir: {Config.get_keibabook_dir()}")
            self.logger.info(f"  seiseki_dir: {Config.get_seiseki_dir()}")
            self.logger.info(f"  shutsuba_dir: {Config.get_shutsuba_dir()}")
            self.logger.info(f"  debug_dir: {Config.get_debug_dir()}")
            
            # ディレクトリ作成テスト
            self.logger.info("\nディレクトリ作成テスト:")
            Config.ensure_directories()
            
            if Config.get_data_dir().exists():
                self.logger.info("✅ カスタムディレクトリが正常に作成されました")
            else:
                self.logger.error("❌ カスタムディレクトリの作成に失敗しました")
                
        finally:
            # 環境変数を元に戻す
            if original_value is not None:
                os.environ["KEIBA_DATA_DIR"] = original_value
            else:
                os.environ.pop("KEIBA_DATA_DIR", None)
    
    def generate_env_file_template(self, output_path: str = ".env.template") -> None:
        """環境変数テンプレートファイルを生成する"""
        self.logger.info(f"=== 環境変数テンプレート生成: {output_path} ===")
        
        template_content = """# 競馬ブックスクレイピングシステム 環境変数設定
# このファイルを .env にコピーして使用してください

# ===== データディレクトリ設定 =====
# データルートディレクトリ（絶対パスまたは相対パス）
# KEIBA_DATA_ROOT_DIR=/path/to/your/data

# メインデータディレクトリ
# KEIBA_DATA_DIR=/path/to/your/data

# 競馬ブックデータディレクトリ
# KEIBA_KEIBABOOK_DIR=/path/to/your/data/keibabook

# 成績データディレクトリ
# KEIBA_SEISEKI_DIR=/path/to/your/data/keibabook/seiseki

# 出馬表データディレクトリ
# KEIBA_SHUTSUBA_DIR=/path/to/your/data/keibabook/shutsuba

# デバッグデータディレクトリ
# KEIBA_DEBUG_DIR=/path/to/your/data/debug

# ログディレクトリ
# KEIBA_LOG_DIR=/path/to/your/logs

# ===== システム設定 =====
# ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
# LOG_LEVEL=INFO

# デバッグモード（true/false）
# DEBUG=false

# ヘッドレスモード（true/false）
# HEADLESS=true

# ===== 競馬ブック認証設定 =====
# 競馬ブックのCookie値（ログイン後にF12で取得）
# KEIBABOOK_SESSION=your_session_value
# KEIBABOOK_TK=your_tk_value
# KEIBABOOK_XSRF_TOKEN=your_xsrf_token_value

# ===== 使用例 =====
# 外部ストレージにデータを保存する場合:
# KEIBA_DATA_ROOT_DIR=/mnt/external_storage/keiba_data

# プロジェクト内の別フォルダにデータを保存する場合:
# KEIBA_DATA_DIR=./custom_data

# 成績データのみ別の場所に保存する場合:
# KEIBA_SEISEKI_DIR=/path/to/seiseki_storage
"""
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
            self.logger.info(f"✅ テンプレートファイルを生成しました: {output_path}")
            self.logger.info("このファイルを .env にコピーして設定を変更してください")
        except Exception as e:
            self.logger.error(f"❌ テンプレートファイル生成に失敗しました: {e}")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="競馬ブックスクレイピングシステム 設定管理ツール")
    parser.add_argument("--show", action="store_true", help="現在の設定を表示")
    parser.add_argument("--env-vars", action="store_true", help="設定可能な環境変数を表示")
    parser.add_argument("--create-dirs", action="store_true", help="必要なディレクトリを作成")
    parser.add_argument("--test-custom", type=str, help="カスタムデータディレクトリでテスト")
    parser.add_argument("--generate-template", type=str, nargs="?", const=".env.template", 
                       help="環境変数テンプレートファイルを生成")
    
    args = parser.parse_args()
    
    if not any(vars(args).values()):
        parser.print_help()
        return
    
    manager = ConfigManager()
    
    if args.show:
        manager.show_current_config()
    
    if args.env_vars:
        manager.show_environment_variables()
    
    if args.create_dirs:
        manager.create_directories()
    
    if args.test_custom:
        manager.test_config_with_custom_path(args.test_custom)
    
    if args.generate_template:
        manager.generate_env_file_template(args.generate_template)


if __name__ == "__main__":
    main() 