import { useEffect, useRef, useState } from 'react';
import type { Mode, SuggestionResult } from '../utils/modeHeuristic';
import { suggestMode } from '../utils/modeHeuristic';

interface ModeSuggestionState {
    suggestedMode: Mode | null;
    confidence: number | null;
    explanation: string | null;
    matchedKeywords: string[];
}

const EMPTY: ModeSuggestionState = {
    suggestedMode: null,
    confidence: null,
    explanation: null,
    matchedKeywords: [],
};

interface ProfileHints {
    hasDatetime?: boolean;
}

export const useModeSuggestion = (
    question: string,
    targetColumn: string,
    hints: ProfileHints = {},
) => {
    const [state, setState] = useState<ModeSuggestionState>(EMPTY);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        if (timerRef.current) clearTimeout(timerRef.current);

        const trimmedQ = question.trim();
        if (trimmedQ.length < 8) {
            setState(EMPTY);
            return;
        }

        timerRef.current = setTimeout(() => {
            const result: SuggestionResult | null = suggestMode(trimmedQ, {
                hasDatetime: !!hints.hasDatetime,
                hasTargetCol: !!targetColumn.trim(),
            });

            if (!result) {
                setState(EMPTY);
                return;
            }

            setState({
                suggestedMode: result.mode,
                confidence: result.confidence,
                explanation: result.explanation,
                matchedKeywords: result.matched_keywords,
            });
        }, 300);

        return () => {
            if (timerRef.current) clearTimeout(timerRef.current);
        };
    }, [question, targetColumn, hints.hasDatetime]);

    return state;
};
