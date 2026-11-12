'use client';

import React from 'react';
import { ExternalLink } from 'lucide-react';
import { PaperMath } from './PaperMath';
import { safePaperLink } from '../../lib/paperPresentation';

export interface HeadingItem {
  title: string;
  level: number;
  slug: string;
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)+/g, '');
}

export function extractHeadings(markdown: string): HeadingItem[] {
  if (!markdown) return [];
  const headings: HeadingItem[] = [];
  const lines = markdown.split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('# ')) {
      const title = trimmed.slice(2).replace(/\*\*/g, '').trim();
      if (title) headings.push({ title, level: 1, slug: slugify(title) });
    } else if (trimmed.startsWith('## ')) {
      const title = trimmed.slice(3).replace(/\*\*/g, '').trim();
      if (title) headings.push({ title, level: 2, slug: slugify(title) });
    } else if (trimmed.startsWith('### ')) {
      const title = trimmed.slice(4).replace(/\*\*/g, '').trim();
      if (title) headings.push({ title, level: 3, slug: slugify(title) });
    }
  }
  return headings;
}

export interface MarkdownViewerProps {
  content: string;
  onCitationClick?: (citationRef: string) => void;
  className?: string;
  academicStyle?: boolean;
}

function renderInline(text: string, onCitationClick?: (citationRef: string) => void): React.ReactNode[] {
  // Regex to match inline elements: bold, italic, code, markdown link, and citation references like [1] or [src_01]
  const regex = /(`[^`]+`|(?<!\\)\$(?!\s)[^$\n]+(?<!\s)\$(?!\d)|\\\([^\n]*?\\\)|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\)|\[\d+\]|\[src_\d+\])/g;
  const parts = text.split(regex);

  return parts.map((part, index) => {
    if (!part) return null;

    if (part.startsWith('$') && part.endsWith('$')) return <PaperMath key={index} source={part.slice(1, -1)} />;
    if (part.startsWith('\\(') && part.endsWith('\\)')) return <PaperMath key={index} source={part.slice(2, -2)} />;

    // Bold: **text**
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index} className="font-semibold text-zinc-950">{part.slice(2, -2)}</strong>;
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
          className="inline-flex items-center align-baseline px-1.5 py-0.5 mx-0.5 text-xs font-semibold rounded bg-zinc-100 text-zinc-800 border border-zinc-200/90 hover:bg-zinc-200 transition-colors cursor-pointer hover:shadow-2xs"
          title={`Citation [${label}]`}
        >
          [{label}]
        </button>
      );
    }

    // Link: [label](url)
    const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (linkMatch) {
      const [, label, href] = linkMatch;
      const safeHref = safePaperLink(href);
      if (!safeHref) return <span key={index}>{label}</span>;
      return (
        <a
          key={index}
          href={safeHref}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:underline inline-flex items-center gap-0.5 font-medium"
        >
          {label}
          <ExternalLink size={11} className="inline ml-0.5 opacity-70" />
        </a>
      );
    }

    return <span key={index}>{part.replace(/\\\$/g, '$')}</span>;
  });
}

export function MarkdownViewer({ content, onCitationClick, className = '', academicStyle = true }: MarkdownViewerProps) {
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
        <li key={idx} className="text-zinc-800 leading-relaxed text-[15px] md:text-[16px]">
          {renderInline(item, onCitationClick)}
        </li>
      ));
      if (inList === 'ul') {
        elements.push(
          <ul key={`ul-${elements.length}`} className="list-disc list-outside pl-6 my-4 space-y-2 text-zinc-800">
            {items}
          </ul>
        );
      } else {
        elements.push(
          <ol key={`ol-${elements.length}`} className="list-decimal list-outside pl-6 my-4 space-y-2 text-zinc-800">
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
        <div key={`table-${elements.length}`} className="overflow-x-auto my-6 border border-zinc-200 rounded-xl bg-white shadow-sm">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-zinc-50/80 border-b-2 border-zinc-300">
                {headerRow.map((cell, cIdx) => (
                  <th key={cIdx} className="px-4 py-3 font-semibold text-zinc-950 border-r border-zinc-200 last:border-r-0">
                    {renderInline(cell.trim(), onCitationClick)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200">
              {bodyRows.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-zinc-50/60 transition-colors">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="px-4 py-2.5 text-zinc-800 border-r border-zinc-200 last:border-r-0">
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
          <pre key={`code-${elements.length}`} className="bg-zinc-900 text-zinc-100 p-4 sm:p-5 rounded-xl text-xs sm:text-sm font-mono overflow-x-auto my-5 leading-relaxed shadow-sm">
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

    // Consume only a closed math block. Unclosed delimiters remain visible text.
    const delimiter = line.startsWith('$$') ? '$$' : line.startsWith('\\[') ? '\\[' : null;
    if (delimiter) {
      const endDelimiter = delimiter === '$$' ? '$$' : '\\]';
      const rest = line.slice(2);
      let end = i;
      let formula: string | null = rest.endsWith(endDelimiter) && rest.length >= 2 ? rest.slice(0, -2) : null;
      if (formula === null) {
        for (let j = i + 1; j < lines.length; j++) {
          if (lines[j].trim().startsWith('```')) break;
          if (lines[j].trim().endsWith(endDelimiter)) {
            formula = [rest, ...lines.slice(i + 1, j), lines[j].trim().slice(0, -2)].join('\n');
            end = j; break;
          }
        }
      }
      if (formula !== null) {
        flushList(); flushTable();
        elements.push(<PaperMath key={`math-${elements.length}`} source={formula} display />);
        i = end; continue;
      }
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
      const text = line.slice(2).trim();
      const slug = slugify(text);
      elements.push(
        <h1
          id={slug}
          key={`h1-${elements.length}`}
          className="text-2xl sm:text-3xl font-bold tracking-tight text-zinc-950 mt-10 mb-4 pb-3 border-b border-zinc-200/90 scroll-mt-24 font-sans"
        >
          {renderInline(text, onCitationClick)}
        </h1>
      );
      continue;
    }
    if (line.startsWith('## ')) {
      flushList();
      const text = line.slice(3).trim();
      const slug = slugify(text);
      elements.push(
        <h2
          id={slug}
          key={`h2-${elements.length}`}
          className="text-xl sm:text-2xl font-bold tracking-tight text-zinc-900 mt-8 mb-3.5 pb-1 border-b border-zinc-100 scroll-mt-24 font-sans"
        >
          {renderInline(text, onCitationClick)}
        </h2>
      );
      continue;
    }
    if (line.startsWith('### ')) {
      flushList();
      const text = line.slice(4).trim();
      const slug = slugify(text);
      elements.push(
        <h3
          id={slug}
          key={`h3-${elements.length}`}
          className="text-lg sm:text-xl font-semibold tracking-tight text-zinc-900 mt-6 mb-2.5 scroll-mt-24 font-sans"
        >
          {renderInline(text, onCitationClick)}
        </h3>
      );
      continue;
    }
    if (line.startsWith('#### ')) {
      flushList();
      const text = line.slice(5).trim();
      const slug = slugify(text);
      elements.push(
        <h4
          id={slug}
          key={`h4-${elements.length}`}
          className="text-base font-semibold text-zinc-800 mt-5 mb-2 scroll-mt-24"
        >
          {renderInline(text, onCitationClick)}
        </h4>
      );
      continue;
    }

    // Horizontal rule
    if (line === '---' || line === '***' || line === '___') {
      flushList();
      elements.push(<hr key={`hr-${elements.length}`} className="my-8 border-zinc-200" />);
      continue;
    }

    // Blockquote
    if (line.startsWith('> ')) {
      flushList();
      elements.push(
        <blockquote key={`bq-${elements.length}`} className="border-l-4 border-zinc-700 bg-zinc-50/90 pl-5 py-3 my-4 rounded-r-xl text-zinc-750 font-normal shadow-2xs">
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
      <p key={`p-${elements.length}`} className="text-[15px] sm:text-[16px] leading-[1.75] text-zinc-800 my-4 text-left font-normal">
        {renderInline(line, onCitationClick)}
      </p>
    );
  }

  flushList();
  flushTable();

  return (
    <article className={`prose prose-zinc max-w-none ${className}`}>
      {elements}
    </article>
  );
}
