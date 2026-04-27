'use client'

import { useState } from 'react'
import { Play, Square, RotateCcw, Settings, Volume2, VolumeX, Droplets, MapPin, AlertTriangle } from 'lucide-react'
import { useTelemetryContext } from '@/contexts/TelemetryContext'

export function MissionControl() {
  const { telemetry, startMission, stopMission, emergencyStop, isConnected, isSimulating } = useTelemetryContext()
  const [soundEnabled, setSoundEnabled] = useState(true)
  const [showSettings, setShowSettings] = useState(false)
  const [selectedZone, setSelectedZone] = useState<'norte' | 'centro' | 'sur'>('sur')

  const { drone, zones } = telemetry
  const isFlying = drone.flightStatus !== 'idle'
  const isIrrigating = drone.flightStatus === 'regando'

  // Find most critical zone
  const getCriticalZone = () => {
    let mostCritical: 'norte' | 'centro' | 'sur' = 'sur'
    let lowestHumidity = 100
    
    for (const [name, data] of Object.entries(zones) as Array<['norte' | 'centro' | 'sur', typeof zones.norte]>) {
      if (data.humedad < lowestHumidity) {
        lowestHumidity = data.humedad
        mostCritical = name
      }
    }
    return mostCritical
  }

  const handleStartMission = () => {
    const targetZone = zones[selectedZone].estado === 'muy_seco' || zones[selectedZone].estado === 'seco'
      ? selectedZone
      : getCriticalZone()
    startMission(targetZone)
  }

  const handleEmergencyStop = () => {
    emergencyStop()
  }

  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      idle: 'En espera',
      ascenso: 'Ascendiendo',
      navegando: 'Navegando',
      regando: 'Regando',
      retorno: 'Regresando',
      descenso: 'Descendiendo',
    }
    return labels[status] || status
  }

  const getStatusColor = (status: string) => {
    if (status === 'idle') return 'var(--foreground-subtle)'
    if (status === 'regando') return 'var(--lv4)'
    if (status === 'retorno' || status === 'descenso') return 'var(--lv2)'
    return 'var(--lv3)'
  }

  return (
    <div className="glass rounded-2xl p-6 animate-fadeUp-delay-4">
      <div className="flex items-center justify-between mb-6">
        <h3 className="font-display font-semibold text-lg">Control de Mision</h3>
        <div className="flex items-center gap-2">
          {/* Connection indicator */}
          <div className={`px-2 py-1 rounded-full text-xs flex items-center gap-1 ${
            isConnected 
              ? 'bg-[var(--lv3)]/20 text-[var(--lv3)]'
              : isSimulating
                ? 'bg-[var(--lv2)]/20 text-[var(--lv2)]'
                : 'bg-[var(--lv0)]/20 text-[var(--lv0)]'
          }`}>
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{
              backgroundColor: isConnected ? 'var(--lv3)' : isSimulating ? 'var(--lv2)' : 'var(--lv0)'
            }} />
            {isConnected ? 'UDP' : isSimulating ? 'SIM' : 'OFF'}
          </div>
          
          <button 
            onClick={() => setSoundEnabled(!soundEnabled)}
            className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-foreground hover:bg-[var(--bg-elevated)] transition-colors"
          >
            {soundEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
          </button>
          <button 
            onClick={() => setShowSettings(!showSettings)}
            className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-foreground hover:bg-[var(--bg-elevated)] transition-colors"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Zone Selection (only when not flying) */}
      {!isFlying && (
        <div className="mb-4">
          <span className="text-sm text-[var(--foreground-muted)] mb-2 block">Zona objetivo:</span>
          <div className="grid grid-cols-3 gap-2">
            {(['norte', 'centro', 'sur'] as const).map((zoneName) => {
              const zone = zones[zoneName]
              const isCritical = zone.estado === 'muy_seco' || zone.estado === 'seco'
              const isSelected = selectedZone === zoneName
              
              return (
                <button
                  key={zoneName}
                  onClick={() => setSelectedZone(zoneName)}
                  className={`p-3 rounded-xl border-2 transition-all ${
                    isSelected ? 'scale-105' : 'opacity-70 hover:opacity-100'
                  }`}
                  style={{
                    borderColor: isSelected 
                      ? isCritical ? 'var(--lv0)' : 'var(--lv3)'
                      : 'var(--border)',
                    backgroundColor: isSelected
                      ? isCritical ? 'var(--lv0)10' : 'var(--lv3)10'
                      : 'var(--bg-elevated)',
                  }}
                >
                  <div className="flex items-center gap-1 mb-1">
                    <MapPin className="w-3 h-3" />
                    <span className="text-xs font-medium capitalize">{zoneName}</span>
                  </div>
                  <div className="text-lg font-bold" style={{
                    color: isCritical ? 'var(--lv0)' : 'var(--foreground)'
                  }}>
                    {zone.humedad.toFixed(0)}%
                  </div>
                  <div className="text-[10px] text-[var(--foreground-muted)] capitalize">
                    {zone.estado.replace('_', ' ')}
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Main Action Button */}
      <button
        onClick={isFlying ? stopMission : handleStartMission}
        className={`
          w-full py-5 px-6 rounded-xl font-display font-bold text-xl
          flex items-center justify-center gap-3
          transition-all duration-300 transform
          ${isFlying 
            ? 'bg-[var(--lv0)] hover:bg-[var(--lv0)]/80 text-white' 
            : 'bg-gradient hover:scale-[1.02] text-white animate-pulse-glow'
          }
          active:scale-[0.98]
        `}
      >
        {isFlying ? (
          <>
            <Square className="w-6 h-6" />
            Detener Mision
          </>
        ) : (
          <>
            <Play className="w-6 h-6" />
            Iniciar Mision Autonoma
          </>
        )}
      </button>

      {/* Emergency Stop when flying */}
      {isFlying && (
        <button
          onClick={handleEmergencyStop}
          className="w-full mt-3 py-3 px-6 rounded-xl font-medium flex items-center justify-center gap-2 bg-[var(--lv0)]/20 text-[var(--lv0)] hover:bg-[var(--lv0)]/30 transition-all border border-[var(--lv0)]/40"
        >
          <AlertTriangle className="w-5 h-5" />
          Parada de Emergencia
        </button>
      )}

      {/* Status indicator */}
      <div className="mt-4 flex items-center justify-center gap-2">
        <span 
          className="w-2 h-2 rounded-full animate-pulse"
          style={{ backgroundColor: getStatusColor(drone.flightStatus) }}
        />
        <span className="text-sm text-[var(--foreground-muted)]">
          {getStatusLabel(drone.flightStatus)}
          {drone.targetZone && isFlying && (
            <span className="ml-1">
              - Zona <strong className="capitalize">{drone.targetZone}</strong>
            </span>
          )}
        </span>
      </div>

      {/* Telemetry summary when flying */}
      {isFlying && (
        <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
          <div className="bg-[var(--bg-elevated)] rounded-lg p-2 text-center">
            <span className="text-[var(--foreground-subtle)]">Bateria</span>
            <div className="font-mono font-bold" style={{ 
              color: drone.battery > 50 ? 'var(--lv3)' : drone.battery > 20 ? 'var(--lv2)' : 'var(--lv0)' 
            }}>
              {drone.battery.toFixed(0)}%
            </div>
          </div>
          <div className="bg-[var(--bg-elevated)] rounded-lg p-2 text-center">
            <span className="text-[var(--foreground-subtle)]">Agua</span>
            <div className="font-mono font-bold" style={{ 
              color: drone.waterLevel > 50 ? 'var(--lv4)' : drone.waterLevel > 20 ? 'var(--lv2)' : 'var(--lv0)' 
            }}>
              {drone.waterLevel.toFixed(0)}%
            </div>
          </div>
        </div>
      )}

      {/* Settings panel */}
      {showSettings && (
        <div className="mt-6 pt-6 border-t border-[var(--border)] animate-fadeUp">
          <h4 className="text-sm font-medium text-[var(--foreground-muted)] mb-4">Configuracion rapida</h4>
          
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm">Altura de vuelo</span>
              <span className="text-sm font-mono text-[var(--foreground-muted)]">1.0m</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Tolerancia XY</span>
              <span className="text-sm font-mono text-[var(--foreground-muted)]">0.15m</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Tiempo de riego</span>
              <span className="text-sm font-mono text-[var(--foreground-muted)]">10s</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Puerto UDP</span>
              <span className="text-sm font-mono text-[var(--foreground-muted)]">5005</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Puerto WebSocket</span>
              <span className="text-sm font-mono text-[var(--foreground-muted)]">8765</span>
            </div>
          </div>
          
          <button className="w-full mt-4 py-2 px-4 rounded-lg border border-[var(--border)] text-sm text-[var(--foreground-muted)] hover:text-foreground hover:bg-[var(--bg-elevated)] transition-colors flex items-center justify-center gap-2">
            <RotateCcw className="w-4 h-4" />
            Restablecer valores
          </button>
        </div>
      )}
    </div>
  )
}
