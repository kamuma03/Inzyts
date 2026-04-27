import React, { useState, useEffect, type FC, type ChangeEvent } from 'react';
import { AnalysisAPI, AnalysisRequest } from '../api';
import { Play, X } from 'lucide-react';
import { Tabs } from './Tabs';
import { useModeSuggestion } from '../hooks/useModeSuggestion';
import { FileUploadSection, DatabaseSection, CloudSection, APISection, ConfigPanel } from './analysis-form';

const DATA_SOURCE_TABS = [
    { id: 'upload', label: 'Upload Files' },
    { id: 'manual', label: 'Manual Path' },
    { id: 'database', label: 'SQL Database' },
    { id: 'cloud', label: 'Cloud Storage' },
    { id: 'api', label: 'REST API' },
];

export interface AnalysisFormInitialValues {
    manualPath?: string;
    dbUri?: string;
    dbQuery?: string;
    mode?: AnalysisRequest['mode'];
    use_cache?: boolean;
    targetCol?: string;
    title?: string;
    question?: string;
    excludeCols?: string;
    dictPath?: string;
}

interface AnalysisFormProps {
    onJobCreated: (jobId: string) => void;
    initialValues?: AnalysisFormInitialValues;
}

export const AnalysisForm: FC<AnalysisFormProps> = ({ onJobCreated, initialValues }) => {
    // Data Source State
    const [files, setFiles] = useState<File[]>([]);
    const [uploadedPaths, setUploadedPaths] = useState<string[]>([]);
    const [uploadedFiles, setUploadedFiles] = useState<Array<{ filename: string; saved_path: string; size: number }>>([]);
    const [manualPath, setManualPath] = useState('');
    const [dictPath, setDictPath] = useState('');
    const [dbUri, setDbUri] = useState('');
    const [dbQuery, setDbQuery] = useState('');

    // Refs
    const fileInputRef = React.useRef<HTMLInputElement>(null);

    // Configuration State
    const [mode, setMode] = useState<AnalysisRequest['mode']>('exploratory');
    const [targetCol, setTargetCol] = useState('');
    const [title, setTitle] = useState('');
    const [question, setQuestion] = useState('');
    const [excludeCols, setExcludeCols] = useState('');
    const [useCache, setUseCache] = useState(false);

    // UI State
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<'upload' | 'manual' | 'database' | 'cloud' | 'api'>('upload');
    const [isDragOver, setIsDragOver] = useState(false);

    // Mode suggestion
    const {
        suggestedMode,
        explanation: suggestionExplanation,
        confidence: suggestionConfidence,
        matchedKeywords: suggestionMatchedKeywords,
    } = useModeSuggestion(question, targetCol);

    // DB Test State
    const [dbTestResult, setDbTestResult] = useState<{ status: string; dialect?: string; host?: string | null; tables?: string[] | null; error?: string | null } | null>(null);
    const [dbTestLoading, setDbTestLoading] = useState(false);

    // Cloud Storage State
    const [cloudUri, setCloudUri] = useState('');

    // API Source State
    const [apiUrl, setApiUrl] = useState('');
    const [apiAuthType, setApiAuthType] = useState<'none' | 'bearer' | 'api_key' | 'basic'>('none');
    const [apiAuthToken, setApiAuthToken] = useState('');
    const [apiKeyName, setApiKeyName] = useState('');
    const [apiKeyValue, setApiKeyValue] = useState('');
    const [apiBasicUser, setApiBasicUser] = useState('');
    const [apiBasicPass, setApiBasicPass] = useState('');
    const [apiHeaders] = useState<Array<{ key: string; value: string }>>([{ key: '', value: '' }]);
    const [jsonPath, setJsonPath] = useState('');

    // Initial Values Effect
    useEffect(() => {
        if (initialValues) {
            if (initialValues.manualPath) { setManualPath(initialValues.manualPath); setActiveTab('manual'); }
            if (initialValues.dbUri) { setDbUri(initialValues.dbUri); setActiveTab('database'); }
            if (initialValues.dbQuery) setDbQuery(initialValues.dbQuery);
            if (initialValues.mode) setMode(initialValues.mode);
            if (initialValues.use_cache) setUseCache(initialValues.use_cache);
            if (initialValues.targetCol) setTargetCol(initialValues.targetCol);
            if (initialValues.title) setTitle(initialValues.title);
            if (initialValues.question) setQuestion(initialValues.question);
            if (initialValues.excludeCols) setExcludeCols(initialValues.excludeCols);
            if (initialValues.dictPath) setDictPath(initialValues.dictPath);
        }
    }, [initialValues]);

    // --- Handlers ---

    const uploadDictFile = async (file: File) => {
        try {
            const resp = await AnalysisAPI.uploadFile(file);
            setDictPath(resp.saved_path);
        } catch (err) {
            console.error("Dict upload failed", err);
            setError("Failed to upload data dictionary. Please try again.");
        }
    };

    const handleDictFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            await uploadDictFile(e.target.files[0]);
        }
    };

    const handleUpload = async () => {
        if (files.length === 0) return;
        setLoading(true);
        setError(null);
        try {
            const uploadResps = await AnalysisAPI.uploadFiles(files);
            const paths = uploadResps.map(r => r.saved_path);
            setUploadedPaths(prev => [...prev, ...paths]);
            setUploadedFiles(prev => [...prev, ...uploadResps]);
            setFiles([]);
            if (fileInputRef.current) fileInputRef.current.value = '';
        } catch (err: any) {
            setError(err.message || 'Upload failed');
        } finally {
            setLoading(false);
        }
    };

    const handleClearFiles = () => {
        setFiles([]);
        setUploadedPaths([]);
        setUploadedFiles([]);
        setError(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    const handleTestDbConnection = async () => {
        if (!dbUri) return;
        setDbTestLoading(true);
        setDbTestResult(null);
        try {
            const result = await AnalysisAPI.testDbConnection(dbUri);
            setDbTestResult(result);
        } catch (err: any) {
            setDbTestResult({ status: 'error', error: err.message || 'Connection test failed' });
        } finally {
            setDbTestLoading(false);
        }
    };

    const buildApiAuth = (): Record<string, string> | undefined => {
        if (apiAuthType === 'bearer') return { type: 'bearer', token: apiAuthToken };
        if (apiAuthType === 'api_key') return { type: 'api_key', key_name: apiKeyName, key_value: apiKeyValue };
        if (apiAuthType === 'basic') return { type: 'basic', username: apiBasicUser, password: apiBasicPass };
        return undefined;
    };

    const buildApiHeaders = (): Record<string, string> | undefined => {
        const h: Record<string, string> = {};
        for (const { key, value } of apiHeaders) {
            if (key.trim()) h[key.trim()] = value;
        }
        return Object.keys(h).length > 0 ? h : undefined;
    };

    const handleSubmit = async () => {
        const finalCsvPath = activeTab === 'upload' ? uploadedPaths[0] : activeTab === 'manual' ? manualPath : undefined;

        // --- Validation ---
        if (activeTab === 'upload' && !finalCsvPath) { setError("Please upload a file first."); return; }

        if (activeTab === 'manual') {
            if (!manualPath) { setError("Please provide a file path."); return; }
            if (manualPath.includes('..')) { setError("Invalid file path: '..' sequences are not allowed."); return; }
            if (!/^[\w\-. /\\]+$/.test(manualPath)) { setError("Invalid file path: Contains disallowed characters."); return; }
        }

        if (activeTab === 'database') {
            if (!dbUri) { setError("Please provide a Database URI."); return; }
            const allowedSchemes = ['postgresql', 'postgres', 'mysql', 'mysql+pymysql', 'mssql', 'bigquery', 'snowflake', 'redshift', 'databricks'];
            try {
                const scheme = dbUri.split('://')[0]?.toLowerCase();
                if (!scheme || !allowedSchemes.some(s => scheme.startsWith(s))) {
                    setError(`Unsupported database scheme. Allowed: ${allowedSchemes.join(', ')}`);
                    return;
                }
            } catch { setError("Invalid database URI format."); return; }
        }

        if (activeTab === 'cloud') {
            if (!cloudUri) { setError("Please provide a cloud storage URI."); return; }
            const allowedCloudSchemes = ['s3', 'gs', 'az', 'abfs', 'abfss'];
            const scheme = cloudUri.split('://')[0]?.toLowerCase();
            if (!scheme || !allowedCloudSchemes.includes(scheme)) {
                setError(`Unsupported cloud scheme. Allowed: ${allowedCloudSchemes.join(', ')}`);
                return;
            }
        }

        if (activeTab === 'api') {
            if (!apiUrl) { setError("Please provide an API URL."); return; }
            if (!apiUrl.startsWith('https://') && !apiUrl.startsWith('http://localhost')) {
                setError("API URL must use HTTPS (except localhost for development).");
                return;
            }
        }

        // Multi-file input
        let multiFileInput = undefined;
        if (activeTab === 'upload' && uploadedPaths.length > 1) {
            multiFileInput = {
                files: uploadedPaths.map((p, i) => ({
                    file_path: p,
                    alias: uploadedFiles[i]?.filename.replace(/\.(csv|parquet|log|xlsx|json)$/i, '') || `file_${i}`,
                    file_hash: uploadedFiles[i] ? `size-${uploadedFiles[i].size}` : "unknown",
                    file_type: "unknown",
                }))
            };
        }

        setLoading(true);
        setError(null);

        try {
            const analysisResp = await AnalysisAPI.analyze({
                csv_path: finalCsvPath || undefined,
                db_uri: activeTab === 'database' ? dbUri : undefined,
                db_query: activeTab === 'database' && dbQuery ? dbQuery : undefined,
                cloud_uri: activeTab === 'cloud' ? cloudUri : undefined,
                api_url: activeTab === 'api' ? apiUrl : undefined,
                api_headers: activeTab === 'api' ? buildApiHeaders() : undefined,
                api_auth: activeTab === 'api' ? buildApiAuth() : undefined,
                json_path: activeTab === 'api' && jsonPath ? jsonPath : undefined,
                mode: mode,
                target_column: targetCol || undefined,
                question: question || undefined,
                title: title || undefined,
                dict_path: dictPath || undefined,
                analysis_type: undefined,
                use_cache: useCache,
                multi_file_input: multiFileInput,
                exclude_columns: excludeCols ? excludeCols.split(',').map(s => s.trim()).filter(Boolean) : undefined
            });
            onJobCreated(analysisResp.job_id);
        } catch (err: any) {
            setError(err.message || 'Failed to start analysis');
        } finally {
            setLoading(false);
        }
    };

    // --- Render data source panel based on active tab ---
    const renderDataSource = () => {
        switch (activeTab) {
            case 'upload':
                return (
                    <FileUploadSection
                        files={files} setFiles={setFiles}
                        uploadedPaths={uploadedPaths} uploadedFiles={uploadedFiles}
                        loading={loading} isDragOver={isDragOver} setIsDragOver={setIsDragOver}
                        fileInputRef={fileInputRef} setError={setError}
                        onUpload={handleUpload} onClearFiles={handleClearFiles}
                    />
                );
            case 'manual':
                return (
                    <input
                        type="text"
                        placeholder="/absolute/path/to/data.csv"
                        value={manualPath}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => { setManualPath(e.target.value); setUploadedPaths([e.target.value]); }}
                        className="w-full p-4 rounded border border-[var(--border-color)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-base"
                    />
                );
            case 'database':
                return (
                    <DatabaseSection
                        dbUri={dbUri} setDbUri={setDbUri}
                        dbQuery={dbQuery} setDbQuery={setDbQuery}
                        dbTestResult={dbTestResult} setDbTestResult={setDbTestResult}
                        dbTestLoading={dbTestLoading} onTestConnection={handleTestDbConnection}
                    />
                );
            case 'cloud':
                return <CloudSection cloudUri={cloudUri} setCloudUri={setCloudUri} />;
            case 'api':
                return (
                    <APISection
                        apiUrl={apiUrl} setApiUrl={setApiUrl}
                        apiAuthType={apiAuthType} setApiAuthType={setApiAuthType}
                        apiAuthToken={apiAuthToken} setApiAuthToken={setApiAuthToken}
                        apiKeyName={apiKeyName} setApiKeyName={setApiKeyName}
                        apiKeyValue={apiKeyValue} setApiKeyValue={setApiKeyValue}
                        apiBasicUser={apiBasicUser} setApiBasicUser={setApiBasicUser}
                        apiBasicPass={apiBasicPass} setApiBasicPass={setApiBasicPass}
                        jsonPath={jsonPath} setJsonPath={setJsonPath}
                    />
                );
            default:
                return null;
        }
    };

    return (
        <div className="p-5 bg-[var(--bg-true-cobalt)] border border-[var(--border-color)] rounded-lg mb-4 shadow-[0_1px_3px_rgba(0,0,0,0.3)] h-full flex flex-col">
            <div className="flex items-center gap-4 mb-4">
                <h3 className="m-0 text-[var(--text-primary)] text-[1.2rem] shrink-0">New Analysis</h3>
                <input
                    type="text"
                    value={title}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setTitle(e.target.value)}
                    placeholder="Title (optional)"
                    className="flex-1 py-2 px-3 rounded border border-[var(--border-color)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-[0.85rem]"
                />
            </div>

            <div className="flex flex-col gap-4 flex-1 overflow-y-auto">
                <Tabs
                    tabs={DATA_SOURCE_TABS}
                    activeTab={activeTab}
                    onSelect={(id) => setActiveTab(id as typeof activeTab)}
                    ariaLabel="Data source selection"
                />

                {/* Data Source Panel */}
                <div className="p-2 bg-[rgba(0,0,0,0.2)] rounded-lg border border-dashed border-[var(--border-color)]">
                    {renderDataSource()}
                </div>

                {/* Configuration */}
                <ConfigPanel
                    dictPath={dictPath} onDictFileChange={handleDictFileChange}
                    onDictFileDrop={uploadDictFile} onDictClear={() => setDictPath('')}
                    targetCol={targetCol} setTargetCol={setTargetCol}
                    excludeCols={excludeCols} setExcludeCols={setExcludeCols}
                    mode={mode} setMode={setMode}
                    suggestedMode={suggestedMode} suggestionExplanation={suggestionExplanation}
                    suggestionConfidence={suggestionConfidence}
                    suggestionMatchedKeywords={suggestionMatchedKeywords}
                    question={question} setQuestion={setQuestion}
                    useCache={useCache} setUseCache={setUseCache}
                />

                <div className="flex-1"></div>

                <button
                    onClick={handleSubmit}
                    disabled={loading}
                    className="py-3 px-6 bg-[var(--bg-french-blue)] text-white font-bold text-base border-none rounded-lg cursor-pointer flex justify-center items-center gap-3 shadow-[0_4px_6px_rgba(0,0,0,0.2)] transition-[transform,box-shadow] duration-100 hover:-translate-y-px hover:shadow-[0_6px_12px_rgba(0,0,0,0.3)]"
                >
                    {loading ? 'Processing...' : <><Play size={20} /> START ANALYSIS</>}
                </button>

                {error && (
                    <div className="text-[#fc8181] py-2 px-3 bg-[rgba(245,101,101,0.1)] border border-[rgba(245,101,101,0.3)] rounded-md flex items-center justify-between text-[0.85rem]">
                        <span>{error}</span>
                        <button onClick={() => setError(null)} className="bg-none border-none text-[#fc8181] cursor-pointer pl-2">
                            <X size={14} />
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};
