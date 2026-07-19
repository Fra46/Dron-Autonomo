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
          const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
          const host = import.meta.env.VITE_WS_HOST || window.location.hostname
          const preferredPort = import.meta.env.VITE_WS_PORT || '8765'
          const ports = Array.from(new Set([preferredPort, '8765', '8766', '8767', '8768', '8769', '8770']))
          return ports.map(port => `${protocol}://${host}:${port}`)
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
