#!/usr/bin/env python3
"""
エンコーディング問題の修正スクリプト
Windows環境（cp932）で絵文字が表示できない問題を修正
"""

import os
import re
import glob

def remove_emojis(text):
    """絵文字を代替文字に置き換える"""
    replacements = {
        '🚀': '[START]',
        '📊': '[DATA]',
        '⚡': '[FAST]',
        '🔥': '[HOT]',
        '📅': '[DATE]',
        '✅': '[OK]',
        '❌': '[ERROR]',
        '📋': '[LIST]',
        '🏇': '[RACE]',
        '💪': '[STRONG]',
        '⭐': '[STAR]',
        '🎯': '[TARGET]',
        '🎉': '[DONE]',
        '📁': '[FILE]',
        '📂': '[FOLDER]',
        '📑': '[INDEX]',
        '🔍': '[SEARCH]',
        '💾': '[SAVE]',
        '📄': '[DOC]',
        '🧹': '[CLEAN]',
        '⏸️': '[PAUSE]',
        '⏱️': '[TIME]',
        '🐴': '[HORSE]',
        '🏟️': '[VENUE]',
        '🏆': '[TROPHY]',
        '📏': '[RULER]',
        '☁️': '[CLOUD]',
        '⚙️': '[SETTING]',
        '📝': '[MEMO]',
        '🔧': '[TOOL]',
        '⚠️': '[WARN]',
        '💡': '[IDEA]',
        '📚': '[BOOK]',
        '🆕': '[NEW]',
        '📆': '[CALENDAR]',
        '🔄': '[REFRESH]',
        '➕': '[PLUS]',
        '➖': '[MINUS]',
        '⏰': '[ALARM]',
        '📉': '[CHART]',
        '📈': '[UP]',
        '🔢': '[NUM]',
        '🤖': '[BOT]'
    }
    
    for emoji, replacement in replacements.items():
        text = text.replace(emoji, replacement)
    
    # その他のUnicode絵文字を削除
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    
    text = emoji_pattern.sub('', text)
    return text

def fix_file(filepath):
    """ファイル内の絵文字を修正"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        content = remove_emojis(content)
        
        if original_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed: {filepath}")
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """メイン処理"""
    print("絵文字の修正を開始します...")
    
    # 修正対象のファイル
    target_files = [
        "src/batch/optimized_data_fetcher.py",
        "src/batch/core/common.py",
        "src/fast_batch_cli.py",
        "src/batch_cli.py",
        "src/integrator_cli.py",
        "src/organizer_cli.py",
        "src/integrator/race_data_integrator.py",
        "src/utils/file_organizer.py"
    ]
    
    fixed_count = 0
    for target in target_files:
        if os.path.exists(target):
            if fix_file(target):
                fixed_count += 1
    
    print(f"\n修正完了: {fixed_count}ファイル")

if __name__ == "__main__":
    main()