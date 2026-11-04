const MARKER = /\[(\d+(?:\s*,\s*\d+)*)\]/g;

/**
 * Turns answer text into paragraphs of segments.
 * Segment: { type: 'text', value } or { type: 'cite', ids: number[], raw }.
 * Nothing is ever interpreted as HTML.
 */
export function parseAnswer(text) {
  return text.split(/\n{2,}/).map((paragraph) => {
    const segments = [];
    let last = 0;
    for (const match of paragraph.matchAll(MARKER)) {
      if (match.index > last) segments.push({ type: 'text', value: paragraph.slice(last, match.index) });
      segments.push({
        type: 'cite',
        ids: match[1].split(',').map((n) => Number(n.trim())),
        raw: match[0],
      });
      last = match.index + match[0].length;
    }
    if (last < paragraph.length) segments.push({ type: 'text', value: paragraph.slice(last) });
    return segments;
  });
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Locates `highlight` inside `snippet`, tolerating whitespace and case differences. */
export function locateHighlight(snippet, highlight) {
  if (!highlight) return null;
  const exact = snippet.indexOf(highlight);
  if (exact >= 0) return { start: exact, end: exact + highlight.length };
  const pattern = highlight.trim().split(/\s+/).map(escapeRegExp).join('\\s+');
  if (!pattern) return null;
  const found = new RegExp(pattern, 'i').exec(snippet);
  return found ? { start: found.index, end: found.index + found[0].length } : null;
}

export const EXCERPT_LIMIT = 360;
const CONTEXT = 110;

/**
 * Returns the part of the passage to show while collapsed, centred on the
 * highlight so the supporting sentence is always visible.
 */
export function excerptAround(snippet, range) {
  if (snippet.length <= EXCERPT_LIMIT) {
    return { text: snippet, offset: 0, before: false, after: false };
  }
  const anchorStart = range ? range.start : 0;
  const anchorEnd = range ? range.end : Math.min(snippet.length, EXCERPT_LIMIT);
  let start = Math.max(0, anchorStart - CONTEXT);
  let end = Math.min(snippet.length, anchorEnd + CONTEXT);
  if (start > 0) {
    const space = snippet.indexOf(' ', start);
    if (space >= 0 && space < anchorStart) start = space + 1;
  }
  if (end < snippet.length) {
    const space = snippet.lastIndexOf(' ', end);
    if (space > anchorEnd) end = space;
  }
  return { text: snippet.slice(start, end), offset: start, before: start > 0, after: end < snippet.length };
}
