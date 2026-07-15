'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  DEFAULT_TELEMETRY,
  TelemetryData,
  parseTelemetryMessage,
} from '@/lib/telemetry'
import {
  createTelemetrySocket,
  TelemetrySocketCommand,
} from '@/lib/telemetrySocket'

interface UseTelemetryOptions {
  wsUrl?: string
}

export function useTelemetry(options: UseTelemetryOptions = {}) {
  const {
    wsUrl = 'ws://127.0.0.1:8765',
  } = options

  console.log('[Telemetry] Hook inicializado con opciones:', { wsUrl })

  const [telemetry, setTelemetry] = useState<TelemetryData>(DEFAULT_TELEMETRY)
  const [isConnected, setIsConnected] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)

  const socketRef = useRef<ReturnType<typeof createTelemetrySocket> | null>(null)
  const commandQueueRef = useRef<TelemetrySocketCommand[]>([])
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Parse WebSocket message from the bridge
  const parseWSMessage = useCallback((data: string) => parseTelemetryMessage(data), [])

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


        if (commandQueueRef.current.length > 0) {
          console.log('[Telemetry] Enviando comandos encolados:', commandQueueRef.current)
          commandQueueRef.current.forEach(command => socketRef.current?.sendCommand(command))
          commandQueueRef.current = []
        }
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
          console.log('[Telemetry] Reintentando conectar después de cierre')
          connect()
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
  }, [wsUrl, parseWSMessage])

  // Send command to drone
  const sendCommand = useCallback((command: TelemetrySocketCommand) => {
    if (socketRef.current) {
      const sent = socketRef.current.sendCommand(command)
      if (sent) {
        console.log('[Telemetry] Comando enviado:', command)
        return
      }

      console.warn('[Telemetry] Socket no abierto, encolando comando:', command)
      commandQueueRef.current.push(command)

      const readyState = socketRef.current.readyState()
      if (readyState === WebSocket.CLOSED || readyState === WebSocket.CLOSING) {
        socketRef.current = null
      }

      connect()
      return
    }

    console.warn('[Telemetry] No conectado, encolando comando:', command)
    commandQueueRef.current.push(command)
    connect()
  }, [connect])

  const startMission = useCallback((targetZone?: string) => {
    const zone = targetZone ?? 'sur'
    sendCommand({ type: 'start_mission', target_zone: zone })
    setTelemetry(prev => ({
      ...prev,
      drone: { ...prev.drone, flightStatus: 'ascenso', targetZone: zone },
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

  const requestStatus = useCallback(() => {
    sendCommand({ type: 'request_status' })
  }, [sendCommand])

  // Initialize
  useEffect(() => {
    console.log('[Telemetry] useEffect ejecutado')

    const connectionDelay = setTimeout(() => {
      console.log('[Telemetry] Llamando a connect()')
      connect()
    }, 500)

    return () => {
      clearTimeout(connectionDelay)
      if (socketRef.current) {
        socketRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [connect])

  return {
    telemetry,
    isConnected,
    connectionError,
    startMission,
    stopMission,
    emergencyStop,
    requestStatus,
    reconnect: connect,
  }
}
