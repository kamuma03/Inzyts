import { describe, it, expect } from 'vitest';
import { formatCost, formatTokens, formatBytes, formatDelta } from './formatters';

describe('formatCost', () => {
    it('handles null/NaN', () => {
        expect(formatCost(null)).toBe('—');
        expect(formatCost(undefined)).toBe('—');
        expect(formatCost(NaN)).toBe('—');
    });
    it('formats zero', () => {
        expect(formatCost(0)).toBe('$0');
    });
    it('uses 4 decimals under $0.01', () => {
        expect(formatCost(0.0042)).toBe('$0.0042');
    });
    it('uses 2 decimals under $100', () => {
        expect(formatCost(12.5)).toBe('$12.50');
    });
    it('uses integer over $100', () => {
        expect(formatCost(1234.5)).toBe('$1,235');
    });
});

describe('formatTokens', () => {
    it('formats small counts', () => {
        expect(formatTokens(42)).toBe('42');
    });
    it('formats thousands', () => {
        expect(formatTokens(1500)).toBe('1.5K');
    });
    it('formats millions', () => {
        expect(formatTokens(2_300_000)).toBe('2.3M');
    });
});

describe('formatBytes', () => {
    it('formats bytes', () => {
        expect(formatBytes(512)).toBe('512 B');
    });
    it('formats KB', () => {
        expect(formatBytes(1024)).toBe('1.0 KB');
    });
    it('formats MB', () => {
        expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB');
    });
});

describe('formatDelta', () => {
    it('returns "none" direction when either value is null', () => {
        const r = formatDelta(null, 100);
        expect(r.direction).toBe('none');
        expect(r.label).toBe('—');
    });
    it('marks lower as better when lowerIsBetter', () => {
        const r = formatDelta(80, 100, { lowerIsBetter: true, formatter: (n) => `${n}` });
        expect(r.direction).toBe('better');
        expect(r.label).toBe('−20');
    });
    it('marks higher as worse when lowerIsBetter', () => {
        const r = formatDelta(120, 100, { lowerIsBetter: true, formatter: (n) => `${n}` });
        expect(r.direction).toBe('worse');
        expect(r.label).toBe('+20');
    });
    it('inverts direction when lowerIsBetter is false', () => {
        const r = formatDelta(0.95, 0.85, { lowerIsBetter: false, formatter: (n) => n.toFixed(2) });
        expect(r.direction).toBe('better');
    });
    it('returns same direction for equal values', () => {
        const r = formatDelta(10, 10);
        expect(r.direction).toBe('same');
    });
});
