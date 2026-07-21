import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import 'bootstrap/dist/css/bootstrap.min.css'
import './styles/globals.css'

// Cargar el helper del PWA solo si está disponible (evita errores en dev
// cuando el plugin VitePWA no está registrado).
let updateSW: any = null
if (import.meta.env.PROD) {
  ;(async () => {
      try {
        const modName = 'virtual' + ':pwa-register'
        const dynamicImport = new Function('name', 'return import(name)')
        const mod = await dynamicImport(modName)
        if (mod && typeof mod.registerSW === 'function') {
          updateSW = mod.registerSW({
            onOfflineReady() {
              // El service worker ya está listo para funcionar offline.
            },
            onRegistered(registration: ServiceWorkerRegistration | undefined) {
              // Se puede usar la registración para control adicional si es necesario.
            }
          })
        }
      } catch (e) {
        // Ignore: virtual:pwa-register not present in this environment
      }
  })()
}

const rootElement = document.getElementById('root')!
const app = import.meta.env.PROD ? (
  <React.StrictMode>
    <App />
  </React.StrictMode>
) : (
  <App />
)

ReactDOM.createRoot(rootElement).render(app)

export { updateSW }
