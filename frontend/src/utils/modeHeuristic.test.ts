import { describe, it, expect } from 'vitest';
import { suggestMode } from './modeHeuristic';

describe('suggestMode', () => {
    const noCtx = { hasDatetime: false, hasTargetCol: false };
    const tsCtx = { hasDatetime: true, hasTargetCol: false };
    const targetCtx = { hasDatetime: false, hasTargetCol: true };

    it('returns null for empty/short input', () => {
        expect(suggestMode('', noCtx)).toBeNull();
        expect(suggestMode('hi', noCtx)).toBeNull();
        expect(suggestMode('shortq', noCtx)).toBeNull();
    });

    it('returns null when nothing matches', () => {
        expect(suggestMode('this is just a sentence', noCtx)).toBeNull();
    });

    it('detects forecasting from "forecast next quarter"', () => {
        const r = suggestMode("Forecast next quarter's revenue", tsCtx);
        expect(r?.mode).toBe('forecasting');
        expect(r?.matched_keywords).toEqual(
            expect.arrayContaining(['forecast', 'next quarter']),
        );
        expect(r?.confidence).toBeGreaterThanOrEqual(0.7);
    });

    it('biases toward predictive when target col is set', () => {
        const r = suggestMode('predict customer churn', targetCtx);
        expect(r?.mode).toBe('predictive');
        expect(r?.matched_keywords).toEqual(expect.arrayContaining(['predict', 'churn']));
    });

    it('detects comparative from "compare control vs variant"', () => {
        const r = suggestMode('compare control vs variant performance', noCtx);
        expect(r?.mode).toBe('comparative');
    });

    it('detects diagnostic from "why did sales drop"', () => {
        const r = suggestMode('why did sales drop last month and what caused it', noCtx);
        expect(r?.mode).toBe('diagnostic');
    });

    it('detects segmentation from clustering language', () => {
        const r = suggestMode('cluster customers into segments', noCtx);
        expect(r?.mode).toBe('segmentation');
    });

    it('detects dimensionality reduction from PCA', () => {
        const r = suggestMode('run pca to reduce dimension count', noCtx);
        expect(r?.mode).toBe('dimensionality_reduction');
    });

    it('detects exploratory from "describe the dataset"', () => {
        const r = suggestMode('describe the dataset and profile its columns', noCtx);
        expect(r?.mode).toBe('exploratory');
    });

    it('exploration explanation includes datetime ctx note', () => {
        const r = suggestMode('forecast revenue next quarter', tsCtx);
        expect(r?.explanation).toContain('datetime column');
    });

    it('predictive explanation includes target col note', () => {
        const r = suggestMode('predict the likelihood of churn', targetCtx);
        expect(r?.explanation).toContain('target column');
    });

    it('confidence stays in [0,1]', () => {
        const r = suggestMode('forecast next quarter next year next month trend', tsCtx);
        expect(r?.confidence).toBeLessThanOrEqual(1);
        expect(r?.confidence).toBeGreaterThan(0);
    });

    it('respects MIN_CONFIDENCE threshold', () => {
        // Single weak hit should fall under the 0.4 threshold and return null.
        const r = suggestMode('what should we estimate today', noCtx);
        // 'estimate' is one weak hit, score = 0.35, below 0.4 → null
        expect(r).toBeNull();
    });

    it('runs in <50ms for 1000 calls (perf smoke)', () => {
        const start = performance.now();
        for (let i = 0; i < 1000; i++) {
            suggestMode('forecast next quarter revenue', { hasDatetime: true, hasTargetCol: false });
        }
        expect(performance.now() - start).toBeLessThan(50);
    });
});
