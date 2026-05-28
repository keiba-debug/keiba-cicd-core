#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TARGET 投票内容確認ダイアログ自動押下エンジン

Session 127 (2026-05-24) で実装。 ふくだ判断:
  「TARGET の最後の投票ボタンさえ PG で押させるならそれでもよい」

技術: pywinauto 0.6.9 (Win32 backend)

検出対象ダイアログ:
  Window title: "投票内容確認"
  Body text   : "以下の買い目で投票します。"
  Buttons     : "投票" (clicked) / "キャンセル"
  Field       : "合計金額 NNN円" (検証)

安全機構 (シズネ視点で必須):
  1. デフォルト dry-run (--confirm 明示必須)
  2. 合計金額の上限チェック (--max-yen)
  3. ベット数の上限チェック (--max-bets)
  4. ダイアログタイトル完全一致 (誤認防止)
  5. ボタンラベル "投票" 完全一致
  6. JSONL 監査ログ追記 (data3/userdata/target_clicker/audit_{yyyy-mm}.jsonl)
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pywinauto import Desktop
from pywinauto.findwindows import ElementNotFoundError
from pywinauto.timings import TimeoutError as PWATimeoutError


DIALOG_TITLE = "投票内容確認"
VOTE_BUTTON_TITLE = "投票"
CANCEL_BUTTON_TITLE = "キャンセル"

# 投票後に出る完了ダイアログ
RESULT_DIALOG_TITLE = "投票終了"
OK_BUTTON_TITLE = "OK"

