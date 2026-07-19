/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

declare module '*.css';
declare module '*.scss';
declare module '*.sass';
declare module '*.less';
declare module '*.styl';

declare module 'virtual:pwa-register' {
  interface RegisterSWOptions {
    onOfflineReady?: () => void
    onRegistered?: (registration: ServiceWorkerRegistration | undefined) => void
    onRegisterError?: (error: Error) => void
  }

  export function registerSW(options?: RegisterSWOptions): () => void
}
