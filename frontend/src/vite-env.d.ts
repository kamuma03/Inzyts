/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_API_URL?: string;
    readonly VITE_JUPYTER_URL?: string;
    readonly VITE_LLM_MODEL?: string;
    readonly VITE_FEATURE_COMMAND_CENTER?: string;
}

interface ImportMeta {
    readonly env: ImportMetaEnv;
}
