import React, { useState, useRef, useEffect } from 'react';
import { AnalysisAPI } from '../api';
import { Loader, Send, MessageSquare, AlertTriangle, Sparkles } from 'lucide-react';
import { formatMarkdown } from '../utils/formatMarkdown';

interface FollowUpCell {
    cell_type: string;
    source: string;
    output: string;
    images: string[];
}

interface ConversationMessage {
    role: 'user' | 'assistant';
    content: string;
    cells?: FollowUpCell[];
    created_at?: string;
}

interface FollowUpChatProps {
    jobId: string;
}


export const FollowUpChat: React.FC<FollowUpChatProps> = ({ jobId }) => {
    const [messages, setMessages] = useState<ConversationMessage[]>([]);
    const [question, setQuestion] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');

    const chatEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const isSubmitting = useRef(false);

    // Load conversation history on mount with unmount guard
    useEffect(() => {
        let mounted = true;
        const loadHistory = async () => {
            try {
                const data = await AnalysisAPI.getConversationHistory(jobId);
                if (mounted && data.messages && data.messages.length > 0) {
                    setMessages(data.messages);
                }
            } catch (err) {
                // Silently fail — no history is fine for new jobs
            }
        };
        loadHistory();
        return () => { mounted = false; };
    }, [jobId]);

    // Auto-scroll to bottom
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSubmit = async () => {
        if (!question.trim() || isSubmitting.current) return;

        isSubmitting.current = true;
        const userQuestion = question.trim();
        setQuestion('');
        setError('');
        setIsLoading(true);

        // Optimistically add user message
        const userMsg: ConversationMessage = { role: 'user', content: userQuestion };
        setMessages(prev => [...prev, userMsg]);

        try {
            const result = await AnalysisAPI.askFollowUp(jobId, userQuestion);

            if (result.success) {
                const assistantMsg: ConversationMessage = {
                    role: 'assistant',
                    content: result.summary,
                    cells: result.cells,
                };
                setMessages(prev => [...prev, assistantMsg]);
            } else {
                setError(result.error || 'Failed to generate analysis');
                // Remove optimistic user message on failure
                setMessages(prev => prev.slice(0, -1));
            }
        } catch (err) {
            setError('Network error — please try again');
            setMessages(prev => prev.slice(0, -1));
        } finally {
            setIsLoading(false);
            isSubmitting.current = false;
            inputRef.current?.focus();
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
        if (e.key === 'Escape') {
            setQuestion('');
        }
    };

    return (
        <div className="mt-4 border border-[var(--border-color)] rounded-lg bg-[rgba(13,27,42,0.5)] overflow-hidden">
            {/* Header */}
            <div className="flex items-center gap-2 px-4 py-2.5 text-[0.85rem] font-semibold text-[var(--bg-turquoise-surf)] border-b border-[rgba(65,90,119,0.3)] bg-[rgba(27,38,59,0.4)]">
                <MessageSquare size={16} />
                <span>Follow-Up Analysis</span>
                {messages.length > 0 && (
                    <span className="ml-auto text-[0.75rem] font-normal text-[var(--text-secondary)] opacity-70">
                        {Math.ceil(messages.filter(m => m.role === 'user').length)} questions
                    </span>
                )}
            </div>

            {/* Messages */}
            {messages.length > 0 && (
                <div className="max-h-[400px] overflow-y-auto p-3 flex flex-col gap-3">
                    {messages.map((msg, i) => (
                        <div key={i} className="animate-[slideIn_0.2s_ease-out]">
                            {msg.role === 'user' ? (
                                <div className="inline-flex items-center gap-2 bg-[rgba(76,201,240,0.1)] border border-[rgba(76,201,240,0.25)] rounded-[12px_12px_12px_4px] px-3.5 py-2 text-[0.88rem] text-[var(--text-primary)] max-w-[80%]">
                                    <Sparkles size={14} className="text-[var(--bg-turquoise-surf)] shrink-0" />
                                    <span>{msg.content}</span>
                                </div>
                            ) : (
                                <div className="flex flex-col gap-2">
                                    {/* Summary */}
                                    {msg.content && (
                                        <div className="text-[0.88rem] text-[var(--text-secondary)] leading-relaxed py-1">
                                            {msg.content}
                                        </div>
                                    )}

                                    {/* Generated cells */}
                                    {msg.cells && msg.cells.map((cell, ci) => (
                                        <div key={ci} className="rounded-md overflow-hidden">
                                            {cell.cell_type === 'code' ? (
                                                <>
                                                    <pre className="font-mono text-[0.82rem] leading-relaxed text-[#e6edf3] bg-[rgba(27,38,59,0.7)] px-3.5 py-2.5 m-0 whitespace-pre-wrap break-words rounded-t-md">{cell.source}</pre>
                                                    {cell.output && (
                                                        <pre className="font-mono text-[0.78rem] text-[var(--text-secondary)] bg-[rgba(13,27,42,0.6)] px-3.5 py-1.5 m-0 whitespace-pre-wrap border-t border-[rgba(65,90,119,0.2)] rounded-b-md">{cell.output}</pre>
                                                    )}
                                                    {cell.images && cell.images.map((img, ii) => (
                                                        <img
                                                            key={ii}
                                                            src={`data:image/png;base64,${img}`}
                                                            alt={`Follow-up chart ${ii}`}
                                                            className="max-w-full rounded mt-1 border border-[rgba(65,90,119,0.3)]"
                                                        />
                                                    ))}
                                                </>
                                            ) : (
                                                <div
                                                    className="text-[var(--text-primary)] leading-[1.7] text-[0.88rem] py-1 [&_h1]:my-1 [&_h1]:text-[var(--text-primary)] [&_h2]:my-1 [&_h2]:text-[var(--text-primary)] [&_h3]:my-1 [&_h3]:text-[var(--text-primary)] [&_code]:bg-[rgba(27,38,59,0.6)] [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded-sm [&_code]:text-[0.85em]"
                                                    dangerouslySetInnerHTML={{
                                                        __html: formatMarkdown(cell.source),
                                                    }}
                                                />
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}

                    {/* Loading indicator */}
                    {isLoading && (
                        <div className="animate-[slideIn_0.2s_ease-out]">
                            <div className="flex items-center gap-2 text-[0.85rem] text-[var(--bg-turquoise-surf)] py-2">
                                <Loader size={16} className="animate-spin" />
                                <span>Analyzing...</span>
                            </div>
                        </div>
                    )}

                    <div ref={chatEndRef} />
                </div>
            )}

            {/* Error */}
            {error && (
                <div className="flex items-center gap-1.5 px-4 py-2 text-[0.8rem] text-red-500 bg-red-500/[0.08] border-t border-red-500/15">
                    <AlertTriangle size={14} />
                    <span>{error}</span>
                </div>
            )}

            {/* Input */}
            <div className="flex items-center gap-2 px-3.5 py-2.5 bg-[rgba(27,38,59,0.5)] border-t border-[rgba(65,90,119,0.3)]">
                <Sparkles size={16} className="text-[var(--bg-turquoise-surf)] shrink-0 opacity-70" />
                <input
                    ref={inputRef}
                    type="text"
                    className="flex-1 bg-transparent border-none outline-none text-[var(--text-primary)] text-[0.88rem] font-sans placeholder:text-[var(--text-secondary)] placeholder:opacity-50"
                    placeholder="Ask a follow-up question about this analysis..."
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={isLoading}
                />
                <button
                    className="flex items-center justify-center bg-transparent border border-[rgba(76,201,240,0.3)] rounded-md p-1.5 text-[var(--bg-turquoise-surf)] cursor-pointer transition-all duration-200 hover:bg-[rgba(76,201,240,0.1)] hover:border-[var(--bg-turquoise-surf)] disabled:opacity-35 disabled:cursor-not-allowed"
                    onClick={handleSubmit}
                    disabled={isLoading || !question.trim()}
                    title="Send"
                >
                    {isLoading ? (
                        <Loader size={16} className="animate-spin" />
                    ) : (
                        <Send size={16} />
                    )}
                </button>
            </div>
        </div>
    );
};
