'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  DEFAULT_TELEMETRY,
  TelemetryData,
  ZoneState,
  calculateHumidityLevel,
  calculateHumidityZones,
  parseTelemetryMessage,
} from '@/lib/telemetry'
import {
  createTelemetrySocket,
  TelemetrySocketCommand,
} from '@/lib/telemetrySocket'

interface UseTelemetryOptions {
  wsUrl?: string
  enableSimulation?: boolean
  simulationInterval?: number
}

export function useTelemetry(options: UseTelemetryOptions = {}) {
  const {
    wsUrl = 'ws://127.0.0.1:8765',
    enableSimulation = true,
    simulationInterval = 1000,
  } = options

  console.log('[Telemetry] Hook inicializado con opciones:', { wsUrl, enableSimulation, simulationInterval })

  const [telemetry, setTelemetry] = useState<TelemetryData>(DEFAULT_TELEMETRY)
  const [isConnected, setIsConnected] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [isSimulating, setIsSimulating] = useState(false)
  
  const socketRef = useRef<ReturnType<typeof createTelemetrySocket> | null>(null)
  const simulationRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Parse WebSocket message from the bridge
  const parseWSMessage = useCallback((data: string) => parseTelemetryMessage(data), [])

  // Simulation for testing
  const startSimulation = useCallback(() => {
    if (simulationRef.current) return
    
    setIsSimulating(true)
    console.log('[Telemetry] Iniciando modo simulacion')
    
    const zonas: readonly ['norte', 'centro', 'sur'] = ['norte', 'centro', 'sur']
    let currentZoneIndex = 0
    
    simulationRef.current = setInterval(() => {
      const currentZone = zonas[currentZoneIndex]
      currentZoneIndex = (currentZoneIndex + 1) % zonas.length
      
      setTelemetry(prev => createSimulationUpdate(prev, zonas))
    }, simulationInterval)
  }, [simulationInterval])

  const stopSimulation = useCallback(() => {
    if (simulationRef.current) {
      clearInterval(simulationRef.current)
      simulationRef.current = null
    }
    setIsSimulating(false)
    console.log('[Telemetry] Simulacion detenida')
  }, [])

  // WebSocket connection
  const connect = useCallback(() => {
    if (socketRef.current) return
    if (typeof window === 'undefined') return

    console.log('[Telemetry] Intentando conectar a WebSocket:', wsUrl)
    try {
      const socket = createTelemetrySocket(wsUrl, {
      onOpen: () => {
        console.log('[Telemetry] WebSocket conectado exitosamente')
        setIsConnected(true)
        setConnectionError(null)
        stopSimulation()
      },
      onMessage: (message) => {
        console.log('[Telemetry] Mensaje recibido:', message)
        const parsed = parseWSMessage(message)
        if (parsed) {
          setTelemetry(prev => ({
            ...prev,
            ...parsed,
            lastSync: Date.now(),
          }))
        }
      },
      onError: (error) => {
        console.error('[Telemetry] Error de WebSocket:', error)
        setConnectionError('Error de conexion')
      },
      onClose: () => {
        console.log('[Telemetry] WebSocket desconectado')
        setIsConnected(false)
        socketRef.current = null

        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
        }

        reconnectTimeoutRef.current = setTimeout(() => {
          if (enableSimulation) {
            startSimulation()
          }
        }, 2000)
      },
    })

    if (socket) {
      socketRef.current = socket
      console.log('[Telemetry] Socket creado')
    } else {
      console.error('[Telemetry] No se pudo crear socket')
    }
    } catch (error) {
      console.error('[Telemetry] Error al crear socket:', error)
      setConnectionError('Error al crear conexion')
    }
  }, [wsUrl, enableSimulation, parseWSMessage, startSimulation, stopSimulation])

  // Send command to drone
  const sendCommand = useCallback((command: TelemetrySocketCommand) => {
    if (socketRef.current) {
      socketRef.current.sendCommand(command)
      console.log('[Telemetry] Comando enviado:', command)
    } else {
      console.warn('[Telemetry] No conectado, comando no enviado')
    }
  }, [])

  const startMission = useCallback((targetZone?: string) => {
    sendCommand({ type: 'start_mission', target_zone: targetZone ?? 'sur' })
    setTelemetry(prev => ({
      ...prev,
      drone: { ...prev.drone, flightStatus: 'ascenso', targetZone: targetZone ?? 'sur' },
    }))
  }, [sendCommand])

  const stopMission = useCallback(() => {
    sendCommand({ type: 'stop_mission' })
    setTelemetry(prev => ({
      ...prev,
      drone: { ...prev.drone, flightStatus: 'retorno' },
    }))
  }, [sendCommand])

  const emergencyStop = useCallback(() => {
    sendCommand({ type: 'emergency_stop' })
    setTelemetry(prev => ({
      ...prev,
      drone: { ...prev.drone, flightStatus: 'descenso' },
    }))
  }, [sendCommand])

  // Initialize
  useEffect(() => {
    console.log('[Telemetry] useEffect ejecutado, enableSimulation:', enableSimulation)
    if (enableSimulation) {
      startSimulation()
    }
    
    const connectionDelay = setTimeout(() => {
      console.log('[Telemetry] Llamando a connect()')
      connect()
    }, 500)
    
    return () => {
      clearTimeout(connectionDelay)
      stopSimulation()
      if (socketRef.current) {
        socketRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return {
    telemetry,
    isConnected,
    isSimulating,
    connectionError,
    startMission,
    stopMission,
    emergencyStop,
    reconnect: connect,
  }
}
