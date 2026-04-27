'use client'

import { createContext, useContext, ReactNode } from 'react'
import { useTelemetry } from '@/hooks/use-telemetry'
import type { TelemetryData } from '@/lib/telemetry'

interface TelemetryContextType {
  telemetry: TelemetryData
  isConnected: boolean
  isSimulating: boolean
  connectionError: string | null
  startMission: (targetZone?: string) => void
  stopMission: () => void
  emergencyStop: () => void
  reconnect: () => void
}

const TelemetryContext = createContext<TelemetryContextType | null>(null)

export function TelemetryProvider({ children }: { children: ReactNode }) {
  console.log('[TelemetryProvider] Inicializando...')
  const telemetryState = useTelemetry({
    wsUrl: typeof window !== 'undefined' ? 'ws://localhost:8765' : '',
    enableSimulation: false, // Temporarily disable simulation
    simulationInterval: 1000,
  })

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
