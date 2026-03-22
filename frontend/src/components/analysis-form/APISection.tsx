import type { FC } from 'react';

type AuthType = 'none' | 'bearer' | 'api_key' | 'basic';

interface APISectionProps {
    apiUrl: string;
    setApiUrl: (v: string) => void;
    apiAuthType: AuthType;
    setApiAuthType: (v: AuthType) => void;
    apiAuthToken: string;
    setApiAuthToken: (v: string) => void;
    apiKeyName: string;
    setApiKeyName: (v: string) => void;
    apiKeyValue: string;
    setApiKeyValue: (v: string) => void;
    apiBasicUser: string;
    setApiBasicUser: (v: string) => void;
    apiBasicPass: string;
    setApiBasicPass: (v: string) => void;
    jsonPath: string;
    setJsonPath: (v: string) => void;
}

const AUTH_OPTIONS: { value: AuthType; label: string }[] = [
    { value: 'none', label: 'None' },
    { value: 'bearer', label: 'Bearer' },
    { value: 'api_key', label: 'API Key' },
    { value: 'basic', label: 'Basic' },
];

export const APISection: FC<APISectionProps> = ({
    apiUrl, setApiUrl, apiAuthType, setApiAuthType,
    apiAuthToken, setApiAuthToken, apiKeyName, setApiKeyName,
    apiKeyValue, setApiKeyValue, apiBasicUser, setApiBasicUser,
    apiBasicPass, setApiBasicPass, jsonPath, setJsonPath,
}) => {
    return (
        <div className="flex flex-col gap-4">
            <input
                type="text"
                placeholder="API URL (e.g. https://api.example.com/v1/data)"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                className="w-full p-4 rounded border border-[var(--border-color)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-base"
            />
            <div className="flex gap-2 flex-wrap">
                <label className="text-[0.85rem] text-[var(--text-secondary)] mr-2 self-center">Auth:</label>
                {AUTH_OPTIONS.map(({ value, label }) => (
                    <button key={value} type="button" onClick={() => setApiAuthType(value)}
                        className={`py-[0.35rem] px-3 rounded border cursor-pointer text-[0.85rem] ${apiAuthType === value ? 'border-[var(--bg-turquoise-surf)] bg-[rgba(56,178,172,0.15)] text-[var(--bg-turquoise-surf)]' : 'border-[var(--border-color)] bg-transparent text-[var(--text-secondary)]'}`}>
                        {label}
                    </button>
                ))}
            </div>
            {apiAuthType === 'bearer' && (
                <input type="password" placeholder="Bearer Token" value={apiAuthToken} onChange={(e) => setApiAuthToken(e.target.value)}
                    className="w-full p-3 rounded border border-[var(--border-color)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)]" />
            )}
            {apiAuthType === 'api_key' && (
                <div className="flex gap-2">
                    <input type="text" placeholder="Header Name (e.g. X-API-Key)" value={apiKeyName} onChange={(e) => setApiKeyName(e.target.value)}
                        className="flex-1 p-3 rounded border border-[var(--border-color)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)]" />
                    <input type="password" placeholder="API Key Value" value={apiKeyValue} onChange={(e) => setApiKeyValue(e.target.value)}
                        className="flex-1 p-3 rounded border border-[var(--border-color)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)]" />
                </div>
            )}
            {apiAuthType === 'basic' && (
                <div className="flex gap-2">
                    <input type="text" placeholder="Username" value={apiBasicUser} onChange={(e) => setApiBasicUser(e.target.value)}
                        className="flex-1 p-3 rounded border border-[var(--border-color)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)]" />
                    <input type="password" placeholder="Password" value={apiBasicPass} onChange={(e) => setApiBasicPass(e.target.value)}
                        className="flex-1 p-3 rounded border border-[var(--border-color)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)]" />
                </div>
            )}
            <input
                type="text"
                placeholder="JMESPath to extract data (e.g. data.results, items[*])"
                value={jsonPath}
                onChange={(e) => setJsonPath(e.target.value)}
                className="w-full p-3 rounded border border-[var(--border-color)] bg-[rgba(0,0,0,0.2)] text-[var(--text-primary)] text-[0.9rem]"
            />
            <div className="text-[0.8rem] text-[var(--text-secondary)]">
                The API agent will fetch data, handle pagination, and convert JSON responses to tabular format for analysis.
            </div>
        </div>
    );
};
