'use client';

import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';

// Mermaidの初期化設定
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
  fontFamily: 'inherit',
});

interface MermaidRendererProps {
  chart: string;
  id?: string;
}

/**
 * Mermaid図をレンダリングするコンポーネント
 */
export function MermaidRenderer({ chart, id }: MermaidRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const renderChart = async () => {
      if (!containerRef.current || !chart.trim()) return;

      try {
        const uniqueId = id || `mermaid-${Math.random().toString(36).substr(2, 9)}`;
        const { svg } = await mermaid.render(uniqueId, chart);
        setSvg(svg);
        setError(null);
      } catch (err) {
        console.error('Mermaid rendering error:', err);
        setError('図の描画に失敗しました');
      }
    };

    renderChart();
  }, [chart, id]);

  if (error) {
    return (
      <div className="p-4 border border-red-500 rounded bg-red-500/10 text-red-400">
        <p className="font-bold">⚠️ {error}</p>
        <pre className="mt-2 text-xs overflow-auto">{chart}</pre>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="mermaid-container my-4 p-4 bg-slate-800/50 rounded-lg overflow-auto"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

/**
 * HTMLコンテンツ内のMermaidコードブロックをレンダリングするコンポーネント
 */
interface MermaidContentProps {
  htmlContent: string;
}

export function MermaidContent({ htmlContent }: MermaidContentProps) {
  const [processedContent, setProcessedContent] = useState<React.ReactNode[]>([]);

  useEffect(() => {
    // Mermaidコードブロックを検出して分割
    // <pre><code class="language-mermaid">...</code></pre> または
    // <pre>graph ... </pre> のパターンを検出
    const mermaidRegex = /<pre[^>]*>(?:<code[^>]*class="[^"]*language-mermaid[^"]*"[^>]*>)?([\s\S]*?)(?:<\/code>)?<\/pre>/gi;
    
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;
    let key = 0;

    while ((match = mermaidRegex.exec(htmlContent)) !== null) {
      const code = match[1].trim();
      
      // Mermaidコードかどうかをチェック（graph, flowchart, sequenceDiagram, etc.）
      const isMermaid = /^(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|journey|gantt|pie|gitGraph|mindmap|timeline|quadrantChart|xychart|block)/i.test(code);
      
      if (isMermaid) {
        // マッチ前のHTMLを追加
        if (match.index > lastIndex) {
          parts.push(
            <div
              key={`html-${key++}`}
              dangerouslySetInnerHTML={{ __html: htmlContent.slice(lastIndex, match.index) }}
            />
          );
        }
        
        // Mermaid図を追加
        parts.push(<MermaidRenderer key={`mermaid-${key++}`} chart={code} />);
        
        lastIndex = match.index + match[0].length;
      }
    }

    // 残りのHTMLを追加
    if (lastIndex < htmlContent.length) {
      parts.push(
        <div
          key={`html-${key++}`}
          dangerouslySetInnerHTML={{ __html: htmlContent.slice(lastIndex) }}
        />
      );
    }

    // Mermaidが見つからなかった場合は元のHTMLをそのまま使用
    if (parts.length === 0) {
      parts.push(
        <div key="html-0" dangerouslySetInnerHTML={{ __html: htmlContent }} />
      );
    }

    setProcessedContent(parts);
  }, [htmlContent]);

  return <>{processedContent}</>;
}
