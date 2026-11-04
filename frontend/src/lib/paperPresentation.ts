/** Preview-only transformations; persisted/exported manuscript text stays unchanged. */
export function withoutRepeatedTitle(markdown: string, title: string): string {
  const match = markdown.match(/^\s*#\s+([^\n]+)\r?\n?/);
  const normalize = (text: string) => text.replace(/\*\*/g, '').trim().normalize('NFC');
  return match && normalize(match[1]) === normalize(title)
    ? markdown.slice(match[0].length).replace(/^\s*\n/, '') : markdown;
}

export function safePaperLink(href: string): string | null {
  if (/^#[a-zA-Z0-9_-]+$/.test(href)) return href;
  try {
    const url = new URL(href);
    return ['https:', 'http:'].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}
