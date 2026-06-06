#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""W7: 見送り通知だけ VOICEVOX「アナウンス」声 (id30) に差し替えるテスト。

ふくだ要望: 投票成功/開始は高テンション声のまま、 見送りだけ落ち着いた声に
(テンションのコントラストが狙い)。 speak() に speaker 引数を足し、 見送りパス
(bettype_scheduler.notify_skip) だけ VOICEVOX_SPEAKER_SKIP を渡す。

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_notify_skip_speaker.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import ml.target_clicker.notify as notify


def test_skip_speaker_default_is_30():
    """env 未設定時の見送り話者は 30 (アナウンス)。"""
    assert notify.VOICEVOX_SPEAKER_SKIP == 30


def test_speak_threads_speaker_to_voicevox(monkeypatch):
    """speak(speaker=N) が VOICEVOX 経路に speaker=N を渡す。"""
    captured = {}

    def fake_voicevox(text, *, speaker=None, timeout=20.0):
        captured["text"] = text
        captured["speaker"] = speaker
        return True

    monkeypatch.setattr(notify, "TTS_ENGINE", "voicevox")
    monkeypatch.setattr(notify, "_try_voicevox", fake_voicevox)

    assert notify.speak("テスト 見送り", speaker=30) is True
    assert captured["speaker"] == 30
    assert captured["text"] == "テスト 見送り"


def test_speak_default_speaker_is_none(monkeypatch):
    """speaker 未指定なら None を渡す (VOICEVOX 側が既定 VOICEVOX_SPEAKER を使う)。"""
    captured = {}

    def fake_voicevox(text, *, speaker=None, timeout=20.0):
        captured["speaker"] = speaker
        return True

    monkeypatch.setattr(notify, "TTS_ENGINE", "voicevox")
    monkeypatch.setattr(notify, "_try_voicevox", fake_voicevox)

    assert notify.speak("通常メッセージ") is True
    assert captured["speaker"] is None


def test_sapi_path_ignores_speaker(monkeypatch):
    """SAPI 経路では speaker を無視して落ちない (VOICEVOX 限定機能)。"""
    monkeypatch.setattr(notify, "TTS_ENGINE", "sapi")
    monkeypatch.setattr(notify, "_try_pyttsx3", lambda text, rate=0: False)
    calls = {}

    def fake_sapi(text, rate=0, pitch=None, timeout_sec=30):
        calls["text"] = text
        return True

    monkeypatch.setattr(notify, "_try_ps_sapi", fake_sapi)
    # speaker を渡しても SAPI 経路では TypeError 等で落ちない
    assert notify.speak("見送り", speaker=30) is True
    assert calls["text"] == "見送り"


def test_notify_skip_passes_skip_speaker(monkeypatch):
    """bettype_scheduler.notify_skip が VOICEVOX_SPEAKER_SKIP を speaker に渡す。"""
    from ml.strategies import bettype_scheduler

    captured = {}

    def fake_speak(text, *, rate=0, async_=False, speaker=None):
        captured["text"] = text
        captured["async_"] = async_
        captured["speaker"] = speaker
        return True

    # notify_skip は関数内で from ...notify import speak するので notify.speak を差し替える
    monkeypatch.setattr(notify, "speak", fake_speak)

    bettype_scheduler.notify_skip("5R", "買い目なし")

    assert captured["speaker"] == 30           # = VOICEVOX_SPEAKER_SKIP
    assert captured["async_"] is False         # skip は同期発話必須 (プロセス即 exit 対策)
    assert "見送り" in captured["text"]
    assert "5レース" in captured["text"]        # R→レース 変換維持 (アール誤読防止)


def test_skip_speaker_env_override(monkeypatch):
    """KEIBA_VOICEVOX_SPEAKER_SKIP で見送り話者を上書きできる (reload で反映)。"""
    import importlib

    monkeypatch.setenv("KEIBA_VOICEVOX_SPEAKER_SKIP", "7")
    reloaded = importlib.reload(notify)
    try:
        assert reloaded.VOICEVOX_SPEAKER_SKIP == 7
    finally:
        # 後続テストへ影響しないよう既定に戻す
        monkeypatch.delenv("KEIBA_VOICEVOX_SPEAKER_SKIP", raising=False)
        importlib.reload(notify)
