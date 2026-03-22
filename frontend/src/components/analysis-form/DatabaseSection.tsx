import type { FC } from 'react';

interface DbTestResult {
    status: string;
    dialect?: string;
    host?: string | null;
    tables?: string[] | null;
    error?: string | null;
}

interface DatabaseSectionProps {
    dbUri: string;
    setDbUri: (v: string) => void;
    dbQuery: string;
    setDbQuery: (v: string) => void;
    dbTestResult: DbTestResult | null;
    setDbTestResult: (v: DbTestResult | null) => void;
    dbTestLoading: boolean;
    onTestConnection: () => void;
}

export const DatabaseSection: FC<DatabaseSectionProps> = ({
    dbUri, setDbUri, dbQuery, setDbQuery,
    dbTestResult, setDbTestResult, dbTestLoading, onTestConnection,
}) => {
    return (
        <div className="flex flex-col gap-4">
            <input
                type="text"
                placeholder="Database URI (e.g. postgresql://user:pass@localhost/db)"
                value={dbUri}
                onChange={(e) => { setDbUri(e.target.value); setDbTestResult(null); }}
                className="w-full p-4 rounded border border-[var(--border-color)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-base"
            />
            <button
                onClick={onTestConnection}
                disabled={!dbUri || dbTestLoading}
                className={`py-2 px-4 bg-[#2d3748] text-white border border-[var(--border-color)] rounded cursor-pointer text-[0.9rem] ${!dbUri ? 'opacity-60' : 'opacity-100'}`}
            >
                {dbTestLoading ? 'Testing...' : 'Test Connection'}
            </button>
            {dbTestResult && (
                <div className={`text-[0.85rem] p-2 rounded ${dbTestResult.status === 'ok' ? 'bg-emerald-900/30 text-emerald-400' : 'bg-red-900/30 text-red-400'}`}>
                    {dbTestResult.status === 'ok' ? (
                        <>Connected to {dbTestResult.dialect}://{dbTestResult.host} — {dbTestResult.tables?.length ?? 0} tables found</>
                    ) : (
                        <>Failed: {dbTestResult.error}</>
                    )}
                </div>
            )}
            <textarea
                placeholder="SQL Query (e.g. SELECT * FROM users) - Leave blank for Autonomous Agent"
                value={dbQuery}
                onChange={(e) => setDbQuery(e.target.value)}
                rows={3}
                className="w-full p-4 rounded border border-[var(--border-color)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-base font-mono"
            />
        </div>
    );
};
