import { useEffect, useRef, useState } from 'react';
import { AnalysisAPI, ModeSuggestionResponse } from '../api';

interface ModeSuggestionState {
    suggestedMode: ModeSuggestionResponse['suggested_mode'] | null;
    confidence: ModeSuggestionResponse['confidence'] | null;
    explanation: string | null;
    isLoading: boolean;
}

export const useModeSuggestion = (question: string, targetColumn: string) => {
    const [state, setState] = useState<ModeSuggestionState>({
        suggestedMode: null,
        confidence: null,
        explanation: null,
        isLoading: false,
    });
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const abortRef = useRef(false);

    useEffect(() => {
        // Clear previous timer
        if (timerRef.current) {
            clearTimeout(timerRef.current);
        }

        const trimmedQ = question.trim();
        const trimmedT = targetColumn.trim();

        // Nothing to suggest on
        if (!trimmedQ && !trimmedT) {
            setState({ suggestedMode: null, confidence: null, explanation: null, isLoading: false });
            return;
        }

        abortRef.current = false;
        setState(prev => ({ ...prev, isLoading: true }));

        timerRef.current = setTimeout(async () => {
            try {
                const result = await AnalysisAPI.suggestMode(
                    trimmedQ || undefined,
                    trimmedT || undefined,
                );
                if (!abortRef.current) {
                    setState({
                        suggestedMode: result.suggested_mode,
                        confidence: result.confidence,
                        explanation: result.explanation,
                        isLoading: false,
                    });
                }
            } catch {
                // Silently ignore errors — suggestion is non-critical
                if (!abortRef.current) {
                    setState(prev => ({ ...prev, isLoading: false }));
                }
            }
        }, 500);

        return () => {
            abortRef.current = true;
            if (timerRef.current) {
                clearTimeout(timerRef.current);
            }
        };
    }, [question, targetColumn]);

    return state;
};
