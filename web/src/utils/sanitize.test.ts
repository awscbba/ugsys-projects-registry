import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { escapeHtml, stripHtml } from './sanitize';

// ── Unit tests ────────────────────────────────────────────────────────────────

describe('escapeHtml', () => {
  it('escapes < and >', () => {
    expect(escapeHtml('<script>')).toBe('&lt;script&gt;');
  });

  it('escapes &', () => {
    expect(escapeHtml('a & b')).toBe('a &amp; b');
  });

  it('escapes double quotes', () => {
    expect(escapeHtml('"hello"')).toBe('&quot;hello&quot;');
  });

  it('escapes single quotes', () => {
    expect(escapeHtml("it's")).toBe('it&#039;s');
  });

  it('returns plain text unchanged', () => {
    expect(escapeHtml('hello world')).toBe('hello world');
  });
});

describe('stripHtml', () => {
  it('removes HTML tags', () => {
    expect(stripHtml('<p>hello</p>')).toBe('hello');
  });

  it('returns plain text unchanged', () => {
    expect(stripHtml('no tags')).toBe('no tags');
  });

  it('removes nested tags', () => {
    expect(stripHtml('<div><span>text</span></div>')).toBe('text');
  });
});

// ── Property tests ────────────────────────────────────────────────────────────

// Feature: web-frontend-quality, Property 6: escapeHtml character escaping
describe('Property 6: escapeHtml escapes all special HTML characters', () => {
  it('replaces < with &lt;', () => {
    fc.assert(
      fc.property(fc.string(), (prefix) => {
        const result = escapeHtml(prefix + '<');
        expect(result).not.toContain('<');
        expect(result).toContain('&lt;');
      }),
      { numRuns: 100 }
    );
  });

  it('replaces > with &gt;', () => {
    fc.assert(
      fc.property(fc.string(), (prefix) => {
        const result = escapeHtml(prefix + '>');
        expect(result).not.toContain('>');
        expect(result).toContain('&gt;');
      }),
      { numRuns: 100 }
    );
  });

  it('replaces & with &amp;', () => {
    fc.assert(
      fc.property(fc.string(), (prefix) => {
        // Use a string that won't already contain & from escaping
        const input = prefix.replace(/&/g, '') + '&';
        const result = escapeHtml(input);
        // The result should contain &amp; (from our & replacement)
        expect(result).toContain('&amp;');
      }),
      { numRuns: 100 }
    );
  });
});

// Feature: web-frontend-quality, Property 7: escapeHtml output contains no raw special HTML chars
describe('Property 7: escapeHtml output contains no raw unescaped HTML special characters', () => {
  it('result of escapeHtml contains no raw < > " or single-quote chars', () => {
    fc.assert(
      fc.property(fc.string(), (s) => {
        const result = escapeHtml(s);
        // After escaping, none of the raw special chars should remain
        // (& is allowed because it's part of the entity encoding itself)
        expect(result).not.toMatch(/[<>"']/);
      }),
      { numRuns: 100 }
    );
  });
});

// Feature: web-frontend-quality, Property 8: stripHtml tag removal
describe('Property 8: stripHtml removes all HTML tags', () => {
  it('result contains no substrings matching /<[^>]*>/ for any string', () => {
    fc.assert(
      fc.property(fc.string(), (s) => {
        const result = stripHtml(s);
        expect(result).not.toMatch(/<[^>]*>/);
      }),
      { numRuns: 100 }
    );
  });
});