AUDIT_DIR = Path(os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")) \
    / "userdata" / "target_clicker"


@dataclass
class DialogContent:
    """投票内容確認ダイアログから抽出した検証用情報"""
    total_yen: int                    # 合計金額 (円)
    n_bets: int                       # 投票ベット数
    limit_yen: int                    # 購入限度額 (IPAT 残高)
    raw_text: str                     # 全文 (監査用)


@dataclass
class ReceiptInfo:
    """投票終了ダイアログから抽出した JRA 受付情報"""
    receipt_number: Optional[str]     # 受付番号 (例: "0029")
    receipt_time: Optional[str]       # 受付時刻 (例: "09:54")
    receipt_bets: Optional[int]       # 受付ベット数
    receipt_total_yen: Optional[int]  # 受付合計金額
    raw_text: str


# ============================================================
# session_expired phase 定数 (シズネ Session 132 🟡-2 / Session 133 実装)
# ============================================================
# auto_vote の事後検知が発火するフェーズ識別子。 文字列リテラル直書きは
# タイポすると常に False に流れて manual_review_required が静かに失われる
# 罠を構造的に防ぐため、 全箇所で本定数を参照する。

SESSION_EXPIRED_PHASE_VOTE_DIALOG_TIMEOUT = "vote_dialog_timeout"
SESSION_EXPIRED_PHASE_RESULT_DIALOG_TIMEOUT = "result_dialog_timeout"
SESSION_EXPIRED_PHASE_EXPLICIT_ERROR_DIALOG = "explicit_error_dialog"

# vote click 実行済 = 受付不明 = ふくだ手動照合必須となる phase の集合
# (将来 explicit_error_dialog の中で click 後系を分離する場合はここに追加)
VOTE_ALREADY_CLICKED_PHASES = frozenset({
    SESSION_EXPIRED_PHASE_RESULT_DIALOG_TIMEOUT,
})


@dataclass
class ClickResult:
    """投票試行の結果"""
    success: bool
    action: str                       # "clicked" / "dry_run" / "rejected" / "timeout" / "error"
    reason: str
    content: Optional[DialogContent]
    clicked_at: Optional[str] = None
    dialog_handle: Optional[int] = None
    receipt: Optional[ReceiptInfo] = None       # 投票完了後の JRA 受付情報
    result_closed: bool = False                 # 投票終了ダイアログを OK で閉じたか
    notify_text: Optional[str] = None           # Session 129: TTS で読み上げた文面 (audit 用)
    notify_spoken: Optional[bool] = None        # Session 129: TTS 成否 (None=未試行)
    # Session 132 (Phase 4-C-full 事後検知): セッション切れ検出時に set される
    # phase は SESSION_EXPIRED_PHASE_* 定数のいずれか (上記)
    session_expired: bool = False
    session_expired_phase: Optional[str] = None
    session_expired_title: Optional[str] = None     # 検出したエラーダイアログのタイトル
    session_expired_keyword: Optional[str] = None   # マッチしたキーワード
    session_expired_pattern_source: Optional[str] = None  # "default" / "file"
    race_id: Optional[str] = None               # ledger 記録用 (呼び出し元が set)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _extract_yen(text: str, key: str) -> Optional[int]:
    """テキストから '合計金額 100円' のような連続パターンを抽出"""
    pattern = re.compile(re.escape(key) + r"\s*([\d,]+)\s*円")
    m = pattern.search(text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _extract_int_after(text: str, key: str) -> Optional[int]:
    """'投票ベット数：1' のような数値を抽出 (全角・半角コロン両対応)"""
    pattern = re.compile(re.escape(key) + r"\s*[:：]?\s*([\d,]+)")
    m = pattern.search(text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


# TARGET ダイアログのラベル/値分離構造に対応するパース
# 実環境観察 (2026-05-24): texts は ['投票ベット数 : 15', '合計金額', '購入可能件数',
#   '購入限度額', '3,000円', '9,000件', '29,090円', '投票', 'キャンセル', ...] のような順序
# ラベル群が先、 値群が後で並ぶため、 ラベル順と値順の対応付けで解決する。
_LABEL_TO_UNIT = {
    "合計金額": "円",
    "購入限度額": "円",
    "購入可能件数": "件",
}
_VALUE_RE = re.compile(r"^([\d,]+)\s*(円|件)$")


def _extract_label_value_pairs(texts: list[str]) -> dict[str, int]:
    """ラベルと値が別コントロールに分離してる TARGET ダイアログ用のパーサ

    アルゴリズム:
      1. ラベル ('合計金額','購入限度額','購入可能件数') を出現順に集める
      2. 値 ('3,000円', '9,000件' 等) を出現順に集める (単位付き)
      3. ラベルの定義 unit と値の unit を順番にマッチング
         - ラベル '合計金額' (円) → 次の '円' 値
         - ラベル '購入可能件数' (件) → 次の '件' 値
         - ラベル '購入限度額' (円) → 次の '円' 値
    """
    label_order: list[str] = []
    values: list[tuple[int, str]] = []   # (数値, 単位)
    for t in texts:
        if t in _LABEL_TO_UNIT:
            label_order.append(t)
            continue
        m = _VALUE_RE.match(t)
        if m:
            try:
                num = int(m.group(1).replace(",", ""))
                values.append((num, m.group(2)))
            except ValueError:
                continue

    # 単位ごとにキュー化して順番に消費
    yen_q = [v for v, u in values if u == "円"]
    ken_q = [v for v, u in values if u == "件"]
    out: dict[str, int] = {}
    for lab in label_order:
        unit = _LABEL_TO_UNIT[lab]
        if unit == "円" and yen_q:
            out[lab] = yen_q.pop(0)
        elif unit == "件" and ken_q:
            out[lab] = ken_q.pop(0)
    return out


def _read_dialog_content(dlg) -> DialogContent:
    """ダイアログ内の Static テキスト群から内容を抽出"""
    texts: list[str] = []
    try:
        for child in dlg.descendants():
            try:
                t = child.window_text()
                if t and t.strip():
                    texts.append(t.strip())
            except Exception:
                continue
    except Exception:
        pass
    full = " | ".join(texts)

    # まず連続パターン ('合計金額 100円') で試す
    total_yen = _extract_yen(full, "合計金額") or 0
    limit_yen = _extract_yen(full, "購入限度額") or 0

    # 失敗 (= TARGET のラベル/値分離レイアウト) ならペア対応で抽出
    if total_yen == 0 or limit_yen == 0:
        pairs = _extract_label_value_pairs(texts)
        if total_yen == 0:
            total_yen = pairs.get("合計金額", 0)
        if limit_yen == 0:
            limit_yen = pairs.get("購入限度額", 0)

    n_bets = _extract_int_after(full, "投票ベット数") or 0
    return DialogContent(
        total_yen=total_yen,
        n_bets=n_bets,
        limit_yen=limit_yen,
        raw_text=full,
    )


def find_dialog_by_title(title: str, timeout_sec: int, poll_sec: float = 0.5):
    """指定タイトルのダイアログを待機"""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            dlg = Desktop(backend="win32").window(title=title)
            if dlg.exists(timeout=0.2):
                return dlg
        except (ElementNotFoundError, PWATimeoutError):
            pass
        except Exception:
            pass
        time.sleep(poll_sec)
    return None


def find_vote_dialog(timeout_sec: int = 30, poll_sec: float = 0.5):
    """投票内容確認ダイアログを待機"""
    return find_dialog_by_title(DIALOG_TITLE, timeout_sec, poll_sec)


_RECEIPT_NO_RE = re.compile(r"受付番号\s*[:：]\s*(\d+)")
_RECEIPT_TIME_RE = re.compile(r"受付時刻\s*[:：]\s*([\d:：]+)")
_RECEIPT_BETS_RE = re.compile(r"受付ベット数\s*[:：]\s*([\d,]+)")


def _read_receipt(dlg) -> ReceiptInfo:
    """投票終了ダイアログから JRA 受付情報を抽出"""
    texts: list[str] = []
    try:
        for child in dlg.descendants():
            try:
                t = child.window_text()
                if t and t.strip():
                    texts.append(t.strip())
            except Exception:
                continue
    except Exception:
        pass
    full = " | ".join(texts)

    no_m = _RECEIPT_NO_RE.search(full)
    tm_m = _RECEIPT_TIME_RE.search(full)
    bets_m = _RECEIPT_BETS_RE.search(full)
    pairs = _extract_label_value_pairs(texts)

    bets = None
    if bets_m:
        try:
            bets = int(bets_m.group(1).replace(",", ""))
        except ValueError:
            bets = None

    return ReceiptInfo(
        receipt_number=no_m.group(1) if no_m else None,
        receipt_time=tm_m.group(1).replace("：", ":") if tm_m else None,
        receipt_bets=bets,
        receipt_total_yen=pairs.get("合計金額"),
        raw_text=full,
    )


def close_result_dialog(timeout_sec: int = 10, verbose: bool = True
                        ) -> tuple[bool, Optional[ReceiptInfo]]:
    """投票終了ダイアログを検出して OK 押下。 (closed, receipt) を返す"""
    dlg = find_dialog_by_title(RESULT_DIALOG_TITLE, timeout_sec=timeout_sec)
    if dlg is None:
        if verbose:
            print(f"[{_now_iso()}] result dialog {RESULT_DIALOG_TITLE!r} "
                  f"not found within {timeout_sec}s (skip)")
        return (False, None)
    receipt = _read_receipt(dlg)
    if verbose:
        print(f"[{_now_iso()}] result dialog detected: "
              f"受付番号={receipt.receipt_number} 時刻={receipt.receipt_time} "
              f"ベット数={receipt.receipt_bets} 合計={receipt.receipt_total_yen}円")
    try:
        ok_btn = dlg.child_window(title=OK_BUTTON_TITLE)
        if not ok_btn.exists(timeout=2):
            if verbose:
                print(f"[{_now_iso()}] OK button not found in result dialog")
            return (False, receipt)
        ok_btn.click()
        if verbose:
            print(f"[{_now_iso()}] CLICKED [OK] on result dialog")
        return (True, receipt)
    except Exception as e:
        if verbose:
            print(f"[{_now_iso()}] OK click failed: {type(e).__name__}: {e}")
        return (False, receipt)


def click_vote_button(
    *,
    confirm: bool = False,
    max_yen: int = 100,
    max_bets: int = 1,
    timeout_sec: int = 30,
    close_result: bool = True,
    result_timeout_sec: int = 10,
    verbose: bool = True,
    notify: bool = True,
    detect_session_expired: bool = True,         # Session 132 (Phase 4-C-full)
    race_id: Optional[str] = None,               # Session 132: ledger 記録用
) -> ClickResult:
    """TARGET 投票ダイアログを検出して [投票] ボタンを click する。

    Args:
        confirm: True で実際に click。 False は dry-run (検出のみ)
        max_yen: この円を超えたら reject
        max_bets: このベット数を超えたら reject
        timeout_sec: ダイアログ待機タイムアウト
        verbose: stdout にログ出力
        notify: Session 129 — True で全 action (success/rejected/timeout/error)
                を TTS 音声通知する。 audit JSONL にも結果を焼き込む。
        detect_session_expired: Session 132 — True で timeout / close_result 失敗時に
                `launcher.detect_session_expired_dialog()` を呼び、 検出時 ClickResult に
                session_expired=True と各種情報を set + ledger event を記録する。
        race_id: ledger 記録時の race_id (None なら ledger は events_jsonl のみ追記)。
    """

    def vprint(msg: str) -> None:
        if verbose:
            print(msg)

    def aud(r: ClickResult) -> ClickResult:
        """_audit のラッパ (Session 129: notify 引数を一律伝播)"""
        if race_id and not r.race_id:
            r.race_id = race_id
        return _audit(r, notify=notify)

    vprint(f"[{_now_iso()}] dialog wait (timeout={timeout_sec}s) title={DIALOG_TITLE!r}")
    dlg = find_vote_dialog(timeout_sec=timeout_sec)
    if dlg is None:
        timeout_result = ClickResult(
            success=False, action="timeout",
            reason=f"dialog {DIALOG_TITLE!r} not found within {timeout_sec}s",
            content=None,
        )
        if detect_session_expired:
            _attach_session_expired_info(
                timeout_result, phase=SESSION_EXPIRED_PHASE_VOTE_DIALOG_TIMEOUT,
                vote_already_clicked=False, verbose=verbose,
            )
        return aud(timeout_result)

    handle = None
    try:
        handle = dlg.handle
    except Exception:
        pass

    content = _read_dialog_content(dlg)
    vprint(f"[{_now_iso()}] dialog detected: total={content.total_yen}円 "
           f"limit={content.limit_yen}円 bets={content.n_bets}")
    vprint(f"  raw: {content.raw_text[:300]}")

    # 検証
    if content.total_yen <= 0:
        return aud(ClickResult(
            success=False, action="rejected",
            reason=f"合計金額 抽出失敗 (total_yen=0)", content=content,
            dialog_handle=handle,
        ))
    if content.total_yen > max_yen:
        return aud(ClickResult(
            success=False, action="rejected",
            reason=f"合計金額 {content.total_yen}円 > 上限 {max_yen}円",
            content=content, dialog_handle=handle,
        ))
    if content.n_bets > max_bets:
        return aud(ClickResult(
            success=False, action="rejected",
            reason=f"ベット数 {content.n_bets} > 上限 {max_bets}",
            content=content, dialog_handle=handle,
        ))
    if content.limit_yen > 0 and content.total_yen > content.limit_yen:
        return aud(ClickResult(
            success=False, action="rejected",
            reason=f"IPAT 残高不足: 合計 {content.total_yen}円 > 残高 {content.limit_yen}円",
            content=content, dialog_handle=handle,
        ))

    # dry-run
    if not confirm:
        vprint(f"[{_now_iso()}] DRY-RUN: would click [{VOTE_BUTTON_TITLE}]")
        return aud(ClickResult(
            success=True, action="dry_run",
            reason="dry-run mode (--confirm not passed)",
            content=content, dialog_handle=handle,
        ))

    # 実 click
    try:
        btn = dlg.child_window(title=VOTE_BUTTON_TITLE, control_type="Button")
        if not btn.exists(timeout=2):
            # Win32 backend は control_type を無視するので fallback
            btn = dlg.child_window(title=VOTE_BUTTON_TITLE)
        btn.click()
        clicked_at = _now_iso()
        vprint(f"[{clicked_at}] CLICKED [{VOTE_BUTTON_TITLE}] button")
    except Exception as e:
        return aud(ClickResult(
            success=False, action="error",
            reason=f"click failed: {type(e).__name__}: {e}",
            content=content, dialog_handle=handle,
        ))

    # 投票終了ダイアログを検出して OK 押下
    receipt: Optional[ReceiptInfo] = None
    closed = False
    if close_result:
        # ダイアログ表示まで少し待つ
        time.sleep(1.0)
        closed, receipt = close_result_dialog(
            timeout_sec=result_timeout_sec, verbose=verbose,
        )

    final = ClickResult(
        success=True, action="clicked",
        reason="vote button clicked"
               + (" + result dialog closed" if closed else ""),
        content=content, clicked_at=clicked_at, dialog_handle=handle,
        receipt=receipt, result_closed=closed,
    )
    # Session 132 (Phase 4-C-full): 投票 click 後に「投票終了」 が出ない or
    # 受付番号取れない場合、 セッション切れの可能性。 投票 click 自体は実行済 = manual_review
    if detect_session_expired and (not closed or receipt is None
                                   or not receipt.receipt_number):
        _attach_session_expired_info(
            final, phase=SESSION_EXPIRED_PHASE_RESULT_DIALOG_TIMEOUT,
            vote_already_clicked=True, verbose=verbose,
        )
    return aud(final)


def _attach_session_expired_info(result: ClickResult, *, phase: str,
                                  vote_already_clicked: bool,
                                  verbose: bool = True) -> None:
    """ClickResult にセッション切れ事後検知の結果を attach (Session 132 / Phase 4-C-full)

    `launcher.detect_session_expired_dialog()` を呼んで、 検出時のみ ClickResult を
    更新する。 検出なしなら ClickResult は変更しない (= session_expired は False のまま)。

    launcher を遅延 import する (循環参照回避 + launcher 未配置時の auto_vote 単独動作維持)
    """
    try:
        from ml.target_clicker.launcher import detect_session_expired_dialog
    except Exception as e:
        if verbose:
            print(f"[auto_vote] launcher import failed (skip session_expired): {e}",
                  file=sys.stderr)
        return
    try:
        info = detect_session_expired_dialog(verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"[auto_vote] detect_session_expired_dialog raised: "
                  f"{type(e).__name__}: {e}", file=sys.stderr)
        return
    if not info.detected:
        return
    result.session_expired = True
    result.session_expired_phase = phase
    result.session_expired_title = info.title
    result.session_expired_keyword = info.matched_keyword
    result.session_expired_pattern_source = info.pattern_source
    # vote_already_clicked を理由文に追記 (audit の reason に焼き込む)
    suffix = f" [session_expired detected: phase={phase}, title={info.title!r}"
    if vote_already_clicked:
        suffix += ", vote_already_clicked=True, manual_review_required=True"
    suffix += "]"
    result.reason = (result.reason or "") + suffix


def _audit(result: ClickResult, *, notify: bool = True) -> ClickResult:
    """JSONL 監査ログ追記 + TTS 通知 (Session 129 拡張)

    - Session 129 (シズネ指摘 K): `ml.utils.jsonl_append.append_jsonl` を
      経由してアトミック (mkdir lock + fsync) で書き込む。
    - Session 129 (TTS 配線): notify=True なら全 action で音声通知。
      失敗パス (timeout/rejected/error) も通知 (シズネ「失敗の通知が大事」)。
    - Session 132 (Phase 4-C-full): session_expired 検出時は専用通知 +
      ledger IPAT_SESSION_EXPIRED_POSTVOTE event を記録 (通常 notify は抑制)。
    """
    # 1) TTS 通知 (audit ログに結果を書きたいので 先に呼ぶ)
    if notify:
        try:
            if result.session_expired:
                # Session 132: 通常の vote_result ではなく session_recovery_attempted を発話
                from ml.target_clicker.notify import (
                    notify_ipat_session_recovery_attempted,
                )
                outcome = notify_ipat_session_recovery_attempted(
                    detected_title=result.session_expired_title, enabled=True,
                )
            else:
                from ml.target_clicker.notify import notify_vote_result
                outcome = notify_vote_result(result, enabled=True)
            result.notify_text = outcome.text
            result.notify_spoken = outcome.spoken
        except Exception as e:
            # 通知失敗は本体を止めない (best-effort)
            print(f"[notify] hook failed: {type(e).__name__}: {e}", file=sys.stderr)
            result.notify_text = None
            result.notify_spoken = False

    # 2) ledger event 記録 (Session 132: session_expired 検出時のみ)
    if result.session_expired:
        try:
            from ml.purchase_ledger.writer import record_ipat_session_expired_postvote
            record_ipat_session_expired_postvote(
                race_id=result.race_id or "",
                detected_phase=result.session_expired_phase or "unknown",
                detected_dialog_title=result.session_expired_title,
                matched_keyword=result.session_expired_keyword,
                vote_already_clicked=(result.session_expired_phase in VOTE_ALREADY_CLICKED_PHASES),
                pattern_source=result.session_expired_pattern_source or "default",
            )
        except Exception as e:
            print(f"[ledger] record_ipat_session_expired_postvote failed: {e}",
                  file=sys.stderr)

    # 3) JSONL 監査ログ追記 (Session 129: jsonl_append でアトミック化)
    try:
        from ml.utils.jsonl_append import append_jsonl
        now = datetime.now()
        log_path = AUDIT_DIR / f"audit_{now.strftime('%Y-%m')}.jsonl"
        entry = {
            "ts": _now_iso(),
            "success": result.success,
            "action": result.action,
            "reason": result.reason,
            "clicked_at": result.clicked_at,
            "dialog_handle": result.dialog_handle,
            "race_id": result.race_id,
            "total_yen": result.content.total_yen if result.content else None,
            "n_bets": result.content.n_bets if result.content else None,
            "limit_yen": result.content.limit_yen if result.content else None,
            "raw_text": result.content.raw_text if result.content else None,
            "receipt_number": result.receipt.receipt_number if result.receipt else None,
            "receipt_time": result.receipt.receipt_time if result.receipt else None,
            "receipt_bets": result.receipt.receipt_bets if result.receipt else None,
            "receipt_total_yen": result.receipt.receipt_total_yen if result.receipt else None,
            "receipt_raw_text": result.receipt.raw_text if result.receipt else None,
            "result_closed": result.result_closed,
            # Session 129: TTS 通知結果も audit に焼き込む (シズネ「通知ログも audit 化」)
            "notify_text": result.notify_text,
            "notify_spoken": result.notify_spoken,
            # Session 132 (Phase 4-C-full): session_expired 事後検知
            "session_expired": result.session_expired,
            "session_expired_phase": result.session_expired_phase,
            "session_expired_title": result.session_expired_title,
            "session_expired_keyword": result.session_expired_keyword,
            "session_expired_pattern_source": result.session_expired_pattern_source,
        }
        ok = append_jsonl(log_path, entry, timeout_sec=5.0)
        if not ok:
            print(f"[audit] append_jsonl returned False: {log_path}", file=sys.stderr)
    except Exception as e:
        # 監査ログ失敗は本体を止めない (ログ欠損 < 状態欠損、 シズネ原則)
        print(f"[audit] failed to write: {e}", file=sys.stderr)
    return result
