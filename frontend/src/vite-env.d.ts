/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_API_URL?: string;
    readonly VITE_JUPYTER_URL?: string;
    readonly VITE_LLM_MODEL?: string;
}

interface ImportMeta {
    readonly env: ImportMetaEnv;
}
