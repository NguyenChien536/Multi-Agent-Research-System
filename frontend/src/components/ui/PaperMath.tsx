import katex from 'katex';

/** Only KaTeX-generated markup is inserted; model HTML is never trusted. */
export function PaperMath({ source, display = false }: { source: string; display?: boolean }) {
  if (source.length > 4096) return <code className="break-all">{source}</code>;
  const html = katex.renderToString(source, {
    displayMode: display, output: 'htmlAndMathml', trust: false,
    throwOnError: false, strict: 'ignore', maxExpand: 1000, maxSize: 20,
    macros: {},
  });
  return <span className={display ? 'block overflow-x-auto my-5 max-w-full' : 'inline-math'}
    dangerouslySetInnerHTML={{ __html: html }} />;
}
