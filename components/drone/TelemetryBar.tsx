'use client'

import { useState, useEffect } from 'react'
import { Battery, Wifi, WifiOff, Navigation, Droplets, Thermometer, Wind, MapPin } from 'lucide-react'
import { useTelemetryContext } from '@/contexts/TelemetryContext'
import { getBatteryColor, getSignalColor, formatCoord, flightStatusColors, flightStatusLabels } from '@/lib/uiUtils'

export function TelemetryBar() {
  const { telemetry, isConnected, isSimulating, connectionError } = useTelemetryContext()
  const [time, setTime] = useState<string>('')

  useEffect(() => {
    const updateTime = () => {
      setTime(new Date().toLocaleTimeString('es-ES', { 
        hour: '2-digit', 
        minute: '2-digit',
        second: '2-digit'
      }))
    }
    updateTime()
    const interval = setInterval(updateTime, 1000)
    return () => clearInterval(interval)
  }, [])

  return (
    <header className="sticky top-0 z-50 w-full glass-strong animate-fadeUp">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Status */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient flex items-center justify-center">
                <Droplets className="w-5 h-5 text-white" />
              </div>
              <span className="font-display font-bold text-lg hidden sm:block">AgroDrone</span>
            </div>
            
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${flightStatusColors[telemetry.flightStatus]} animate-pulse`} />
              <span className="text-sm font-medium text-[var(--foreground-muted)]">
                {flightStatusLabels[telemetry.flightStatus]}
              </span>
            </div>
            
            {/* UDP Connection Status */}
            <div className={`hidden md:flex items-center gap-1.5 px-2 py-1 rounded-full text-xs ${
              isConnected 
                ? 'bg-[var(--lv3)]/20 text-[var(--lv3)]' 
                : isSimulating 
                  ? 'bg-[var(--lv2)]/20 text-[var(--lv2)]'
                  : 'bg-[var(--lv0)]/20 text-[var(--lv0)]'
            }`}>
              {isConnected ? (
                <Wifi className="w-3 h-3" />
              ) : (
                <WifiOff className="w-3 h-3" />
              )}
              <span>{isConnected ? 'UDP Conectado' : isSimulating ? 'Simulacion' : 'Desconectado'}</span>
            </div>
          </div>

          {/* Telemetry Data */}
          <div className="flex items-center gap-3 sm:gap-6">
            {/* Coordinates */}
            <div className="hidden xl:flex items-center gap-1.5">
              <MapPin className="w-4 h-4 text-[var(--gradient-end)]" />
              <span className="text-xs font-mono text-[var(--foreground-muted)]">
                {formatCoord(telemetry.coordinates.latitude, 'lat')}, {formatCoord(telemetry.coordinates.longitude, 'lng')}
              </span>
            </div>
            
            {/* Battery */}
            <div className="flex items-center gap-1.5">
              <Battery className={`w-4 h-4 ${getBatteryColor(telemetry.battery)}`} />
              <span className={`text-sm font-mono ${getBatteryColor(telemetry.battery)}`}>
                {telemetry.battery.toFixed(0)}%
              </span>
            </div>

            {/* Signal */}
            <div className="flex items-center gap-1.5">
              <Wifi className={`w-4 h-4 ${getSignalColor(telemetry.signal)}`} />
              <span className={`text-sm font-mono ${getSignalColor(telemetry.signal)}`}>
                {telemetry.signal.toFixed(0)}%
              </span>
            </div>

            {/* Altitude */}
            <div className="hidden md:flex items-center gap-1.5">
              <Navigation className="w-4 h-4 text-[var(--lv4)]" />
              <span className="text-sm font-mono text-[var(--foreground-muted)]">
                {telemetry.coordinates.altitude.toFixed(1)}m
              </span>
            </div>

            {/* Temperature */}
            <div className="hidden lg:flex items-center gap-1.5">
              <Thermometer className="w-4 h-4 text-[var(--lv1)]" />
              <span className="text-sm font-mono text-[var(--foreground-muted)]">
                {telemetry.temperature.toFixed(1)}C
              </span>
            </div>

            {/* Wind/Speed */}
            <div className="hidden lg:flex items-center gap-1.5">
              <Wind className="w-4 h-4 text-[var(--foreground-muted)]" />
              <span className="text-sm font-mono text-[var(--foreground-muted)]">
                {telemetry.speed.toFixed(1)} m/s
              </span>
            </div>

            {/* Water Level */}
            <div className="hidden lg:flex items-center gap-1.5">
              <Droplets className="w-4 h-4 text-[var(--lv4)]" />
              <span className="text-sm font-mono text-[var(--foreground-muted)]">
                {telemetry.waterLevel.toFixed(0)}%
              </span>
            </div>

            {/* Time */}
            <div className="text-sm font-mono text-[var(--foreground-subtle)] hidden sm:block">
              {time}
            </div>
          </div>
        </div>
        
        {/* Connection error banner */}
        {connectionError && !isSimulating && (
          <div className="pb-2 -mt-1">
            <div className="text-xs text-center py-1 px-3 rounded bg-[var(--lv0)]/20 text-[var(--lv0)]">
              {connectionError} - Usando datos de simulacion
            </div>
          </div>
        )}
      </div>
    </header>
  )
}
