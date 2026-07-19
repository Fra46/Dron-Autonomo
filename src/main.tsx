import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import 'bootstrap/dist/css/bootstrap.min.css'
import './styles/globals.css'
import { registerSW } from 'virtual:pwa-register'

const updateSW = registerSW({
  onOfflineReady() {
    // El service worker ya está listo para funcionar offline.
  },
  onRegistered(registration: ServiceWorkerRegistration | undefined) {
    // Se puede usar la registración para control adicional si es necesario.
  }
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)

export { updateSW }
