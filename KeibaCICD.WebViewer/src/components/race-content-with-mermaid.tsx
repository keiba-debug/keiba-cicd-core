'use client';

import React, { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

// Mermaidの初期化設定
let mermaidInitialized = false;

interface RaceContentWithMermaidProps {
  htmlContent: string;
}

/**
 * Mermaidコードを安全にサニタイズ
 * 日本語の括弧などMermaid構文と競合する文字をエスケープ
 */
function sanitizeMermaidCode(code: string): string {
  // ノード内のテキストで問題になる文字をエスケープ
  // [テキスト] 形式のノード内の括弧をエスケープ
  return code.replace(/\[([^\]]*)\]/g, (match, content) => {
    // 括弧を全角に変換
    const sanitized = content
      .replace(/\(/g, '（')
      .replace(/\)/g, '）');
    return `[${sanitized}]`;
  });
}

/**
 * レースコンテンツをMermaid対応で表示するコンポーネント
 */
export function RaceContentWithMermaid({ htmlContent }: RaceContentWithMermaidProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Mermaidを初期化（1回のみ）
    if (!mermaidInitialized) {
      mermaid.initialize({
        startOnLoad: false,
        theme: 'dark',
        securityLevel: 'loose',
        fontFamily: 'inherit',
        flowchart: {
          useMaxWidth: true,
          htmlLabels: true,
        },
      });
      mermaidInitialized = true;
    }

    const renderMermaid = async () => {
      if (!containerRef.current) return;

      // preタグ内のMermaidコードを検出
      const preElements = containerRef.current.querySelectorAll('pre');
      
      for (const pre of Array.from(preElements)) {
        const rawCode = pre.textContent?.trim() || '';
        
        // Mermaidコードかどうかをチェック（より厳密に）
        const mermaidKeywords = /^(graph\s+(LR|RL|TD|TB|BT)|flowchart\s+(LR|RL|TD|TB|BT)|sequenceDiagram|classDiagram|stateDiagram|erDiagram|journey|gantt|pie|gitGraph|mindmap|timeline)/i;
        const isMermaid = mermaidKeywords.test(rawCode);
        
        if (isMermaid) {
          try {
            // コードをサニタイズ
            const code = sanitizeMermaidCode(rawCode);
            const uniqueId = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
            
            // Mermaidの構文チェック
            const isValid = await mermaid.parse(code).catch(() => false);
            
            if (isValid) {
              const { svg } = await mermaid.render(uniqueId, code);
              
              // preタグをMermaid SVGで置換
              const wrapper = document.createElement('div');
              wrapper.className = 'mermaid-container my-4 p-4 bg-slate-700/30 rounded-lg overflow-auto border border-slate-600';
              wrapper.innerHTML = svg;
              pre.replaceWith(wrapper);
            } else {
              // 無効な場合はそのまま表示（スタイルのみ追加）
              console.warn('Invalid Mermaid syntax, displaying as code block');
            }
          } catch (err) {
            // エラーの場合は元のpreタグをそのまま表示
            console.warn('Mermaid rendering skipped:', err);
          }
        }
      }
    };

    // DOMが更新された後にMermaidをレンダリング
    const timer = setTimeout(renderMermaid, 100);
    return () => clearTimeout(timer);
  }, [htmlContent]);

  return (
    <article
      ref={containerRef}
      className="prose prose-neutral dark:prose-invert max-w-none 
                 prose-headings:scroll-mt-20 
                 prose-table:w-full prose-table:text-sm
                 prose-th:bg-muted prose-th:text-left prose-th:p-2
                 prose-td:p-2 prose-td:border
                 prose-a:text-primary prose-a:no-underline hover:prose-a:underline"
      dangerouslySetInnerHTML={{ __html: htmlContent }}
    />
  );
}
