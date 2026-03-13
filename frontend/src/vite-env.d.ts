/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_API_URL: string
}

interface ImportMeta {
    readonly env: ImportMetaEnv
}

declare const __APP_BUILD_COMMIT__: string
declare const __APP_BUILD_DATE__: string
declare const __APP_BUILD_VERSION__: string
