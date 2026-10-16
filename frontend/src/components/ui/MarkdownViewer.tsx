'use client';

import React from 'react';
import { ExternalLink } from 'lucide-react';

interface MarkdownViewerProps {
  content: string;
  onCitationClick?: (citationRef: string) => void;
  className?: string;
}

function renderInline(text: string, onCitationClick?: (citationRef: string) => void): React.ReactNode[] {
  // Regex to match inline elements: bold, italic, code, markdown link, and citation references like [1] or [src_01]
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|\[\d+\]|\[src_\d+\])/g;
  const parts = text.split(regex);

  return parts.map((part, index) => {
    if (!part) return null;

    // Bold: **text**
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index} className="font-semibold text-zinc-900">{part.slice(2, -2)}</strong>;
    }

    // Italic: *text*
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={index} className="italic text-zinc-800">{part.slice(1, -1)}</em>;
    }

    // Inline code: `code`
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={index} className="px-1.5 py-0.5 mx-0.5 rounded bg-zinc-100 text-zinc-800 text-xs font-mono border border-zinc-200">
          {part.slice(1, -1)}
        </code>
      );
    }

    // Citation badge: [1], [2], [src_01]
    const citationMatch = part.match(/^\[(\d+|src_\d+)\]$/);
    if (citationMatch) {
      const label = citationMatch[1];
      return (
        <button
          key={index}
          type="button"
          onClick={() => onCitationClick?.(label)}
          className="inline-flex items-center align-baseline px-1.5 py-0.2 mx-0.5 text-xs font-semibold rounded bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition-colors cursor-pointer"
          title={`Xem trích dẫn [${label}]`}
        >
          [{label}]
        </button>
      );
    }

    // Link: [label](url)
    const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (linkMatch) {
      const [, label, href] = linkMatch;
      return (
        <a
          key={index}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:underline inline-flex items-center gap-0.5 font-medium"
        >
          {label}
          <ExternalLink size={11} className="inline ml-0.5 opacity-70" />
        </a>
      );
    }

    return <span key={index}>{part}</span>;
  });
}

