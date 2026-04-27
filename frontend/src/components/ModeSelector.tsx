import { FC, useState, useCallback, useRef, useEffect, type KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { Sparkles, BarChart2, TrendingUp, GitCompare, Activity, PieChart, Layers, Info, Wand2 } from 'lucide-react';
import { AnalysisRequest } from '../api';

export const ANALYSIS_MODES: {
    id: AnalysisRequest['mode'];
    label: string;
    desc: string;
    detailedDesc: string;
    icon: any;
}[] = [
    {
        id: 'exploratory',
        label: 'Exploratory',
        desc: 'Understand data structure, quality, and initial patterns.',
        detailedDesc: 'Performs comprehensive data profiling including missing values, distributions, correlations, and outlier detection. Best for initial data understanding when you don\'t have a specific hypothesis. Produces a detailed profile notebook without modeling.',
        icon: Sparkles
    },
    {
        id: 'predictive',
        label: 'Predictive',
        desc: 'Train models to predict a target variable (Regression/Classification).',
        detailedDesc: 'Builds and evaluates machine learning models to predict a specified target column. Automatically selects between regression and classification based on the target type. Includes feature importance, cross-validation, and model comparison.',
        icon: BarChart2
    },
    {
        id: 'forecasting',
        label: 'Forecasting',
        desc: 'Predict future values based on time-series data.',
        detailedDesc: 'Analyzes temporal patterns using time-series models (Prophet, ARIMA, exponential smoothing). Requires data with a datetime column. Generates future predictions with confidence intervals and trend/seasonality decomposition.',
        icon: TrendingUp
    },
    {
        id: 'comparative',
        label: 'Comparative',
        desc: 'Compare groups (A/B Testing) or analyze variations.',
        detailedDesc: 'Runs statistical tests to compare two or more groups in your data. Supports A/B testing, hypothesis testing, and effect size estimation. Ideal for experiment analysis, treatment vs control comparisons, or cohort analysis.',
        icon: GitCompare
    },
    {
        id: 'diagnostic',
        label: 'Diagnostic',
        desc: 'Identify root causes of anomalies or outcomes.',
        detailedDesc: 'Investigates why specific outcomes or anomalies occurred using root cause analysis techniques. Identifies key drivers and contributing factors behind trends, drops, or spikes in your data.',
        icon: Activity
    },
    {
        id: 'segmentation',
        label: 'Segmentation',
        desc: 'Cluster data into meaningful groups.',
        detailedDesc: 'Uses unsupervised clustering algorithms (K-Means, DBSCAN) to discover natural groupings in your data. Generates segment profiles with key characteristics and distributions for each cluster.',
        icon: PieChart
    },
    {
        id: 'dimensionality_reduction',
        label: 'Dimensionality',
        desc: 'Reduce features using PCA/t-SNE.',
        detailedDesc: 'Reduces high-dimensional data to fewer components using PCA, t-SNE, or UMAP. Useful for visualization of complex datasets, feature compression, and understanding variance structure across many variables.',
        icon: Layers
    },
];

/** Small info icon with a tooltip rendered via portal to avoid overflow clipping. */
const InfoTooltip: FC<{ text: string }> = ({ text }) => {
    const [visible, setVisible] = useState(false);
    const [coords, setCoords] = useState({ top: 0, left: 0, showBelow: false });
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const buttonRef = useRef<HTMLButtonElement>(null);
    const tooltipRef = useRef<HTMLDivElement>(null);

    const updatePosition = () => {
        if (!buttonRef.current) return;
        const rect = buttonRef.current.getBoundingClientRect();
        const showBelow = rect.top < 160;
        const tooltipWidth = 260;
        // Align right edge of tooltip with right edge of icon, clamp to viewport
        let left = rect.right - tooltipWidth;
        if (left < 8) left = 8;
        if (left + tooltipWidth > window.innerWidth - 8) left = window.innerWidth - tooltipWidth - 8;

        setCoords({
            top: showBelow ? rect.bottom + 8 : rect.top - 8,
            left,
            showBelow,
        });
    };

    const show = () => {
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        updatePosition();
        setVisible(true);
    };
    const hide = () => {
        timeoutRef.current = setTimeout(() => setVisible(false), 150);
    };
    const toggle = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (visible) {
            setVisible(false);
        } else {
            show();
        }
    };

    // Close on outside click or scroll
    useEffect(() => {
        if (!visible) return;
        const handleClose = (e: MouseEvent) => {
            if (
                buttonRef.current?.contains(e.target as Node) ||
                tooltipRef.current?.contains(e.target as Node)
            ) return;
            setVisible(false);
        };
        const handleScroll = () => setVisible(false);
        document.addEventListener('mousedown', handleClose);
        window.addEventListener('scroll', handleScroll, true);
        return () => {
            document.removeEventListener('mousedown', handleClose);
            window.removeEventListener('scroll', handleScroll, true);
        };
    }, [visible]);

    return (
        <>
            <button
                ref={buttonRef}
                type="button"
                onClick={toggle}
                onMouseEnter={show}
                onMouseLeave={hide}
                aria-label="More info"
                className="inline-flex items-center justify-center p-0 border-none bg-transparent cursor-pointer text-[var(--text-secondary)] opacity-50 hover:opacity-100 transition-opacity"
            >
                <Info size={14} />
            </button>
            {visible && createPortal(
                <div
                    ref={tooltipRef}
                    onMouseEnter={() => { if (timeoutRef.current) clearTimeout(timeoutRef.current); }}
                    onMouseLeave={hide}
                    style={{
                        position: 'fixed',
                        zIndex: 9999,
                        top: coords.showBelow ? coords.top : undefined,
                        bottom: coords.showBelow ? undefined : window.innerHeight - coords.top,
                        left: coords.left,
                        width: 260,
                    }}
                    className="p-3 text-[0.8rem] leading-[1.5] text-[var(--text-secondary)] bg-[var(--bg-deep-twilight)] border border-[var(--border-color)] rounded-lg shadow-[0_8px_24px_rgba(0,0,0,0.5)]"
                >
                    {text}
                </div>,
                document.body,
            )}
        </>
    );
};

