#!/usr/bin/env python3
"""
MD結果確認スクリプト
"""

import glob
import os

def check_md_file(md_file_path):
    """MDファイルの結果セクションを確認"""
    try:
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # レース結果セクションを探す
        if '## 🏁 レース結果' in content:
            # セクションを抽出
            start_idx = content.index('## 🏁 レース結果')
            end_idx = content.find('\n## ', start_idx + 1)
            if end_idx == -1:
                end_idx = len(content)
            
            results_section = content[start_idx:end_idx]
            
            # 新機能の確認
            has_lap_summary = 'レースラップ要約' in results_section
            has_extended_columns = '上り3F' in results_section and '通過' in results_section and '4角' in results_section
            has_payouts = '### 払戻' in results_section
            
            return {
                'file': os.path.basename(md_file_path),
                'has_results': True,
                'has_lap_summary': has_lap_summary,
                'has_extended_columns': has_extended_columns,
                'has_payouts': has_payouts,
                'sample': results_section[:500] + '...' if len(results_section) > 500 else results_section
            }
        else:
            return {
                'file': os.path.basename(md_file_path),
                'has_results': False
            }
    except Exception as e:
        return {
            'file': os.path.basename(md_file_path),
            'error': str(e)
        }

def main():
    # MDファイルを取得
    md_files = glob.glob('Z:/KEIBA-CICD/data/organized/2025/08/23/*/*.md')
    
    print(f"Found {len(md_files)} MD files")
    print("=" * 60)
    
    # 各ファイルをチェック
    summary = {
        'total': len(md_files),
        'with_results': 0,
        'with_lap_summary': 0,
        'with_extended_columns': 0,
        'with_payouts': 0
    }
    
    for i, md_file in enumerate(md_files[:3]):  # まず3ファイルだけチェック
        result = check_md_file(md_file)
        
        print(f"\n[{i+1}] {result['file']}")
        
        if 'error' in result:
            print(f"  ERROR: {result['error']}")
        elif result['has_results']:
            summary['with_results'] += 1
            print(f"  [OK] Has results section")
            
            if result['has_lap_summary']:
                summary['with_lap_summary'] += 1
                print(f"  [OK] Has lap summary")
            else:
                print(f"  [--] No lap summary")
            
            if result['has_extended_columns']:
                summary['with_extended_columns'] += 1
                print(f"  [OK] Has extended columns (上り3F, 通過, 4角)")
            else:
                print(f"  [--] No extended columns")
            
            if result['has_payouts']:
                summary['with_payouts'] += 1
                print(f"  [OK] Has payouts table")
            else:
                print(f"  [--] No payouts table")
            
            print(f"\n  Sample:\n{result['sample']}")
        else:
            print(f"  [--] No results section")
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"  Total files: {summary['total']}")
    print(f"  With results: {summary['with_results']}")
    print(f"  With lap summary: {summary['with_lap_summary']}")
    print(f"  With extended columns: {summary['with_extended_columns']}")
    print(f"  With payouts: {summary['with_payouts']}")

if __name__ == "__main__":
    main()