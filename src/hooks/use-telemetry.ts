'use client'

import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import {
  DEFAULT_TELEMETRY,
  TelemetryData,
  calculateHumidityLevel,
  parseTelemetryMessage,
} from '@/lib/telemetry'
import {
  createTelemetrySocket,
  TelemetrySocketCommand,
} from '@/lib/telemetrySocket'

interface UseTelemetryOptions {
  wsUrl?: string | string[]
}

export function useTelemetry(options: UseTelemetryOptions = {}) {
  const {
    wsUrl = 'ws://127.0.0.1:8765',
  } = options
  const wsUrls = useMemo(() => Array.isArray(wsUrl) ? wsUrl : [wsUrl], [wsUrl])

  const [telemetry, setTelemetry] = useState<TelemetryData>(DEFAULT_TELEMETRY)
  const [isConnected, setIsConnected] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)

  const socketRef = useRef<ReturnType<typeof createTelemetrySocket> | null>(null)
  const commandQueueRef = useRef<TelemetrySocketCommand[]>([])
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const shouldReconnectRef = useRef(true)
  const connectionAttemptRef = useRef(0)

  // Parse WebSocket message from the bridge
  const parseWSMessage = useCallback((data: string | Record<string, unknown>) => parseTelemetryMessage(data), [])

  // WebSocket connection
  const connect = useCallback(() => {
    if (!shouldReconnectRef.current) return
    if (socketRef.current) return
    if (typeof window === 'undefined') return

    const targetUrl = wsUrls[connectionAttemptRef.current % wsUrls.length]
    console.log('[Telemetry] Intentando conectar a WebSocket:', targetUrl)
    try {
      const socket = createTelemetrySocket(targetUrl, {
        onOpen: () => {
        console.log('[Telemetry] WebSocket conectado exitosamente')
        connectionAttemptRef.current = 0
        setIsConnected(true)
        setConnectionError(null)
        socket?.sendCommand({ type: 'auth' })

        if (commandQueueRef.current.length > 0) {
          console.log('[Telemetry] Enviando comandos encolados:', commandQueueRef.current)
          commandQueueRef.current.forEach(command => socket?.sendCommand(command))
          commandQueueRef.current = []
        }
      },
      onMessage: (message) => {
        console.log('[Telemetry] Mensaje recibido:', message)

        let raw: Record<string, any> | null = null
        try {
          raw = JSON.parse(message)
        } catch {
          raw = null
        }

        const parsed = parseWSMessage(raw ?? message)

        // Latencia real ida-y-vuelta: si este mensaje es el eco directo de un
        // request_status con client_ts, se calcula con el reloj del propio
        // navegador (evita depender de sincronizacion de relojes entre maquinas).
        let latencyUpdate: { pwaLatencyMs: number } | null = null
        let modeFromServer: 'auto' | 'manual' | null = null
        try {
          const rawMessage = raw ?? {}
          if (typeof rawMessage?.pingTs === 'number') {
            latencyUpdate = { pwaLatencyMs: Date.now() - rawMessage.pingTs }
          }
          
          // Solo confiar en el modo del servidor si está explícitamente en el JSON crudo.
          // Esto evita que telemetrías genéricas reseteen el modo a 'auto'.
          if (rawMessage?.drone?.mode === 'manual' || rawMessage?.drone?.modo === 'manual') {
            modeFromServer = 'manual'
          } else if (rawMessage?.drone?.mode === 'auto' || rawMessage?.drone?.modo === 'auto') {
            modeFromServer = 'auto'
          }
        } catch {
          // Mensaje no parseable como JSON crudo; parseWSMessage ya maneja ese caso.
        }

        if (parsed || latencyUpdate) {
          setTelemetry(prev => {
            const SMOOTH_ALPHA = 0.25 // factor de suavizado para humedad (0..1)

            let merged = {
              ...prev,
              ...parsed,
              ...latencyUpdate,
              lastSync: Date.now(),
            }

            // Si el parsed incluye zonas, aplicar suavizado exponencial sobre
            // la humedad para evitar cambios visuales bruscos.
            if (parsed?.zones) {
              const newZones = { ...prev.zones }
              for (const key of ['norte','centro','sur'] as const) {
                const prevHum = prev.zones[key].humedad ?? 0
                const incomingHum = parsed.zones[key]?.humedad ?? prevHum
                const smoothHum = prevHum + (incomingHum - prevHum) * SMOOTH_ALPHA
                const estado = parsed.zones[key]?.estado ?? prev.zones[key].estado
                const temperatura = parsed.zones[key]?.temperatura ?? prev.zones[key].temperatura
                const nivel = calculateHumidityLevel(smoothHum)

                newZones[key] = {
                  humedad: Math.round(smoothHum * 10) / 10,
                  estado: estado,
                  temperatura: temperatura,
                  nivel: nivel as any,
                }
              }

              merged = {
                ...merged,
                zones: newZones,
                humidityZones: parsed.humidityZones ?? prev.humidityZones,
                averageHumidity: typeof parsed.averageHumidity === 'number'
                  ? parsed.averageHumidity
                  : (newZones.norte.humedad + newZones.centro.humedad + newZones.sur.humedad) / 3,
              }
            }

            // Si el servidor envió explícitamente un valor para el modo, actualizarlo.
            // Si no lo envió (modeFromServer === null), preservar el modo actual del usuario.
            if (modeFromServer !== null && merged.drone) {
              merged.drone = {
                ...merged.drone,
                mode: modeFromServer,
              }
            } else if (merged.drone) {
              merged.drone = {
                ...merged.drone,
                mode: prev.drone.mode,
              }
            }

            return merged
          })
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
        console.log('[Telemetry] Conexión cerrada en cliente')

        if (!shouldReconnectRef.current) {
          return
        }

        connectionAttemptRef.current = (connectionAttemptRef.current + 1) % wsUrls.length

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
  }, [wsUrls, parseWSMessage])

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
    sendCommand({ type: 'request_status', client_ts: Date.now() })
  }, [sendCommand])

  const setMode = useCallback((mode: 'auto' | 'manual') => {
    sendCommand({ type: 'set_mode', mode })
    setTelemetry(prev => ({
      ...prev,
      drone: { ...prev.drone, mode },
    }))
  }, [sendCommand])

  // Initialize
  useEffect(() => {
    shouldReconnectRef.current = true
    console.log('[Telemetry] useEffect ejecutado')
    console.log('[Telemetry] Hook inicializado con opciones:', { wsUrl })

    const connectionDelay = setTimeout(() => {
      console.log('[Telemetry] Llamando a connect()')
      connect()
    }, 500)

    return () => {
      shouldReconnectRef.current = false
      clearTimeout(connectionDelay)
      if (socketRef.current) {
        socketRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [connect])

  // Ping periodico para medir latencia real en vivo (panel de TelemetryBar).
  // Solo mientras haya conexion activa, para no encolar comandos inutilmente.
  useEffect(() => {
    if (!isConnected) return
    const pingInterval = setInterval(() => {
      sendCommand({ type: 'request_status', client_ts: Date.now() })
    }, 3000)
    return () => clearInterval(pingInterval)
  }, [isConnected, sendCommand])

  return {
    telemetry,
    isConnected,
    connectionError,
    startMission,
    stopMission,
    emergencyStop,
    requestStatus,
    setMode,
    reconnect: connect,
  }
}
