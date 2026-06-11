import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// --- Mock socket.io-client with a controllable fake socket -----------------
type Handler = (...args: unknown[]) => void;

interface FakeSocket {
    connected: boolean;
    handlers: Record<string, Handler>;
    on: ReturnType<typeof vi.fn>;
    off: ReturnType<typeof vi.fn>;
    emit: ReturnType<typeof vi.fn>;
    disconnect: ReturnType<typeof vi.fn>;
    /** Test helper to fire a registered handler. */
    fire: (event: string, ...args: unknown[]) => void;
}

const makeFakeSocket = (): FakeSocket => {
    const handlers: Record<string, Handler> = {};
    const socket: FakeSocket = {
        connected: false,
        handlers,
        on: vi.fn((event: string, cb: Handler) => { handlers[event] = cb; }),
        off: vi.fn((event: string) => { delete handlers[event]; }),
        emit: vi.fn(),
        disconnect: vi.fn(() => { socket.connected = false; }),
        fire: (event: string, ...args: unknown[]) => { handlers[event]?.(...args); },
    };
    return socket;
};

let lastSocket: FakeSocket;
const ioMock = vi.fn((..._args: unknown[]) => {
    lastSocket = makeFakeSocket();
    return lastSocket;
});

vi.mock('socket.io-client', () => ({
    io: (...args: unknown[]) => ioMock(...args),
    Socket: class {},
}));

import { useSocket } from './useSocket';

describe('useSocket', () => {
    beforeEach(() => {
        ioMock.mockClear();
        sessionStorage.clear();
    });

    it('opens a connection and joins the job room on connect', () => {
        const { unmount } = renderHook(() => useSocket('job-123'));
        expect(ioMock).toHaveBeenCalledTimes(1);

        // Simulate the socket connecting — the shared handler emits join_job.
        act(() => { lastSocket.fire('connect'); });
        expect(lastSocket.emit).toHaveBeenCalledWith('join_job', { job_id: 'job-123' });

        unmount();
    });

    it('does not open a connection when jobId is null', () => {
        renderHook(() => useSocket(null));
        expect(ioMock).not.toHaveBeenCalled();
    });

    it('tears down (disconnect) when the last consumer unmounts', () => {
        const { unmount } = renderHook(() => useSocket('job-xyz'));
        expect(lastSocket.disconnect).not.toHaveBeenCalled();
        unmount();
        expect(lastSocket.disconnect).toHaveBeenCalledTimes(1);
    });

    it('shares ONE connection + one join across multiple consumers of the same job', () => {
        const a = renderHook(() => useSocket('shared-job'));
        const b = renderHook(() => useSocket('shared-job'));

        // Only a single underlying io() connection for the same jobId.
        expect(ioMock).toHaveBeenCalledTimes(1);

        // One join_job for the shared room on connect.
        act(() => { lastSocket.fire('connect'); });
        const joinCalls = lastSocket.emit.mock.calls.filter(([ev]) => ev === 'join_job');
        expect(joinCalls).toHaveLength(1);

        // First consumer leaving must NOT disconnect — the second still holds a ref.
        a.unmount();
        expect(lastSocket.disconnect).not.toHaveBeenCalled();

        // Last consumer leaving tears it down.
        b.unmount();
        expect(lastSocket.disconnect).toHaveBeenCalledTimes(1);
    });

    it('fans a log event out to consumer state', () => {
        const { result, unmount } = renderHook(() => useSocket('job-logs'));
        act(() => {
            lastSocket.fire('connect');
            lastSocket.fire('log', { timestamp: '2020-01-01T00:00:00Z', level: 'INFO', message: 'hello' });
        });
        expect(result.current.logs).toHaveLength(1);
        expect(result.current.logs[0].message).toBe('hello');
        unmount();
    });

    it('passes the JWT as an auth payload when present', () => {
        sessionStorage.setItem('inzyts_jwt_token', 'tok-abc');
        const { unmount } = renderHook(() => useSocket('job-auth'));
        const opts = ioMock.mock.calls[0]?.[1] as { auth?: { token?: string } } | undefined;
        expect(opts?.auth?.token).toBe('tok-abc');
        unmount();
    });
});
