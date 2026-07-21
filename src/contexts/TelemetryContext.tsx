import { createContext, useContext, ReactNode, useEffect } from 'react'
import { useTelemetry } from '@/hooks/use-telemetry'
import type { TelemetryData } from '@/lib/telemetry'

interface TelemetryContextType {
  telemetry: TelemetryData
  isConnected: boolean
  connectionError: string | null
  startMission: (targetZone?: string) => void
  stopMission: () => void
  emergencyStop: () => void
  requestStatus: () => void
  setMode: (mode: 'auto' | 'manual') => void
  reconnect: () => void
}

const TelemetryContext = createContext<TelemetryContextType | null>(null)

export function TelemetryProvider({ children }: { children: ReactNode }) {
  const telemetryState = useTelemetry({
    wsUrl: typeof window !== 'undefined'
      ? (() => {
          const host = import.meta.env.VITE_WS_HOST || window.location.hostname
          const preferred = parseInt(import.meta.env.VITE_WS_PORT || '8765', 10) || 8765
          const explicitProtocol = (import.meta.env.VITE_WS_PROTOCOL as string | undefined)?.toLowerCase() ?? 'ws'
          const protocol = explicitProtocol === 'wss' ? 'wss' : 'ws'
          // Use a single fixed port to avoid port-scanning reconnection issues
          // from the PWA; the bridge listens on 8765 by default.
          return `${protocol}://${host}:${preferred}`
        })()
      : '',
  })

  useEffect(() => {
    console.log('[TelemetryProvider] Inicializando...')
  }, [])

  return (
    <TelemetryContext.Provider value={telemetryState}>
      {children}
    </TelemetryContext.Provider>
  )
}

export function useTelemetryContext() {
  const context = useContext(TelemetryContext)
  if (!context) {
    throw new Error('useTelemetryContext must be used within a TelemetryProvider')
  }
  return context
}
