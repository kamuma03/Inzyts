/** Output formats produced by a kernel cell, modelled after nbformat. */
export type CellOutput =
    | StreamOutput
    | DisplayDataOutput
    | ExecuteResultOutput
    | ErrorOutput;

export interface StreamOutput {
    output_type: 'stream';
    name: 'stdout' | 'stderr';
    text: string;
}

export interface DisplayDataOutput {
    output_type: 'display_data';
    data: Record<string, string>;
    metadata?: Record<string, unknown>;
}

export interface ExecuteResultOutput {
    output_type: 'execute_result';
    data: Record<string, string>;
    metadata?: Record<string, unknown>;
}

export interface ErrorOutput {
    output_type: 'error';
    ename: string;
    evalue: string;
    traceback: string[];
}

/** Status of a cell — drives the per-cell badge ("idle" / "busy" / "error"). */
export type CellExecState = 'idle' | 'busy' | 'queued' | 'error';

/** A single Live-panel cell row. */
export interface LiveCell {
    id: string;
    code: string;
    /** Outputs accumulated from this cell's most recent execution. */
    outputs: CellOutput[];
    state: CellExecState;
    execution_count: number | null;
    error_name: string | null;
    error_value: string | null;
    duration_ms: number | null;
    killed_reason: string | null;
}

/** WS payloads emitted by `src/server/services/cell_stream.py`. */
export interface CellStatusEvent {
    execution_id: string;
    job_id: string;
    execution_state: 'busy' | 'idle';
}

export interface CellOutputEvent {
    execution_id: string;
    job_id: string;
    output: CellOutput | { output_type: 'status'; execution_state: string };
}

export interface CellCompleteEvent {
    execution_id: string;
    job_id: string;
    success: boolean;
    error_name: string | null;
    error_value: string | null;
    execution_count: number | null;
    duration_ms: number;
    killed_reason: string | null;
}
