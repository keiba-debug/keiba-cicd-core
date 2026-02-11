"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type ActionType = "paddok" | "seiseki";

const PRESETS = [5, 9, 10];

interface TrackFetchActionsProps {
  date: string;
  track: string;
  className?: string;
}

export function TrackFetchActions({ date, track, className }: TrackFetchActionsProps) {
  const [running, setRunning] = useState<{ action: ActionType; from: number; to?: number } | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [customFrom, setCustomFrom] = useState("5");
  const [customTo, setCustomTo] = useState("");

  const execute = async (action: ActionType, fromRace: number, toRace?: number) => {
    setRunning({ action, from: fromRace, to: toRace });
    const rangeInfo = toRace ? `${fromRace}R〜${toRace}R` : `${fromRace}R〜`;
    setStatus(`${rangeInfo} 実行中...`);

    try {
      const response = await fetch("/api/admin/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          date,
          raceFrom: fromRace,
          raceTo: toRace,
          track,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      let isCompleted = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = JSON.parse(line.slice(6));
          if (data.type === "complete") {
            setStatus(String(data.message ?? "完了"));
            isCompleted = true;
          }
          if (data.type === "error") {
            setStatus(String(data.message ?? "エラー"));
            isCompleted = true;
          }
        }
      }

      if (!isCompleted) {
        setStatus("完了");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(`エラー: ${message}`);
    } finally {
      setRunning(null);
    }
  };

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">開始</span>
        <input
          type="number"
          min={1}
          max={12}
          value={customFrom}
          onChange={(event) => setCustomFrom(event.target.value)}
          aria-label="開始レース番号"
          className="h-7 w-16 rounded-md border bg-background px-2 text-xs"
          disabled={!!running}
        />
        <span className="text-xs text-muted-foreground">R 〜</span>
        <input
          type="number"
          min={1}
          max={12}
          value={customTo}
          onChange={(event) => setCustomTo(event.target.value)}
          placeholder="任意"
          aria-label="終了レース番号"
          className="h-7 w-16 rounded-md border bg-background px-2 text-xs"
          disabled={!!running}
        />
        <span className="text-xs text-muted-foreground">R</span>
        <Button
          variant="outline"
          size="sm"
          disabled={!!running || !customFrom}
          onClick={() => execute("paddok", Number(customFrom), customTo ? Number(customTo) : undefined)}
          title={`${track} ${customFrom}R以降 パドック取得`}
        >
          {running?.action === "paddok" && running.from === Number(customFrom) ? "⏳" : "🐎"}
          パドック
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!!running || !customFrom}
          onClick={() => execute("seiseki", Number(customFrom), customTo ? Number(customTo) : undefined)}
          title={`${track} ${customFrom}R以降 成績取得`}
        >
          {running?.action === "seiseki" && running.from === Number(customFrom) ? "⏳" : "🏆"}
          成績
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {PRESETS.map((fromRace) => (
          <React.Fragment key={fromRace}>
            <Button
              variant="outline"
              size="sm"
              disabled={!!running}
              onClick={() => execute("paddok", fromRace)}
              title={`${track} ${fromRace}R以降 パドック取得`}
            >
              {running?.action === "paddok" && running.from === fromRace ? "⏳" : "🐎"}
              {fromRace}R〜パドック
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!!running}
              onClick={() => execute("seiseki", fromRace)}
              title={`${track} ${fromRace}R以降 成績取得`}
            >
              {running?.action === "seiseki" && running.from === fromRace ? "⏳" : "🏆"}
              {fromRace}R〜成績
            </Button>
          </React.Fragment>
        ))}
      </div>
      {status && <span className="text-xs text-muted-foreground">{status}</span>}
    </div>
  );
}
