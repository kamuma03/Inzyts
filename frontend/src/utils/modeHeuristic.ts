import type { AnalysisRequest } from '../api';

export type Mode = NonNullable<AnalysisRequest['mode']>;

export interface SuggestionResult {
    mode: Mode;
    confidence: number;
    matched_keywords: string[];
    explanation: string;
}

export interface SuggestionContext {
    hasDatetime: boolean;
    hasTargetCol: boolean;
}

const KEYWORDS: Record<Mode, string[]> = {
    forecasting: [
        'forecast', 'predict next', 'next quarter', 'next year', 'next month',
        'project', 'future', 'time series', 'trend',
    ],
    predictive: [
        'predict', 'classify', 'estimate', 'will it', 'likelihood',
        'probability of', 'churn', 'risk',
    ],
    comparative: [
        'compare', 'a/b', 'ab test', 'variant', 'control vs',
        'difference between', 'lift',
    ],
    diagnostic: [
        'why did', 'caused', 'root cause', 'driver of', 'contribute',
        'reason for', 'attribute',
    ],
    segmentation: [
        'cluster', 'segment', 'persona', 'group similar', 'cohort',
    ],
    dimensionality_reduction: [
        'pca', 'reduce dimension', 'embed', 't-sne', 'tsne', 'umap',
        'feature compression',
    ],
    exploratory: [
        'describe', 'profile', 'explore', 'overview',
        "what's in", 'summarize', 'summarise',
    ],
};

const MIN_CONFIDENCE = 0.4;

const MODE_LABEL: Record<Mode, string> = {
    forecasting: 'Forecasting',
    predictive: 'Predictive',
    comparative: 'Comparative',
    diagnostic: 'Diagnostic',
    segmentation: 'Segmentation',
    dimensionality_reduction: 'Dimensionality',
    exploratory: 'Exploratory',
};

function buildExplanation(mode: Mode, hits: string[], ctx: SuggestionContext): string {
    const kwList = hits.map(h => `"${h}"`).join(', ');
    const parts = [`matched ${kwList}`];
    if (mode === 'forecasting' && ctx.hasDatetime) {
        parts.push('and dataset has a datetime column');
    }
    if (mode === 'predictive' && ctx.hasTargetCol) {
        parts.push('and a target column is set');
    }
    return parts.join(' ');
}

export function suggestMode(question: string, ctx: SuggestionContext): SuggestionResult | null {
    const q = question.toLowerCase().trim();
    if (q.length < 8) return null;

    let best: SuggestionResult | null = null;

    for (const [mode, kws] of Object.entries(KEYWORDS) as [Mode, string[]][]) {
        const hits = kws.filter(k => q.includes(k));
        if (hits.length === 0) continue;

        let score = Math.min(1, hits.length * 0.35);
        if (mode === 'forecasting' && ctx.hasDatetime) score += 0.2;
        if (mode === 'predictive' && ctx.hasTargetCol) score += 0.2;
        score = Math.min(1, score);

        if (!best || score > best.confidence) {
            best = {
                mode,
                confidence: score,
                matched_keywords: hits,
                explanation: buildExplanation(mode, hits, ctx),
            };
        }
    }

    return best && best.confidence >= MIN_CONFIDENCE ? best : null;
}

export function modeLabel(mode: Mode): string {
    return MODE_LABEL[mode];
}
