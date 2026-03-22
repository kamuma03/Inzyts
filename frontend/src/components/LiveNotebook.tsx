import React, { useState, useEffect, useRef } from 'react';
import { AnalysisAPI } from '../api';

interface LiveNotebookProps {
    jobId: string;
    resultPath?: string | null;
}

export const LiveNotebook: React.FC<LiveNotebookProps> = ({ resultPath }) => {
    const [kernelStatus, setKernelStatus] = useState<'connecting' | 'connected' | 'error' | 'authenticating'>('authenticating');
    const [token, setToken] = useState<string | null>(null);
    const formRef = useRef<HTMLFormElement>(null);

    // Fetch token securely from authenticated backend
    useEffect(() => {
        const fetchToken = async () => {
             try {
                 const res = await AnalysisAPI.getJupyterToken();
                 setToken(res.token);
                 setKernelStatus('connecting');
             } catch (e) {
                 setKernelStatus('error');
             }
        };
        fetchToken();
    }, []);

    useEffect(() => {
        if (!token) return;

        const checkConnection = async () => {
            try {
                // Determine if we can reach Jupyter directly
                const jupyterBase = import.meta.env.VITE_JUPYTER_URL?.replace('/lab', '') || 'http://localhost:8888';
                const response = await fetch(`${jupyterBase}/api/status`, {
                    headers: { 'Authorization': `token ${token}` }
                });
                if (response.ok) {
                    setKernelStatus('connected');
                    // Once connected, authenticate the iframe by submitting the token
                    if (formRef.current) {
                        formRef.current.submit();
                    }
                } else {
                    setKernelStatus('error');
                }
            } catch (e) {
                setKernelStatus('error');
            }
        };

        checkConnection();
    }, [token]);

    if (kernelStatus === 'error') {
        return (
            <div className="p-8 text-center text-red-500">
                Could not connect to Live Jupyter Server. Ensure the container is running and tokens match.
            </div>
        );
    }

    if (kernelStatus === 'authenticating' || kernelStatus === 'connecting') {
        return (
             <div className="p-8 text-center text-gray-500">
                Locating execution environment...
            </div>
        );
    }

    const baseUrl = import.meta.env.VITE_JUPYTER_URL || 'http://localhost:8888/lab';
    const targetPath = resultPath || '';
    const nextUrl = targetPath ? `/lab/tree/${targetPath}` : '/lab';
    // Jupyter allows logging in by sending POST to /login with password=token
    const loginUrl = `${baseUrl.replace('/lab', '')}/login?next=${encodeURIComponent(nextUrl)}`;

    return (
        <div className="w-full h-[800px] flex flex-col">
            <div className="bg-gray-100 p-2 text-sm text-gray-600 border-b flex justify-between items-center">
                <span>🟢 Live Execution Environment</span>
                <button onClick={() => formRef.current?.submit()} className="text-blue-500 hover:underline bg-transparent border-none cursor-pointer">
                    Reload Environment ↻
                </button>
            </div>
            <iframe
                name="jupyter-iframe"
                width="100%"
                height="100%"
                className="border-none"
                title="Live Jupyter Environment"
                allow="clipboard-read; clipboard-write; scripts"
            />
            {token && (
                 <form target="jupyter-iframe" action={loginUrl} method="POST" ref={formRef} className="hidden">
                     <input type="hidden" name="password" value={token} />
                 </form>
            )}
        </div>
    );
};
