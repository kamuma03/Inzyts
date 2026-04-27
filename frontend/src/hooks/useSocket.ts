import { useEffect, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';
import type { PhaseStatus, RunMetrics } from '../api';
import type {
    CellCompleteEvent,
    CellOutputEvent,
    CellStatusEvent,
} from '../components/command-center/panels/live/types';

export interface LogMessage {
    timestamp: string;
    level: string;
    message: string;
}

export interface AgentEvent {
    type: string;
    event: string;
    phase?: string;
    agent?: string;
    status?: string;
    data: Record<string, unknown>;
}

export interface ProgressUpdate {
    progress: number;
    message: string;
    phase: string;
    elapsed_seconds: number | null;
    eta_seconds: number | null;
    phase_timings: Record<string, { elapsed: number }>;
}

/** Optional callbacks for the per-job cell-execution stream. Passed into
 *  useSocket so the Live panel can react to streaming output without
 *  opening a second socket connection for the same job. */
export interface UseSocketHandlers {
    onCellStatus?: (event: CellStatusEvent) => void;
    onCellOutput?: (event: CellOutputEvent) => void;
    onCellComplete?: (event: CellCompleteEvent) => void;
}

export const useSocket = (jobId: string | null, handlers?: UseSocketHandlers) => {
    const [logs, setLogs] = useState<LogMessage[]>([]);
    const [events, setEvents] = useState<AgentEvent[]>([]);
    const [progress, setProgress] = useState<ProgressUpdate | null>(null);
    const [metrics, setMetrics] = useState<RunMetrics | null>(null);
    const [phases, setPhases] = useState<PhaseStatus[] | null>(null);
    const [isConnected, setIsConnected] = useState(false);
    const socketRef = useRef<Socket | null>(null);
    // Handlers held in a ref so updating them never forces a socket
    // reconnect. The socket reconnects only when jobId changes.
    const handlersRef = useRef<UseSocketHandlers | undefined>(handlers);
    handlersRef.current = handlers;

    useEffect(() => {
        if (!jobId) return;

        // Track whether this effect is still active to prevent state updates
        // after cleanup (e.g. when jobId changes rapidly).
        let mounted = true;

        // Determine backend URL dynamically for Docker and local dev support
        const getSocketUrl = () => {
            // Use relative URL to leverage Vite proxy / Nginx reverse proxy
            return "/";
        };

        // Use sessionStorage consistently with api.ts — cleared on tab/browser close.
        const token = sessionStorage.getItem('inzyts_jwt_token');

        const socket = io(getSocketUrl(), {
            transports: ['websocket'],
            timeout: 10000,
            extraHeaders: token?.trim() ? { Authorization: `Bearer ${token}` } : undefined
        });

        socketRef.current = socket;

        socket.on('connect', () => {
            if (!mounted) return;
            if (import.meta.env.DEV) console.log('Socket connected');
            setIsConnected(true);
            socket.emit('join_job', { job_id: jobId });
            // Reset state on new connection/job
            setLogs([]);
            setEvents([]);
            setProgress(null);
            setMetrics(null);
            setPhases(null);
        });

        socket.on('disconnect', () => {
            if (!mounted) return;
            if (import.meta.env.DEV) console.log('Socket disconnected');
            setIsConnected(false);
        });

        socket.on('log', (data: unknown) => {
            if (!mounted) return;
            // Handle both string and object logs
            let newLog: LogMessage;
            if (typeof data === 'string') {
                newLog = { timestamp: new Date().toISOString(), level: 'INFO', message: data };
            } else {
                let fallbackMessage: string;
                try {
                    fallbackMessage = JSON.stringify(data);
                } catch {
                    fallbackMessage = String(data);
                }
                const logObj = data as Record<string, unknown>;
                newLog = {
                    timestamp: (logObj.timestamp as string) || new Date().toISOString(),
                    level: (logObj.level as string) || 'INFO',
                    message: (logObj.message as string) || fallbackMessage
                };
            }
            setLogs((prev) => {
                const updated = [...prev, newLog];
                // Cap at 500 entries to prevent unbounded memory growth
                return updated.length > 500 ? updated.slice(-500) : updated;
            });
        });

        socket.on('agent_event', (data: AgentEvent) => {
            if (!mounted) return;
            setEvents((prev) => [...prev, data]);
        });

        socket.on('progress', (data: ProgressUpdate) => {
            if (!mounted) return;
            setProgress(data);
        });

        socket.on('metrics_snapshot', (data: RunMetrics) => {
            if (!mounted) return;
            setMetrics(data);
        });

        socket.on('phase_update', (data: { job_id: string; phases: PhaseStatus[] }) => {
            if (!mounted) return;
            setPhases(data.phases);
        });

        // Cell-execution stream events — forwarded to optional handler
        // callbacks. Keeps cell state out of useSocket itself so a 1000-event
        // run doesn't re-render every consumer of the hook.
        socket.on('cell_status', (data: CellStatusEvent) => {
            if (!mounted) return;
            handlersRef.current?.onCellStatus?.(data);
        });
        socket.on('cell_output', (data: CellOutputEvent) => {
            if (!mounted) return;
            handlersRef.current?.onCellOutput?.(data);
        });
        socket.on('cell_complete', (data: CellCompleteEvent) => {
            if (!mounted) return;
            handlersRef.current?.onCellComplete?.(data);
        });

        return () => {
            mounted = false;
            socket.off('connect');
            socket.off('disconnect');
            socket.off('log');
            socket.off('agent_event');
            socket.off('progress');
            socket.off('metrics_snapshot');
            socket.off('phase_update');
            socket.off('cell_status');
            socket.off('cell_output');
            socket.off('cell_complete');
            socket.disconnect();
            // Clear the ref so stale socket instances don't linger when jobId changes.
            socketRef.current = null;
        };
    }, [jobId]);

    return { logs, events, progress, metrics, phases, isConnected };
};