interface ModeSelectorProps {
    selectedMode: AnalysisRequest['mode'];
    onSelect: (mode: AnalysisRequest['mode']) => void;
    suggestedMode?: AnalysisRequest['mode'] | null;
    suggestionExplanation?: string | null;
    suggestionConfidence?: number | null;
    suggestionMatchedKeywords?: string[];
}

const confidenceColor = (c: number | null | undefined): string => {
    if (c == null) return 'var(--text-dim)';
    if (c >= 0.7) return 'var(--status-good)';
    if (c >= 0.5) return 'var(--status-warn)';
    return 'var(--text-dim)';
};

const confidenceLabel = (c: number | null | undefined): string => {
    if (c == null) return 'unknown';
    if (c >= 0.7) return 'high confidence';
    if (c >= 0.5) return 'medium confidence';
    return 'low confidence';
};

export const ModeSelector: FC<ModeSelectorProps> = ({
    selectedMode, onSelect, suggestedMode, suggestionExplanation,
    suggestionConfidence, suggestionMatchedKeywords,
}) => {
    const handleKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
        const currentIndex = ANALYSIS_MODES.findIndex(m => m.id === selectedMode);
        let nextIndex = currentIndex;

        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
            e.preventDefault();
            nextIndex = (currentIndex + 1) % ANALYSIS_MODES.length;
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
            e.preventDefault();
            nextIndex = (currentIndex - 1 + ANALYSIS_MODES.length) % ANALYSIS_MODES.length;
        } else if (e.key === 'Home') {
            e.preventDefault();
            nextIndex = 0;
        } else if (e.key === 'End') {
            e.preventDefault();
            nextIndex = ANALYSIS_MODES.length - 1;
        } else {
            return;
        }

        onSelect(ANALYSIS_MODES[nextIndex].id);
        const btn = document.getElementById(`mode-${ANALYSIS_MODES[nextIndex].id}`);
        btn?.focus();
    }, [selectedMode, onSelect]);

    return (
        <div>
            {/* Suggestion banner */}
            {suggestedMode && suggestedMode !== selectedMode && (
                <div className="flex items-center gap-2 px-3 py-2 mb-3 bg-[rgba(0,255,238,0.08)] border border-[rgba(0,255,238,0.25)] rounded-[6px] text-[0.85rem] text-[var(--text-secondary)]">
                    <Wand2 size={14} className="text-[var(--bg-turquoise-surf)] shrink-0" />
                    <span
                        aria-label={`Suggested mode: ${ANALYSIS_MODES.find(m => m.id === suggestedMode)?.label || suggestedMode}, ${confidenceLabel(suggestionConfidence)}`}
                        className="inline-block w-2 h-2 rounded-full shrink-0"
                        style={{ backgroundColor: confidenceColor(suggestionConfidence) }}
                        title={confidenceLabel(suggestionConfidence)}
                    />
                    <span>
                        AI suggests <strong className="text-[var(--bg-turquoise-surf)]">
                            {ANALYSIS_MODES.find(m => m.id === suggestedMode)?.label || suggestedMode}
                        </strong>
                        {suggestionMatchedKeywords && suggestionMatchedKeywords.length > 0 && (
                            <span> — matched {suggestionMatchedKeywords.map(k => `"${k}"`).join(', ')}</span>
                        )}
                    </span>
                    {suggestionExplanation && (
                        <span className="ml-2 shrink-0">
                            <InfoTooltip text={suggestionExplanation} />
                        </span>
                    )}
                    <button
                        type="button"
                        onClick={() => onSelect(suggestedMode)}
                        className="ml-auto px-[0.6rem] py-1 text-[0.8rem] font-semibold bg-[var(--bg-turquoise-surf)] text-[var(--bg-deep-twilight)] border-none rounded cursor-pointer shrink-0"
                    >
                        Apply
                    </button>
                </div>
            )}

            <div
                role="radiogroup"
                aria-label="Analysis mode selection"
                onKeyDown={handleKeyDown}
                className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3 mt-2"
            >
                {ANALYSIS_MODES.map((mode) => {
                    const isSelected = selectedMode === mode.id;
                    const isSuggested = suggestedMode === mode.id && !isSelected;
                    const Icon = mode.icon;
                    return (
                        <button
                            key={mode.id}
                            id={`mode-${mode.id}`}
                            onClick={() => onSelect(mode.id)}
                            type="button"
                            role="radio"
                            aria-checked={isSelected}
                            aria-label={`${mode.label} mode: ${mode.desc}`}
                            tabIndex={isSelected ? 0 : -1}
                            className={`p-3 cursor-pointer flex flex-col gap-2 transition-all duration-200 w-full text-left appearance-none text-inherit rounded-lg ${
                                isSelected
                                    ? 'border-2 border-[var(--bg-turquoise-surf)] bg-[rgba(0,255,238,0.05)]'
                                    : isSuggested
                                        ? 'border-2 border-[rgba(0,255,238,0.4)] bg-[rgba(0,255,238,0.02)]'
                                        : 'border border-[var(--border-color)] bg-[rgba(0,0,0,0.2)]'
                            }`}
                        >
                            <div className={`flex items-center gap-2 font-semibold ${isSelected ? 'text-[var(--bg-turquoise-surf)]' : 'text-[var(--text-primary)]'}`}>
                                <Icon size={18} />
                                <span>{mode.label}</span>
                                {isSuggested && (
                                    <span className="ml-auto text-[0.65rem] font-bold px-[5px] py-px rounded-[3px] bg-[rgba(0,255,238,0.15)] text-[var(--bg-turquoise-surf)] uppercase tracking-[0.5px]">
                                        Suggested
                                    </span>
                                )}
                                <span className={isSuggested ? '' : 'ml-auto'}>
                                    <InfoTooltip text={mode.detailedDesc} />
                                </span>
                            </div>
                            <p className="m-0 text-[0.8rem] text-[var(--text-secondary)] leading-[1.4]">
                                {mode.desc}
                            </p>
                        </button>
                    );
                })}
            </div>
        </div>
    );
};
