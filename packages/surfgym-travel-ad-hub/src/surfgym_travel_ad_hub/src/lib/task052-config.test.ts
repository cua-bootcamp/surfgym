import { describe, expect, it } from 'vitest';

import { isTask052AdEnabled } from './task052-config';

describe('isTask052AdEnabled', () => {
  it.each([
    [undefined, false],
    ['', false],
    ['false', false],
    ['true', true],
    ['TRUE', true],
  ])('maps %s to %s', (value, expected) => {
    expect(isTask052AdEnabled(value)).toBe(expected);
  });
});