export function MarkdownViewer({ content, onCitationClick, className = '' }: MarkdownViewerProps) {
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];

  let inCodeBlock = false;
  let codeBlockContent: string[] = [];
  let inList: 'ul' | 'ol' | null = null;
  let listItems: string[] = [];
  let inTable = false;
  let tableRows: string[][] = [];

  const flushList = () => {
    if (inList && listItems.length > 0) {
      const items = listItems.map((item, idx) => (
        <li key={idx} className="text-zinc-700 leading-relaxed">
          {renderInline(item, onCitationClick)}
        </li>
      ));
      if (inList === 'ul') {
        elements.push(
          <ul key={`ul-${elements.length}`} className="list-disc list-outside pl-6 my-3 space-y-1.5">
            {items}
          </ul>
        );
      } else {
        elements.push(
          <ol key={`ol-${elements.length}`} className="list-decimal list-outside pl-6 my-3 space-y-1.5">
            {items}
          </ol>
        );
      }
      inList = null;
      listItems = [];
    }
  };

  const flushTable = () => {
    if (inTable && tableRows.length > 0) {
      const headerRow = tableRows[0];
      const bodyRows = tableRows.slice(1);
      elements.push(
        <div key={`table-${elements.length}`} className="overflow-x-auto my-4 border border-zinc-200 rounded-xl">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-zinc-50 border-b border-zinc-200">
                {headerRow.map((cell, cIdx) => (
                  <th key={cIdx} className="px-4 py-2.5 font-semibold text-zinc-900 border-r border-zinc-200 last:border-r-0">
                    {renderInline(cell.trim(), onCitationClick)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200">
              {bodyRows.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-zinc-50/50">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="px-4 py-2 text-zinc-700 border-r border-zinc-200 last:border-r-0">
                      {renderInline(cell.trim(), onCitationClick)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      inTable = false;
      tableRows = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const line = rawLine.trim();

    // Code block toggle
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        elements.push(
          <pre key={`code-${elements.length}`} className="bg-zinc-900 text-zinc-100 p-4 rounded-xl text-xs font-mono overflow-x-auto my-4 leading-relaxed">
            <code>{codeBlockContent.join('\n')}</code>
          </pre>
        );
        inCodeBlock = false;
        codeBlockContent = [];
      } else {
        flushList();
        flushTable();
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeBlockContent.push(rawLine);
      continue;
    }

    // Markdown Table row: | cell | cell |
    if (line.startsWith('|') && line.endsWith('|')) {
      flushList();
      // Skip separator rows like |---|---|
      if (/^\|[-|\s]+\|$/.test(line)) {
        continue;
      }
      const cells = line.slice(1, -1).split('|');
      inTable = true;
      tableRows.push(cells);
      continue;
    } else if (inTable) {
      flushTable();
    }

    // Headings
    if (line.startsWith('# ')) {
      flushList();
      elements.push(
        <h1 key={`h1-${elements.length}`} className="text-2xl md:text-3xl font-bold tracking-tight text-zinc-900 mt-8 mb-4 pb-2 border-b border-zinc-200">
          {renderInline(line.slice(2), onCitationClick)}
        </h1>
      );
      continue;
    }
    if (line.startsWith('## ')) {
      flushList();
      elements.push(
        <h2 key={`h2-${elements.length}`} className="text-xl md:text-2xl font-bold tracking-tight text-zinc-850 mt-6 mb-3">
          {renderInline(line.slice(3), onCitationClick)}
        </h2>
      );
      continue;
    }
    if (line.startsWith('### ')) {
      flushList();
      elements.push(
        <h3 key={`h3-${elements.length}`} className="text-lg md:text-xl font-semibold text-zinc-800 mt-5 mb-2">
          {renderInline(line.slice(4), onCitationClick)}
        </h3>
      );
      continue;
    }
    if (line.startsWith('#### ')) {
      flushList();
      elements.push(
        <h4 key={`h4-${elements.length}`} className="text-base font-semibold text-zinc-800 mt-4 mb-2">
          {renderInline(line.slice(5), onCitationClick)}
        </h4>
      );
      continue;
    }

    // Horizontal rule
    if (line === '---' || line === '***' || line === '___') {
      flushList();
      elements.push(<hr key={`hr-${elements.length}`} className="my-6 border-zinc-200" />);
      continue;
    }

    // Blockquote
    if (line.startsWith('> ')) {
      flushList();
      elements.push(
        <blockquote key={`bq-${elements.length}`} className="border-l-4 border-blue-500 bg-blue-50/40 pl-4 py-2 my-3 rounded-r-lg text-zinc-700 italic">
          {renderInline(line.slice(2), onCitationClick)}
        </blockquote>
      );
      continue;
    }

    // Unordered List
    if (line.startsWith('- ') || line.startsWith('* ')) {
      if (inList !== 'ul') flushList();
      inList = 'ul';
      listItems.push(line.slice(2));
      continue;
    }

    // Ordered List
    const olMatch = line.match(/^(\d+)\.\s+(.*)$/);
    if (olMatch) {
      if (inList !== 'ol') flushList();
      inList = 'ol';
      listItems.push(olMatch[2]);
      continue;
    }

    // Empty lines flush lists
    if (!line) {
      flushList();
      continue;
    }

    // Standard Paragraph
    flushList();
    elements.push(
      <p key={`p-${elements.length}`} className="text-sm md:text-base leading-7 text-zinc-700 my-2.5">
        {renderInline(line, onCitationClick)}
      </p>
    );
  }

  flushList();
  flushTable();

  return (
    <article className={`prose prose-zinc max-w-none font-sans ${className}`}>
      {elements}
    </article>
  );
}
