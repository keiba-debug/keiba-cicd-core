#!/usr/bin/env python3
"""
システム監視ツール

スクレイピングシステムの動作状況、パフォーマンス、データ品質を監視します。
"""

import json
from pathlib import Path
import argparse
from datetime import datetime, timedelta
import sys

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Keibabookパッケージのパスを追加
keibabook_src = project_root / "KeibaCICD.keibabook" / "src"
sys.path.insert(0, str(keibabook_src))

from utils.logger import setup_logger


class SystemMonitor:
    """システム監視クラス"""
    
    def __init__(self):
        """初期化"""
        self.logger = setup_logger("system_monitor", level="INFO")
        self.project_root = Path(__file__).parent.parent
        
    def get_system_health(self) -> dict:
        """システムヘルスチェック"""
        health = {
            'timestamp': datetime.now().isoformat(),
            'directories': self._check_directories(),
            'recent_logs': self._check_recent_logs(),
            'data_files': self._check_data_files(),
            'environment': self._check_environment()
        }
        return health
    
    def _check_directories(self) -> dict:
        """重要ディレクトリの存在チェック"""
        required_dirs = [
            'data/keibabook/seiseki',
            'data/debug',
            'data/analysis',
            'logs',
            'src',
            'scripts',
            'tools'
        ]
        
        dir_status = {}
        for dir_path in required_dirs:
            full_path = self.project_root / dir_path
            dir_status[dir_path] = {
                'exists': full_path.exists(),
                'is_dir': full_path.is_dir() if full_path.exists() else False,
                'file_count': len(list(full_path.glob('*'))) if full_path.exists() and full_path.is_dir() else 0
            }
        
        return dir_status
    
    def _check_recent_logs(self) -> dict:
        """最近のログファイルチェック"""
        logs_dir = self.project_root / 'logs'
        if not logs_dir.exists():
            return {'status': 'logs_directory_missing'}
        
        log_files = list(logs_dir.glob('*.log'))
        if not log_files:
            return {'status': 'no_log_files'}
        
        # 最新のログファイル分析
        latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
        
        recent_logs = {
            'total_log_files': len(log_files),
            'latest_log': {
                'name': latest_log.name,
                'size_kb': round(latest_log.stat().st_size / 1024, 2),
                'modified': datetime.fromtimestamp(latest_log.stat().st_mtime).isoformat()
            },
            'log_analysis': self._analyze_log_file(latest_log)
        }
        
        return recent_logs
    
    def _analyze_log_file(self, log_file: Path) -> dict:
        """ログファイルの内容分析"""
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            error_count = sum(1 for line in lines if 'ERROR' in line or '❌' in line)
            warning_count = sum(1 for line in lines if 'WARNING' in line or '⚠️' in line)
            success_count = sum(1 for line in lines if '✅' in line or 'SUCCESS' in line)
            
            return {
                'total_lines': len(lines),
                'error_count': error_count,
                'warning_count': warning_count,
                'success_count': success_count,
                'has_recent_activity': len(lines) > 0
            }
        except Exception as e:
            return {'analysis_error': str(e)}
    
    def _check_data_files(self) -> dict:
        """データファイルの状況チェック"""
        data_dir = self.project_root / 'data/keibabook/seiseki'
        if not data_dir.exists():
            return {'status': 'data_directory_missing'}
        
        json_files = list(data_dir.glob('seiseki_*.json'))
        
        if not json_files:
            return {'status': 'no_data_files'}
        
        # 最新ファイルの分析
        latest_files = sorted(json_files, key=lambda f: f.stat().st_mtime, reverse=True)[:5]
        
        data_info = {
            'total_files': len(json_files),
            'total_size_mb': round(sum(f.stat().st_size for f in json_files) / (1024*1024), 2),
            'latest_files': []
        }
        
        for file in latest_files:
            file_info = {
                'name': file.name,
                'size_kb': round(file.stat().st_size / 1024, 2),
                'modified': datetime.fromtimestamp(file.stat().st_mtime).isoformat()
            }
            
            # ファイル内容の簡易分析
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    file_info['race_info'] = data.get('race_info', {})
                    file_info['horse_count'] = len(data.get('results', []))
                    file_info['interview_count'] = sum(1 for r in data.get('results', []) 
                                                     if r.get('interview') and r.get('interview').strip())
                    file_info['memo_count'] = sum(1 for r in data.get('results', []) 
                                               if r.get('memo') and r.get('memo').strip())
            except Exception as e:
                file_info['content_error'] = str(e)
            
            data_info['latest_files'].append(file_info)
        
        return data_info
    
    def _check_environment(self) -> dict:
        """環境設定のチェック"""
        env_file = self.project_root / '.env'
        
        env_status = {
            'env_file_exists': env_file.exists(),
            'python_version': sys.version,
            'dependencies': self._check_dependencies()
        }
        
        if env_file.exists():
            try:
                with open(env_file, 'r') as f:
                    env_content = f.read()
                    env_status['has_session_cookie'] = 'KEIBABOOK_SESSION=' in env_content and 'dummy' not in env_content.lower()
                    env_status['has_tk_cookie'] = 'KEIBABOOK_TK=' in env_content and 'dummy' not in env_content.lower()
                    env_status['has_xsrf_token'] = 'KEIBABOOK_XSRF_TOKEN=' in env_content and 'dummy' not in env_content.lower()
            except Exception as e:
                env_status['env_read_error'] = str(e)
        
        return env_status
    
    def _check_dependencies(self) -> dict:
        """依存関係のチェック"""
        required_packages = [
            'selenium', 'beautifulsoup4', 'pandas', 'requests', 'lxml'
        ]
        
        dependencies = {}
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
                dependencies[package] = 'installed'
            except ImportError:
                dependencies[package] = 'missing'
        
        return dependencies
    
    def get_data_quality_report(self) -> dict:
        """データ品質レポートの取得"""
        data_dir = self.project_root / 'data/keibabook/seiseki'
        if not data_dir.exists():
            return {'status': 'no_data_directory'}
        
        json_files = list(data_dir.glob('seiseki_*.json'))
        if not json_files:
            return {'status': 'no_data_files'}
        
        total_horses = 0
        total_interviews = 0
        total_memos = 0
        valid_files = 0
        
        for file in json_files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    results = data.get('results', [])
                    total_horses += len(results)
                    total_interviews += sum(1 for r in results if r.get('interview') and r.get('interview').strip())
                    total_memos += sum(1 for r in results if r.get('memo') and r.get('memo').strip())
                    valid_files += 1
            except Exception:
                continue
        
        interview_coverage = (total_interviews / total_horses * 100) if total_horses > 0 else 0
        memo_coverage = (total_memos / total_horses * 100) if total_horses > 0 else 0
        
        return {
            'total_data_files': len(json_files),
            'valid_files': valid_files,
            'total_horses': total_horses,
            'interview_coverage_percent': round(interview_coverage, 2),
            'memo_coverage_percent': round(memo_coverage, 2),
            'average_horses_per_race': round(total_horses / valid_files, 1) if valid_files > 0 else 0
        }
    
    def generate_health_report(self, output_file: str = None) -> dict:
        """ヘルスレポートの生成"""
        self.logger.info("システムヘルスチェックを開始")
        
        report = {
            'system_health': self.get_system_health(),
            'data_quality': self.get_data_quality_report(),
            'recommendations': self._generate_recommendations()
        }
        
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"ヘルスレポートを保存: {output_path}")
        
        return report
    
    def _generate_recommendations(self) -> list:
        """推奨事項の生成"""
        recommendations = []
        
        health = self.get_system_health()
        
        # データファイルのチェック
        data_info = health.get('data_files', {})
        if data_info.get('total_files', 0) == 0:
            recommendations.append({
                'priority': 'high',
                'category': 'data',
                'message': 'データファイルがありません。スクレイピングを実行してください。'
            })
        
        # 環境設定のチェック
        env_info = health.get('environment', {})
        if not env_info.get('has_session_cookie', False):
            recommendations.append({
                'priority': 'critical',
                'category': 'configuration',
                'message': '実際のCookieが設定されていません。.envファイルを更新してください。'
            })
        
        # ログファイルのチェック
        log_info = health.get('recent_logs', {})
        if log_info.get('log_analysis', {}).get('error_count', 0) > 5:
            recommendations.append({
                'priority': 'medium',
                'category': 'monitoring',
                'message': '多数のエラーが検出されました。ログファイルを確認してください。'
            })
        
        return recommendations


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="System Monitor for Keiba Scraping")
    parser.add_argument("--output", help="Output file for health report")
    parser.add_argument("--format", choices=['json', 'console'], default='console', help="Output format")
    
    args = parser.parse_args()
    
    monitor = SystemMonitor()
    
    print("🔍 System Health Check Starting...")
    
    # ヘルスレポート生成
    report = monitor.generate_health_report(args.output)
    
    if args.format == 'console':
        print("\n=== System Health Report ===")
        
        # データ状況
        data_files = report['system_health'].get('data_files', {})
        if 'total_files' in data_files:
            print(f"📊 Data Status:")
            print(f"   Total files: {data_files['total_files']}")
            print(f"   Total size: {data_files['total_size_mb']} MB")
            if data_files.get('latest_files'):
                latest = data_files['latest_files'][0]
                if 'horse_count' in latest:
                    print(f"   Latest race: {latest['horse_count']} horses")
                    print(f"   Interview coverage: {latest.get('interview_count', 0)} horses")
                    print(f"   Memo coverage: {latest.get('memo_count', 0)} horses")
        
        # データ品質
        quality = report.get('data_quality', {})
        if 'interview_coverage_percent' in quality:
            print(f"\n🎯 Data Quality:")
            print(f"   Interview coverage: {quality['interview_coverage_percent']:.1f}%")
            print(f"   Memo coverage: {quality['memo_coverage_percent']:.1f}%")
            print(f"   Average horses per race: {quality['average_horses_per_race']}")
        
        # 推奨事項
        recommendations = report['recommendations']
        if recommendations:
            print(f"\n💡 Recommendations:")
            for rec in recommendations[:5]:  # Top 5
                priority_emoji = {'critical': '🚨', 'high': '⚠️', 'medium': '📝', 'low': 'ℹ️'}
                emoji = priority_emoji.get(rec['priority'], 'ℹ️')
                print(f"   {emoji} [{rec['category']}] {rec['message']}")
        else:
            print(f"\n✅ No critical issues found!")
    
    print(f"\n📄 Report saved to: {args.output if args.output else 'console only'}")


if __name__ == "__main__":
    main() 