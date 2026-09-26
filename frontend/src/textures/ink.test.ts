import { describe, expect, it } from 'vitest';
import { boxTile, inkTextures, ruleTile } from './ink';

describe('ink textures', () => {
  it('draws the same wear on every build', () => {
    expect(inkTextures()).toEqual(inkTextures());
  });

  it('wears each seed differently', () => {
    expect(ruleTile(7)).not.toEqual(ruleTile(23));
  });

  it('cuts the wear out of the ink rather than painting over it', () => {
    for (const svg of Object.values(inkTextures())) {
      expect(svg).toMatch(/^<svg [^>]*>.*<\/svg>$/);
      expect(svg).toContain('mask="url(#wear)"');
      // The only white is the mask's keep layer; nothing is painted white on the page.
      expect(svg.replace(/<mask .*?<\/mask>/, '')).not.toContain('#fff');
    }
  });

  it('inks the warn box in a different colour from the plain one', () => {
    expect(boxTile(11)).not.toEqual(boxTile(11, '#86621a'));
    expect(boxTile(11, '#86621a')).toContain('stroke="#86621a"');
  });
});
