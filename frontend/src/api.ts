import axios from 'axios';

const api = axios.create({
    baseURL: (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api/v2',
});

// Request interceptor to add auth token.
// The token is stored in sessionStorage — cleared on tab/browser close, not persisted.
api.interceptors.request.use((config) => {
    const token = sessionStorage.getItem('inzyts_jwt_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Response interceptor to handle 401 Unauthorized
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response && error.response.status === 401) {
            // Token expired or invalid — clear all auth state
            sessionStorage.removeItem('inzyts_jwt_token');
            sessionStorage.removeItem('inzyts_user_role');
            sessionStorage.removeItem('inzyts_username');
            // Prevent redirect loop if already on login page
            if (window.location.pathname !== '/login') {
                window.location.href = '/login';
            }
        }
        return Promise.reject(error);
    }
);

// ---------------------------------------------------------------------------
// Role helpers
// ---------------------------------------------------------------------------
export type UserRole = 'admin' | 'analyst' | 'viewer';

export function getStoredRole(): UserRole {
    return (sessionStorage.getItem('inzyts_user_role') as UserRole) || 'viewer';
}

export function getStoredUsername(): string | null {
    return sessionStorage.getItem('inzyts_username');
}

export function isAdmin(): boolean {
    return getStoredRole() === 'admin';
}

// ---------------------------------------------------------------------------
// Admin types
// ---------------------------------------------------------------------------
export interface UserRecord {
    id: string;
    username: string;
    email: string | null;
    role: UserRole;
    is_active: boolean;
    created_at: string | null;
}

export interface AuditLogRecord {
    id: number;
    timestamp: string | null;
    user_id: string | null;
    username: string | null;
    action: string;
    resource_type: string | null;
    resource_id: string | null;
    detail: string | null;
    ip_address: string | null;
    status_code: number | null;
    method: string | null;
    path: string | null;
}

export interface FileInput {
    file_path: string;
    file_hash: string;
    file_type: string;
    alias?: string;
}

export interface MultiFileInput {
    files: FileInput[];
    join_keys?: Record<string, string>;
}

export interface ModeSuggestionResponse {
    suggested_mode: AnalysisRequest['mode'];
    detection_method: string;
    confidence: 'high' | 'medium' | 'low';
    explanation: string;
}

export interface AnalysisRequest {
    csv_path?: string;
    db_uri?: string;
    db_query?: string;
    cloud_uri?: string;
    api_url?: string;
    api_headers?: Record<string, string>;
    api_auth?: Record<string, string>;
    json_path?: string;
    mode: 'exploratory' | 'predictive' | 'forecasting' | 'comparative' | 'diagnostic' | 'segmentation' | 'dimensionality_reduction';
    target_column?: string;
    question?: string;
    title?: string;
    dict_path?: string;
    analysis_type?: string;

    use_cache?: boolean;
    multi_file_input?: MultiFileInput;
    exclude_columns?: string[];
}

export interface JobSummary {
    id: string;
    status: string;
    mode: string;
    created_at: string;
    cost_estimate?: {
        total: number;
        currency: string;
    };
    token_usage?: {
        prompt?: number;
        completion?: number;
        total?: number;
        input?: number;
        output?: number;
        [key: string]: number | undefined;
    };
    result_path?: string;
    csv_path?: string;
    error_message?: string;
}
export interface AnalysisResponse {
    job_id: string;
    status: string;
    estimated_cost: number;
    message: string;
}

export const AnalysisAPI = {
    login: async (username: string, password: string) => {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        const response = await api.post('/auth/login', formData, {
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        });
        const data = response.data; // { access_token, token_type, role, username }
        // Persist role and username alongside token
        if (data.role) sessionStorage.setItem('inzyts_user_role', data.role);
        if (data.username) sessionStorage.setItem('inzyts_username', data.username);
        return data;
    },

    getCurrentUser: async () => {
        const response = await api.get('/auth/me');
        return response.data;
    },

    analyze: async (data: AnalysisRequest) => {
        const response = await api.post<AnalysisResponse>('/analyze', data);
        return response.data;
    },

    suggestMode: async (question?: string, targetColumn?: string) => {
        const response = await api.post<ModeSuggestionResponse>('/suggest-mode', {
            question: question || null,
            target_column: targetColumn || null,
        });
        return response.data;
    },

    getJobStatus: async (jobId: string) => {
        const response = await api.get(`/jobs/${encodeURIComponent(jobId)}`);
        return response.data;
    },

    cancelJob: async (jobId: string) => {
        const response = await api.post(`/jobs/${encodeURIComponent(jobId)}/cancel`);
        return response.data;
    },

    uploadFile: async (file: File) => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await api.post('/files/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        return response.data;
    },

    uploadFiles: async (files: File[]) => {
        const formData = new FormData();
        files.forEach((file) => {
            formData.append('files', file);
        });
        const response = await api.post<Array<{ filename: string, saved_path: string, size: number }>>('/files/upload_batch', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        return response.data;
    },

    getJobs: async (skip = 0, limit = 10) => {
        const response = await api.get(`/jobs?skip=${skip}&limit=${limit}`);
        return response.data;
    },

    getFilePreview: async (path: string) => {
        const response = await api.get(`/files/preview?path=${encodeURIComponent(path)}`);
        return response.data;
    },

    testDbConnection: async (dbUri: string) => {
        const response = await api.post<{ status: string; dialect: string; host: string | null; tables: string[] | null; error: string | null }>('/files/db-test', { db_uri: dbUri });
        return response.data;
    },

    previewSqlQuery: async (dbUri: string, query: string) => {
        const response = await api.post('/files/sql-preview', { db_uri: dbUri, query });
        return response.data;
    },

    previewApiEndpoint: async (apiUrl: string, apiHeaders?: Record<string, string>, apiAuth?: Record<string, string>, jsonPath?: string) => {
        const response = await api.post('/files/api-preview', { api_url: apiUrl, api_headers: apiHeaders, api_auth: apiAuth, json_path: jsonPath });
        return response.data;
    },

    getNotebookHtml: async (jobId: string) => {
        const response = await api.get(`/notebooks/${encodeURIComponent(jobId)}/html`);
        return response.data; // { html: string, job_id: string }
    },

    getJupyterToken: async (): Promise<{ token: string }> => {
        const response = await api.get('/notebooks/jupyter-token');
        return response.data;
    },

    getJobMetrics: async (jobId: string) => {
        const response = await api.get(`/metrics/${encodeURIComponent(jobId)}`);
        return response.data;
    },

    getTemplates: async () => {
        const response = await api.get<DomainTemplate[]>('/templates');
        return response.data;
    },

    uploadTemplate: async (file: File) => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await api.post('/templates', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        return response.data;
    },

    deleteTemplate: async (domainName: string) => {
        const response = await api.delete(`/templates/${encodeURIComponent(domainName)}`);
        return response.data;
    },

    downloadNotebook: async (jobId: string) => {
        const response = await api.get(
            `/notebooks/${encodeURIComponent(jobId)}/download`,
            { responseType: 'blob' },
        );
        return response;
    },

    getNotebookCells: async (jobId: string) => {
        const response = await api.get(`/notebooks/${encodeURIComponent(jobId)}/cells`);
        return response.data; // { cells: [...], job_id: string }
    },

    editCell: async (jobId: string, cellIndex: number, currentCode: string, instruction: string) => {
        const response = await api.post(`/notebooks/${encodeURIComponent(jobId)}/cells/edit`, {
            cell_index: cellIndex,
            current_code: currentCode,
            instruction: instruction,
        });
        return response.data; // { new_code, output, images, success, error }
    },

    askFollowUp: async (jobId: string, question: string) => {
        const response = await api.post(`/notebooks/${encodeURIComponent(jobId)}/ask`, { question });
        return response.data; // { summary, cells, success, error, conversation_length }
    },

    getConversationHistory: async (jobId: string) => {
        const response = await api.get(`/notebooks/${encodeURIComponent(jobId)}/conversation`);
        return response.data; // { job_id, messages: [{role, content, cells, created_at}] }
    },

    // --- Report export endpoints ---

    exportReport: async (jobId: string, format: string = 'html', options?: { include_executive_summary?: boolean; include_pii_masking?: boolean }) => {
        if (options) {
            const response = await api.post(
                `/reports/${encodeURIComponent(jobId)}/export`,
                { format, ...options },
                { responseType: 'blob' },
            );
            return response;
        }
        const response = await api.get(
            `/reports/${encodeURIComponent(jobId)}/export`,
            { params: { format }, responseType: 'blob' },
        );
        return response;
    },

    getExecutiveSummary: async (jobId: string) => {
        const response = await api.get(`/reports/${encodeURIComponent(jobId)}/executive-summary`);
        return response.data;
    },

    getPIIScan: async (jobId: string) => {
        const response = await api.get(`/reports/${encodeURIComponent(jobId)}/pii-scan`);
        return response.data;
    },

    // --- Admin endpoints ---

    listUsers: async (skip = 0, limit = 50) => {
        const response = await api.get<UserRecord[]>(`/admin/users?skip=${skip}&limit=${limit}`);
        return response.data;
    },

    createUser: async (data: { username: string; password: string; email?: string; role?: UserRole }) => {
        const response = await api.post<UserRecord>('/admin/users', data);
        return response.data;
    },

    updateUser: async (userId: string, data: { email?: string; role?: string; is_active?: boolean; password?: string }) => {
        const response = await api.put<UserRecord>(`/admin/users/${encodeURIComponent(userId)}`, data);
        return response.data;
    },

    deleteUser: async (userId: string) => {
        await api.delete(`/admin/users/${encodeURIComponent(userId)}`);
    },

    getAuditLogs: async (params?: { skip?: number; limit?: number; username?: string; action?: string; since?: string; until?: string }) => {
        const searchParams = new URLSearchParams();
        if (params) {
            Object.entries(params).forEach(([k, v]) => { if (v != null) searchParams.set(k, String(v)); });
        }
        const response = await api.get<AuditLogRecord[]>(`/admin/audit-logs?${searchParams.toString()}`);
        return response.data;
    },

    getAuditLogsSummary: async () => {
        const response = await api.get<{ actions: Record<string, number> }>('/admin/audit-logs/summary');
        return response.data;
    },
};

// ---------------------------------------------------------------------------
// Command Center types
// ---------------------------------------------------------------------------

export interface PreviousMetrics {
    tokens_used: number | null;
    cost_usd: number | null;
    elapsed_seconds: number | null;
    quality_score: number | null;
}

export interface RunMetrics {
    job_id: string;
    elapsed_seconds: number;
    eta_seconds: number | null;
    tokens_used: number;
    prompt_tokens: number;
    completion_tokens: number;
    cost_usd: number;
    quality_score: number | null;
    agents_active: number;
    agents_total: number;
    previous_job_id: string | null;
    previous: PreviousMetrics | null;
}

export type PipelinePhaseId = 'phase1' | 'extensions' | 'phase2';
export type PhaseStatusValue = 'queued' | 'running' | 'done' | 'failed';

export interface AgentSummary {
    name: string;
    status: PhaseStatusValue;
    started_at: number | null;
    finished_at: number | null;
}

export interface SubStepStatus {
    id: string;
    name: string;
    status: PhaseStatusValue;
    started_at: number | null;
    finished_at: number | null;
    agents: AgentSummary[];
}

export interface PhaseStatus {
    id: PipelinePhaseId;
    name: string;
    status: PhaseStatusValue;
    started_at: number | null;
    finished_at: number | null;
    retries: number;
    steps: SubStepStatus[];
}

export interface PhaseUpdatePayload {
    job_id: string;
    phases: PhaseStatus[];
}

export type ColumnDtype = 'int' | 'float' | 'datetime' | 'category' | 'text' | 'bool';
export type ColumnRole = 'target' | 'time' | 'dim' | 'metric' | 'pii' | 'other';

export interface ColumnStats {
    mean?: number | null;
    median?: number | null;
    min?: number | null;
    max?: number | null;
    p99?: number | null;
}

export interface ColumnProfile {
    name: string;
    dtype: ColumnDtype;
    cardinality_or_range: string;
    role: ColumnRole;
    null_count: number;
    histogram: number[];
    stats: ColumnStats | null;
}

export interface CostBreakdownRow {
    phase: string;
    label: string;
    cost_usd: number;
    prompt_tokens: number;
    completion_tokens: number;
    is_estimate: boolean;
}

export interface CostBreakdownResponse {
    total_cost_usd: number;
    rows: CostBreakdownRow[];
    is_estimate: boolean;
}

// Adds Command Center API methods to AnalysisAPI surface.
export const CommandCenterAPI = {
    getColumns: async (jobId: string): Promise<ColumnProfile[]> => {
        const response = await api.get<ColumnProfile[]>(`/jobs/${encodeURIComponent(jobId)}/columns`);
        return response.data;
    },
    getCost: async (jobId: string): Promise<CostBreakdownResponse> => {
        const response = await api.get<CostBreakdownResponse>(`/jobs/${encodeURIComponent(jobId)}/cost`);
        return response.data;
    },
};

export interface DomainTemplate {
    domain_name: string;
    description: string;
    concepts: Array<{
        name: string;
        description: string;
        regex_patterns: string[];
        synonyms: string[];
    }>;
    recommended_analyses: Array<{
        concept: string;
        analysis_type: string;
        description: string;
        required_columns: string[];
    }>;
    kpis: Array<{
        name: string;
        formula_description: string;
        required_concepts: string[];
    }>;
}
