import { useEffect, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';

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

export const useSocket = (jobId: string | null) => {
    const [logs, setLogs] = useState<LogMessage[]>([]);
    const [events, setEvents] = useState<AgentEvent[]>([]);
    const [progress, setProgress] = useState<ProgressUpdate | null>(null);
    const [isConnected, setIsConnected] = useState(false);
    const socketRef = useRef<Socket | null>(null);

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

        return () => {
            mounted = false;
            socket.off('connect');
            socket.off('disconnect');
            socket.off('log');
            socket.off('agent_event');
            socket.off('progress');
            socket.disconnect();
            // Clear the ref so stale socket instances don't linger when jobId changes.
            socketRef.current = null;
        };
    }, [jobId]);

    return { logs, events, progress, isConnected };
};
