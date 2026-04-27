import type { FC } from 'react';
import { HelpCircle } from 'lucide-react';

interface QuestionCardProps {
    question: string | null | undefined;
}

/** Read-only display of the user's analysis question, shown in the right rail. */
export const QuestionCard: FC<QuestionCardProps> = ({ question }) => {
    return (
        <div className="p-3 border border-[var(--border-color)] rounded-lg bg-[var(--bg-surface-hi)]">
            <div className="flex items-center gap-2 mb-2 text-[10px] uppercase tracking-[1.5px] text-[var(--text-dim)]">
                <HelpCircle size={12} />
                <span>Question</span>
            </div>
            <p className="m-0 text-[13px] leading-[1.5] text-[var(--text-primary)] break-words">
                {question?.trim() ? question : (
                    <span className="text-[var(--text-dim)] italic">No question provided.</span>
                )}
            </p>
        </div>
    );
};
