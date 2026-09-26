import { afterEach, describe, expect, it } from 'vitest';
import { linkedNames, render, renderInline, setLinkResolver } from './markdown';

afterEach(() => setLinkResolver(null));

describe('linkedNames', () => {
  it('finds every [[name]] in a blob of text', () => {
    expect(linkedNames('[[Cerys]] told [[Pedr]] about the gate.')).toEqual(['Cerys', 'Pedr']);
  });

  it('trims, and ignores empty brackets', () => {
    expect(linkedNames('[[ Dilwen ]] and [[]]')).toEqual(['Dilwen']);
  });

  it('is happy with no links at all', () => {
    expect(linkedNames('')).toEqual([]);
    expect(linkedNames(undefined)).toEqual([]);
  });
});

describe('rendering a link', () => {
  it('links a name the table knows', () => {
    setLinkResolver((name) => (name === 'Cerys' ? { href: '#/n/abc', title: 'Record' } : null));
    expect(renderInline('Ask [[Cerys]].')).toBe('Ask <a class="entity" href="#/n/abc" title="Record">Cerys</a>.');
  });

  it('leaves a name it cannot resolve as plain text', () => {
    // Which is also what a player sees for a record the GM has hidden: the
    // mention must not advertise that someone exists.
    setLinkResolver(() => null);
    expect(renderInline('Ask [[Brennan]].')).toBe('Ask Brennan.');
  });

  it('escapes what it renders, resolved or not', () => {
    setLinkResolver((name) => (name === '<b>' ? { href: '#/n/x"y', title: 'Record' } : null));
    expect(renderInline('[[<script>]]')).toBe('&lt;script&gt;');
    expect(renderInline('[[<b>]]')).toContain('href="#/n/x&quot;y"');
    expect(renderInline('[[<b>]]')).toContain('&lt;b&gt;</a>');
  });

  it('works inside block markdown too', () => {
    setLinkResolver(() => ({ href: '#/n/abc', title: 'Record' }));
    expect(render('- saw [[Cerys]]')).toBe('<ul><li>saw <a class="entity" href="#/n/abc" title="Record">Cerys</a></li></ul>');
  });

  it('does not disturb ordinary emphasis', () => {
    setLinkResolver(() => null);
    expect(renderInline('**bold** and *thin*')).toBe('<strong>bold</strong> and <em>thin</em>');
  });
});
