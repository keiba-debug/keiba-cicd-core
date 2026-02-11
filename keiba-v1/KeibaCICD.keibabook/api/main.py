#!/usr/bin/env python3
"""
FastAPI Backend for KeibaCICD GUI
MVP実装 - CLI実行とログストリーミング（Day4: エラーハンドリング強化）
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import asyncio
import subprocess
import uuid
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import sys
import os
import shutil
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 設定値
MAX_RETRY_ATTEMPTS = int(os.getenv('MAX_RETRY_ATTEMPTS', '3'))
RETRY_WAIT_SECONDS = int(os.getenv('RETRY_WAIT_SECONDS', '5'))
RETRY_BACKOFF_MULTIPLIER = float(os.getenv('RETRY_BACKOFF_MULTIPLIER', '2'))
LOG_RETENTION_DAYS = int(os.getenv('LOG_RETENTION_DAYS', '7'))
DATA_ROOT_PATH = os.getenv('DATA_ROOT_PATH', 'Z:/KEIBA-CICD')
KEIBA_PROJECT_PATH = os.getenv('KEIBA_PROJECT_PATH', 'C:/source/git-h.fukuda1207/_keiba/keiba-cicd-core/KeibaCICD.keibabook')

app = FastAPI(title="KeibaCICD API", version="0.1.0")

# CORS設定（ローカル開発用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ジョブ管理
jobs: Dict[str, Dict[str, Any]] = {}
job_logs_dir = Path("./job_logs")
job_logs_dir.mkdir(exist_ok=True)

class RunRequest(BaseModel):
    """CLI実行リクエスト"""
    command: str  # 'fast_batch', 'integrator', 'markdown', 'accumulator'
    args: Dict[str, Any]

class JobResponse(BaseModel):
    """ジョブレスポンス"""
    job_id: str
    status: str
    created_at: str

@app.get("/")
async def root():
    """ヘルスチェック"""
    return {"status": "ok", "service": "KeibaCICD API"}

@app.get("/health")
async def health_check():
    """
    システムヘルスチェック（詳細版）
    """
    from pathlib import Path
    import psutil
    
    # ディスク使用状況
    log_dir_size = sum(f.stat().st_size for f in job_logs_dir.glob("*") if f.is_file())
    
    # ジョブ統計
    job_stats = {
        "total": len(jobs),
        "running": sum(1 for j in jobs.values() if j["status"] == "running"),
        "completed": sum(1 for j in jobs.values() if j["status"] == "completed"),
        "failed": sum(1 for j in jobs.values() if j["status"] == "failed"),
        "error": sum(1 for j in jobs.values() if j["status"] == "error")
    }
    
    # プロセス情報
    process = psutil.Process()
    memory_info = process.memory_info()
    
    # データディレクトリの存在確認
    data_dir_exists = Path(DATA_ROOT_PATH).exists() if DATA_ROOT_PATH else False
    project_dir_exists = Path(KEIBA_PROJECT_PATH).exists() if KEIBA_PROJECT_PATH else False
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "KeibaCICD API",
        "version": "0.1.0",
        "environment": {
            "data_root_path": DATA_ROOT_PATH,
            "keiba_project_path": KEIBA_PROJECT_PATH,
            "data_dir_exists": data_dir_exists,
            "project_dir_exists": project_dir_exists
        },
        "jobs": job_stats,
        "logs": {
            "directory": str(job_logs_dir),
            "total_size_mb": round(log_dir_size / (1024 * 1024), 2),
            "retention_days": LOG_RETENTION_DAYS
        },
        "system": {
            "memory_usage_mb": round(memory_info.rss / (1024 * 1024), 2),
            "cpu_percent": process.cpu_percent()
        },
        "retry_config": {
            "max_attempts": MAX_RETRY_ATTEMPTS,
            "wait_seconds": RETRY_WAIT_SECONDS,
            "backoff_multiplier": RETRY_BACKOFF_MULTIPLIER
        }
    }

@app.post("/run", response_model=JobResponse)
async def run_command(request: RunRequest, background_tasks: BackgroundTasks):
    """
    CLIコマンドを非同期実行
    """
    job_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    
    # ジョブ情報を登録
    jobs[job_id] = {
        "id": job_id,
        "command": request.command,
        "args": request.args,
        "status": "running",
        "created_at": created_at,
        "log_file": str(job_logs_dir / f"{job_id}.log")
    }
    
    # バックグラウンドでCLI実行
    background_tasks.add_task(execute_cli, job_id, request.command, request.args)
    
    return JobResponse(job_id=job_id, status="running", created_at=created_at)

async def execute_cli(job_id: str, command: str, args: Dict[str, Any], retry_count: int = 0):
    """
    CLIを実行してログをファイルに出力（自動リトライ機能付き）
    """
    log_file = jobs[job_id]["log_file"]
    
    try:
        # コマンドを構築
        cmd_parts = build_command(command, args)
        logger.info(f"Executing (attempt {retry_count + 1}): {' '.join(cmd_parts)}")
        
        # プロセス実行
        with open(log_file, "a" if retry_count > 0 else "w", encoding="utf-8") as f:
            if retry_count > 0:
                f.write(f"\n\n=== Retry Attempt {retry_count + 1} at {datetime.now().isoformat()} ===\n")
            
            process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=KEIBA_PROJECT_PATH
            )
            
            # ログをストリーミング
            async for line in process.stdout:
                decoded_line = line.decode("utf-8", errors="replace")
                f.write(decoded_line)
                f.flush()
            
            await process.wait()
            
            # リトライ可能なエラーかチェック
            if process.returncode != 0 and retry_count < MAX_RETRY_ATTEMPTS - 1:
                if is_retryable_error(log_file):
                    wait_time = RETRY_WAIT_SECONDS * (RETRY_BACKOFF_MULTIPLIER ** retry_count)
                    logger.info(f"Retryable error detected. Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    await execute_cli(job_id, command, args, retry_count + 1)
                    return
            
            # ステータス更新
            jobs[job_id]["status"] = "completed" if process.returncode == 0 else "failed"
            jobs[job_id]["return_code"] = process.returncode
            jobs[job_id]["retry_count"] = retry_count
            
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["retry_count"] = retry_count
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n\nError: {e}\n")

def is_retryable_error(log_file: str) -> bool:
    """ログファイルからリトライ可能なエラーか判定"""
    retryable_patterns = [
        "timeout",
        "connection error",
        "network",
        "502 bad gateway",
        "503 service unavailable",
        "504 gateway timeout",
        "temporary failure"
    ]
    
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read().lower()
            return any(pattern in content for pattern in retryable_patterns)
    except:
        return False

def build_command(command: str, args: Dict[str, Any]) -> List[str]:
    """
    コマンドライン引数を構築
    """
    python_exe = sys.executable
    
    # コマンドマッピング
    command_map = {
        "fast_batch": ["python", "-m", "src.fast_batch_cli"],
        "integrator": ["python", "-m", "src.integrator_cli"],
        "markdown": ["python", "-m", "src.markdown_cli"],
        "accumulator": ["python", "-m", "src.accumulator_cli"],
        "organizer": ["python", "-m", "src.organizer_cli"]
    }
    
    if command not in command_map:
        raise ValueError(f"Unknown command: {command}")
    
    cmd_parts = command_map[command]
    
    # サブコマンドの処理
    if "subcommand" in args:
        cmd_parts.append(args.pop("subcommand"))
    
    # 引数を追加
    for key, value in args.items():
        if value is not None:
            if isinstance(value, bool):
                if value:
                    cmd_parts.append(f"--{key}")
            else:
                cmd_parts.append(f"--{key}")
                cmd_parts.append(str(value))
    
    return cmd_parts

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    ジョブのステータスを取得
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return jobs[job_id]

@app.get("/jobs")
async def list_jobs(limit: int = 10):
    """
    最近のジョブ一覧を取得
    """
    sorted_jobs = sorted(
        jobs.values(),
        key=lambda x: x["created_at"],
        reverse=True
    )
    return sorted_jobs[:limit]

@app.get("/logs/{job_id}")
async def get_logs(job_id: str, tail: Optional[int] = None):
    """
    ジョブのログを取得（ファイルから読み込み）
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    log_file = Path(jobs[job_id]["log_file"])
    
    if not log_file.exists():
        return {"logs": [], "status": jobs[job_id]["status"]}
    
    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    
    if tail and tail > 0:
        lines = lines[-tail:]
    
    return {
        "logs": lines,
        "status": jobs[job_id]["status"],
        "total_lines": len(lines)
    }

