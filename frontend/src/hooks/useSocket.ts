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

// ---------------------------------------------------------------------------
// Shared, ref-counted connection registry
// ---------------------------------------------------------------------------
//
// Multiple components (JobContext + LivePanel) call useSocket(jobId) for the
// SAME job. Previously each call opened its own socket.io connection and its
// own `join_job`, doubling server-side fan-out and connection overhead. We now
// keep ONE module-level connection per jobId, ref-counted: the first consumer
// creates it (and joins the room), the last consumer to unmount tears it down.
// Each consumer registers its own event callbacks; the single socket fans
// every event out to all registered consumers.

type SocketEvent =
    | 'connect'
    | 'disconnect'
    | 'log'
    | 'agent_event'
    | 'progress'
    | 'metrics_snapshot'
    | 'phase_update'
    | 'cell_status'
    | 'cell_output'
    | 'cell_complete';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Listener = (...args: any[]) => void;

interface SharedConnection {
    socket: Socket;
    jobId: string;
    refCount: number;
    listeners: Record<SocketEvent, Set<Listener>>;
}

const connections = new Map<string, SharedConnection>();

const SOCKET_EVENTS: SocketEvent[] = [
    'connect',
    'disconnect',
    'log',
    'agent_event',
    'progress',
    'metrics_snapshot',
    'phase_update',
    'cell_status',
    'cell_output',
    'cell_complete',
];

function emit(conn: SharedConnection, event: SocketEvent, ...args: unknown[]) {
    conn.listeners[event].forEach((fn) => {
        try {
            fn(...args);
        } catch (e) {
            if (import.meta.env.DEV) console.error(`useSocket listener for "${event}" threw`, e);
        }
    });
}

function acquireConnection(jobId: string): SharedConnection {
    const existing = connections.get(jobId);
    if (existing) {
        existing.refCount += 1;
        return existing;
    }

    // Use sessionStorage consistently with api.ts — cleared on tab/browser close.
    const token = sessionStorage.getItem('inzyts_jwt_token');

    // Auth: prefer the Socket.IO `auth` payload over `extraHeaders`. Browsers
    // cannot set custom headers on the WebSocket handshake, so `extraHeaders`
    // is silently dropped when `transports: ['websocket']` is used — auth then
    // fails server-side and no events ever reach the client. The `auth` option
    // travels in the engine.io connect payload instead, so it works regardless
    // of transport (the server reads it from the third arg of its `connect`
    // handler). We keep extraHeaders too so Node-based test clients can still
    // authenticate.
    const socket = io('/', {
        transports: ['websocket'],
        timeout: 10000,
        auth: token?.trim() ? { token } : undefined,
        extraHeaders: token?.trim() ? { Authorization: `Bearer ${token}` } : undefined,
    });

    const conn: SharedConnection = {
        socket,
        jobId,
        refCount: 1,
        listeners: SOCKET_EVENTS.reduce((acc, ev) => {
            acc[ev] = new Set<Listener>();
            return acc;
        }, {} as Record<SocketEvent, Set<Listener>>),
    };

    // Single set of socket handlers fans out to every registered consumer.
    socket.on('connect', () => {
        if (import.meta.env.DEV) console.log('Socket connected', jobId);
        // (Re)join the job room on every (re)connect so a dropped connection
        // resumes streaming after socket.io auto-reconnects.
        socket.emit('join_job', { job_id: jobId });
        emit(conn, 'connect');
    });
    socket.on('disconnect', () => {
        if (import.meta.env.DEV) console.log('Socket disconnected', jobId);
        emit(conn, 'disconnect');
    });
    socket.on('log', (data: unknown) => emit(conn, 'log', data));
    socket.on('agent_event', (data: AgentEvent) => emit(conn, 'agent_event', data));
    socket.on('progress', (data: ProgressUpdate) => emit(conn, 'progress', data));
    socket.on('metrics_snapshot', (data: RunMetrics) => emit(conn, 'metrics_snapshot', data));
    socket.on('phase_update', (data: { job_id: string; phases: PhaseStatus[] }) =>
        emit(conn, 'phase_update', data),
    );
    socket.on('cell_status', (data: CellStatusEvent) => emit(conn, 'cell_status', data));
    socket.on('cell_output', (data: CellOutputEvent) => emit(conn, 'cell_output', data));
    socket.on('cell_complete', (data: CellCompleteEvent) => emit(conn, 'cell_complete', data));

    connections.set(jobId, conn);
    return conn;
}

