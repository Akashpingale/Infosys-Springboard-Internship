/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Where the FastAPI backend is reachable. Set in .env.local; never holds a secret. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