@app.get("/artifacts")
async def list_artifacts(date: str):
    """
    指定日の成果物（organized配下）を列挙（拡張版）
    """
    from pathlib import Path
    import glob
    
    # 日付形式をYYYY-MM-DDまたはYYYY/MM/DDを受け付ける
    date_normalized = date.replace("-", "/")
    date_path = date_normalized.replace("/", "\\")
    base_path = Path("Z:/KEIBA-CICD/data/organized") / date_path
    
    if not base_path.exists():
        return {"date": date, "venues": [], "error": "Date not found"}
    
    venues = []
    for venue_dir in base_path.iterdir():
        if venue_dir.is_dir():
            venue_name = venue_dir.name
            
            # レース情報を収集
            races = []
            
            # integrated JSONから情報を取得
            for json_file in venue_dir.glob("integrated_*.json"):
                race_id = json_file.stem.replace("integrated_", "")
                race_number = race_id[-2:] if len(race_id) >= 2 else "00"
                
                # JSONからレース名を取得（可能な場合）
                race_name = f"{race_number}R"
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        race_data = json.load(f)
                        if 'race_info' in race_data:
                            race_name = race_data['race_info'].get('race_name', race_name)
                            if not race_name:
                                race_name = f"{race_number}R"
                except:
                    pass
                
                # MDファイルの存在確認
                md_file = venue_dir / f"{race_id}.md"
                has_md = md_file.exists()
                
                races.append({
                    "race_id": race_id,
                    "race_number": int(race_number) if race_number.isdigit() else 0,
                    "race_name": race_name,
                    "has_md": has_md,
                    "has_json": True
                })
            
            # MDファイルのみ存在する場合も追加
            for md_file in venue_dir.glob("*.md"):
                if not md_file.stem.startswith("integrated"):
                    race_id = md_file.stem
                    if not any(r['race_id'] == race_id for r in races):
                        race_number = race_id[-2:] if len(race_id) >= 2 else "00"
                        races.append({
                            "race_id": race_id,
                            "race_number": int(race_number) if race_number.isdigit() else 0,
                            "race_name": f"{race_number}R",
                            "has_md": True,
                            "has_json": False
                        })
            
            # レース番号でソート
            races.sort(key=lambda x: x['race_number'])
            
            venues.append({
                "venue": venue_name,
                "venue_code": venue_name,  # 将来的にコード変換可能
                "races": races,
                "total_races": len(races)
            })
    
    return {
        "date": date_normalized,
        "venues": venues,
        "total_venues": len(venues),
        "total_races": sum(v['total_races'] for v in venues)
    }