function releaseConnection(jobId: string) {
    const conn = connections.get(jobId);
    if (!conn) return;
    conn.refCount -= 1;
    if (conn.refCount > 0) return;
    // Last consumer gone — tear the connection down entirely.
    SOCKET_EVENTS.forEach((ev) => conn.socket.off(ev));
    conn.socket.disconnect();
    connections.delete(jobId);
}

export const useSocket = (jobId: string | null, handlers?: UseSocketHandlers) => {
    const [logs, setLogs] = useState<LogMessage[]>([]);
    const [events, setEvents] = useState<AgentEvent[]>([]);
    const [progress, setProgress] = useState<ProgressUpdate | null>(null);
    const [metrics, setMetrics] = useState<RunMetrics | null>(null);
    const [phases, setPhases] = useState<PhaseStatus[] | null>(null);
    const [isConnected, setIsConnected] = useState(false);

    // Handlers held in a ref so updating them never re-subscribes. The
    // subscription is tied only to jobId.
    const handlersRef = useRef<UseSocketHandlers | undefined>(handlers);
    handlersRef.current = handlers;

    useEffect(() => {
        if (!jobId) return;

        // Fresh state for the job we're (re)subscribing to. This runs once per
        // jobId change — NOT on every socket reconnect — so a transient
        // reconnect no longer wipes the consumer's accumulated logs/events/etc.
        setLogs([]);
        setEvents([]);
        setProgress(null);
        setMetrics(null);
        setPhases(null);

        let mounted = true;
        const conn = acquireConnection(jobId);

        // If the shared socket is already connected (we joined an existing
        // connection), reflect that immediately.
        if (conn.socket.connected) {
            setIsConnected(true);
        }

        const onConnect: Listener = () => {
            if (mounted) setIsConnected(true);
        };
        const onDisconnect: Listener = () => {
            if (mounted) setIsConnected(false);
        };
        const onLog: Listener = (data: unknown) => {
            if (!mounted) return;
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
                    message: (logObj.message as string) || fallbackMessage,
                };
            }
            setLogs((prev) => {
                const updated = [...prev, newLog];
                // Cap at 500 entries to prevent unbounded memory growth.
                return updated.length > 500 ? updated.slice(-500) : updated;
            });
        };
        const onAgentEvent: Listener = (data: AgentEvent) => {
            if (mounted) setEvents((prev) => [...prev, data]);
        };
        const onProgress: Listener = (data: ProgressUpdate) => {
            if (mounted) setProgress(data);
        };
        const onMetrics: Listener = (data: RunMetrics) => {
            if (mounted) setMetrics(data);
        };
        const onPhase: Listener = (data: { job_id: string; phases: PhaseStatus[] }) => {
            if (mounted) setPhases(data.phases);
        };
        const onCellStatus: Listener = (data: CellStatusEvent) =>
            handlersRef.current?.onCellStatus?.(data);
        const onCellOutput: Listener = (data: CellOutputEvent) =>
            handlersRef.current?.onCellOutput?.(data);
        const onCellComplete: Listener = (data: CellCompleteEvent) =>
            handlersRef.current?.onCellComplete?.(data);

        conn.listeners.connect.add(onConnect);
        conn.listeners.disconnect.add(onDisconnect);
        conn.listeners.log.add(onLog);
        conn.listeners.agent_event.add(onAgentEvent);
        conn.listeners.progress.add(onProgress);
        conn.listeners.metrics_snapshot.add(onMetrics);
        conn.listeners.phase_update.add(onPhase);
        conn.listeners.cell_status.add(onCellStatus);
        conn.listeners.cell_output.add(onCellOutput);
        conn.listeners.cell_complete.add(onCellComplete);

        return () => {
            mounted = false;
            conn.listeners.connect.delete(onConnect);
            conn.listeners.disconnect.delete(onDisconnect);
            conn.listeners.log.delete(onLog);
            conn.listeners.agent_event.delete(onAgentEvent);
            conn.listeners.progress.delete(onProgress);
            conn.listeners.metrics_snapshot.delete(onMetrics);
            conn.listeners.phase_update.delete(onPhase);
            conn.listeners.cell_status.delete(onCellStatus);
            conn.listeners.cell_output.delete(onCellOutput);
            conn.listeners.cell_complete.delete(onCellComplete);
            releaseConnection(jobId);
        };
    }, [jobId]);

    return { logs, events, progress, metrics, phases, isConnected };
};
