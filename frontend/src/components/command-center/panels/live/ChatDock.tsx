import { useCallback, useState, type FC } from 'react';
import { MessageSquare, ChevronUp, ChevronDown } from 'lucide-react';
import { FollowUpChat } from '../../../FollowUpChat';

interface ChatDockProps {
    jobId: string;
}

const STORAGE_KEY = 'inzyts.notebook.chatDockOpen';

/** Re-homes the follow-up chat into a collapsible dock anchored to the bottom
 *  of the notebook surface (FR-11). Collapsed it's a 44px handle that reclaims
 *  its height for the notebook; expanded it slides up to ≤360px. The open
 *  state persists across reloads. */
export const ChatDock: FC<ChatDockProps> = ({ jobId }) => {
    const [open, setOpen] = useState<boolean>(() => {
        try {
            return sessionStorage.getItem(STORAGE_KEY) === '1';
        } catch {
            return false;
        }
    });

    const toggle = useCallback(() => {
        setOpen((prev) => {
            const next = !prev;
            try { sessionStorage.setItem(STORAGE_KEY, next ? '1' : '0'); } catch { /* noop */ }
            return next;
        });
    }, []);

    return (
        <div className="chat-dock shrink-0 border-t border-[var(--rule)] bg-[var(--surface-1)]">
            <button
                type="button"
                onClick={toggle}
                className="flex items-center gap-2 w-full h-11 px-4 border-none bg-transparent cursor-pointer text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.03)]"
                aria-expanded={open}
                aria-label={open ? 'Collapse follow-up chat' : 'Expand follow-up chat'}
            >
                <MessageSquare size={15} className="text-[var(--accent)]" />
                <span className="text-[0.85rem] font-medium">Follow-up chat</span>
                {!open && (
                    <span className="text-[0.72rem] text-[var(--text-dim)]">
                        Ask a question about this analysis
                    </span>
                )}
                <span className="ml-auto">
                    {open ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
                </span>
            </button>
            {open && (
                <div className="chat-dock-body max-h-[360px] overflow-y-auto px-4 pb-3">
                    <FollowUpChat jobId={jobId} />
                </div>
            )}
        </div>
    );
};