@app.post("/retry/{job_id}")
async def retry_job(job_id: str, background_tasks: BackgroundTasks):
    """
    失敗したジョブを再試行
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job["status"] not in ["failed", "error"]:
        raise HTTPException(status_code=400, detail="Job is not in failed state")
    
    # 新しいジョブIDで再実行
    new_job_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    
    jobs[new_job_id] = {
        "id": new_job_id,
        "command": job["command"],
        "args": job["args"],
        "status": "running",
        "created_at": created_at,
        "original_job_id": job_id,
        "log_file": str(job_logs_dir / f"{new_job_id}.log")
    }
    
    background_tasks.add_task(execute_cli, new_job_id, job["command"], job["args"])
    
    return JobResponse(job_id=new_job_id, status="running", created_at=created_at)

class PartialRerunRequest(BaseModel):
    """部分再実行リクエスト"""
    date: str
    data_types: List[str]  # ['seiseki', 'odds', 'race_info'] など

@app.post("/rerun-partial")
async def rerun_partial(request: PartialRerunRequest, background_tasks: BackgroundTasks):
    """
    特定データ型のみ再取得
    """
    job_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    
    # 部分実行用のコマンドを構築
    command = "fast_batch"
    args = {
        "subcommand": "data",
        "start": request.date,
        "end": request.date,
        "data-types": ",".join(request.data_types)  # カンマ区切りで渡す（ハイフン付き）
    }
    
    jobs[job_id] = {
        "id": job_id,
        "command": command,
        "args": args,
        "status": "running",
        "created_at": created_at,
        "partial_rerun": True,
        "data_types": request.data_types,
        "log_file": str(job_logs_dir / f"{job_id}.log")
    }
    
    background_tasks.add_task(execute_cli, job_id, command, args)
    
    return JobResponse(job_id=job_id, status="running", created_at=created_at)

@app.get("/markdown/{race_id}")
async def get_markdown(race_id: str):
    """
    レースのMarkdownを取得
    """
    # race_idから日付と場所を推測
    # 例: 202504020111 -> 2025/04/02, 場所コード01, 11R
    if len(race_id) < 12:
        raise HTTPException(status_code=400, detail="Invalid race_id format")
    
    year = "2025"
    month = race_id[4:6]
    day = race_id[6:8]
    
    # 場所コードマッピング
    venue_map = {
        "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
        "05": "東京", "06": "中山", "07": "中京", "08": "京都",
        "09": "阪神", "10": "小倉"
    }
    venue_code = race_id[8:10]
    venue_name = venue_map.get(venue_code, "")
    
    if not venue_name:
        raise HTTPException(status_code=400, detail="Unknown venue code")
    
    # MDファイルパス構築
    md_path = Path(f"Z:/KEIBA-CICD/data/organized/{year}/{month}/{day}/{venue_name}/{race_id}.md")
    
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Markdown file not found")
    
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    return {
        "race_id": race_id,
        "venue": venue_name,
        "content": content
    }

@app.get("/markdown_html/{race_id}")
async def get_markdown_html(race_id: str):
    """
    レースのMarkdownをHTML形式で取得
    """
    import markdown2
    
    # まずMarkdownを取得
    md_response = await get_markdown(race_id)
    
    if "content" not in md_response:
        raise HTTPException(status_code=404, detail="Markdown not found")
    
    # Markdown→HTML変換
    html_content = markdown2.markdown(
        md_response["content"],
        extras=["tables", "fenced-code-blocks", "header-ids"]
    )
    
    # 基本的なスタイルを含むHTMLテンプレート
    full_html = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{md_response.get('race_id', 'Race')} - {md_response.get('venue', '')}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Hiragino Sans', sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background: #f5f5f5;
            }}
            h1, h2, h3 {{ color: #2c3e50; margin-top: 1.5em; }}
            h1 {{ border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
            h2 {{ border-bottom: 1px solid #ecf0f1; padding-bottom: 5px; }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 20px 0;
                background: white;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            th {{
                background: #3498db;
                color: white;
                padding: 10px;
                text-align: left;
            }}
            td {{
                padding: 10px;
                border-bottom: 1px solid #ecf0f1;
            }}
            tr:hover {{ background: #f8f9fa; }}
            code {{
                background: #f4f4f4;
                padding: 2px 5px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
            }}
            pre {{
                background: #2c3e50;
                color: #ecf0f1;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
            }}
            blockquote {{
                border-left: 4px solid #3498db;
                margin: 1em 0;
                padding-left: 1em;
                color: #7f8c8d;
            }}
            details {{
                background: white;
                padding: 10px;
                margin: 10px 0;
                border-radius: 5px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }}
            summary {{
                cursor: pointer;
                font-weight: bold;
                color: #2c3e50;
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    return {
        "race_id": race_id,
        "venue": md_response.get('venue', ''),
        "html": full_html,
        "raw_html": html_content
    }

async def cleanup_old_logs():
    """
    古いログファイルを削除（バックグラウンドタスク）
    """
    while True:
        try:
            cutoff_date = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
            
            for log_file in job_logs_dir.glob("*.log"):
                if log_file.stat().st_mtime < cutoff_date.timestamp():
                    logger.info(f"Removing old log file: {log_file}")
                    log_file.unlink()
            
            # 対応するジョブ情報も削除
            job_ids_to_remove = []
            for job_id, job_info in jobs.items():
                if "created_at" in job_info:
                    job_date = datetime.fromisoformat(job_info["created_at"])
                    if job_date < cutoff_date:
                        job_ids_to_remove.append(job_id)
            
            for job_id in job_ids_to_remove:
                del jobs[job_id]
                logger.info(f"Removed old job info: {job_id}")
            
        except Exception as e:
            logger.error(f"Error in log cleanup: {e}")
        
        # 24時間ごとに実行
        await asyncio.sleep(86400)

@app.on_event("startup")
async def startup_event():
    """
    アプリケーション起動時の処理
    """
    logger.info("Starting KeibaCICD API...")
    logger.info(f"Data root path: {DATA_ROOT_PATH}")
    logger.info(f"Project path: {KEIBA_PROJECT_PATH}")
    logger.info(f"Log retention: {LOG_RETENTION_DAYS} days")
    
    # ログクリーンアップタスクを開始
    asyncio.create_task(cleanup_old_logs())

@app.get("/logs/download/{job_id}")
async def download_log(job_id: str):
    """
    ログファイルをダウンロード
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    log_file = Path(jobs[job_id]["log_file"])
    
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="Log file not found")
    
    return FileResponse(
        path=str(log_file),
        filename=f"job_{job_id}.log",
        media_type="text/plain"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)