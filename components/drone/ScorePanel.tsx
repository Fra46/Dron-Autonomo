'use client'

import { useState, useEffect } from 'react'
import { Droplets, TrendingUp, TrendingDown, Minus, History, Wifi, WifiOff, MapPin } from 'lucide-react'
import { useTelemetryContext } from '@/contexts/TelemetryContext'

const getHumidityColor = (humidity: number): string => {
  if (humidity < 25) return 'var(--lv0)'
  if (humidity < 40) return 'var(--lv1)'
  if (humidity < 55) return 'var(--lv2)'
  if (humidity < 70) return 'var(--lv3)'
  if (humidity < 85) return 'var(--lv4)'
  return 'var(--lv5)'
}

const getEstadoLabel = (estado: string): string => {
  const labels: Record<string, string> = {
    'humedo': 'Humedo',
    'normal': 'Normal',
    'seco': 'Seco',
    'muy_seco': 'Muy Seco',
  }
  return labels[estado] || estado
}

const getEstadoEmoji = (estado: string): string => {
  const emojis: Record<string, string> = {
    'humedo': '',
    'normal': '',
    'seco': '',
    'muy_seco': '',
  }
  return emojis[estado] || ''
}

export function ScorePanel() {
  const { telemetry, isConnected, isSimulating } = useTelemetryContext()
  const [history, setHistory] = useState<number[]>([48, 49, 47, 45, 48, 51, 48])
  const [trend, setTrend] = useState<'up' | 'down' | 'stable'>('stable')
  
  const currentHumidity = telemetry.averageHumidity
  const { zones, lastReading } = telemetry

  useEffect(() => {
    setHistory(prev => {
      const newHistory = [...prev.slice(-6), currentHumidity]
      
      if (newHistory.length >= 2) {
        const lastValue = newHistory[newHistory.length - 2]
        if (currentHumidity > lastValue + 0.5) {
          setTrend('up')
        } else if (currentHumidity < lastValue - 0.5) {
          setTrend('down')
        } else {
          setTrend('stable')
        }
      }
      
      return newHistory
    })
  }, [currentHumidity])

  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus
  const trendColor = trend === 'up' ? 'text-[var(--lv3)]' : trend === 'down' ? 'text-[var(--lv0)]' : 'text-[var(--foreground-muted)]'

  const maxHistory = Math.max(...history)
  const minHistory = Math.min(...history)
  const range = maxHistory - minHistory || 1

  const trendDiff = history.length >= 2 
    ? Math.abs(currentHumidity - history[history.length - 2])
    : 0

  return (
    <div className="glass rounded-2xl p-6 glow animate-fadeUp-delay-1">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient flex items-center justify-center">
            <Droplets className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-display font-semibold">Nivel de Humedad</h3>
            <span className="text-sm text-[var(--foreground-muted)]">Promedio del terreno</span>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs ${
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
            <span>{isConnected ? 'UDP' : isSimulating ? 'SIM' : 'OFF'}</span>
          </div>
          
          <div className={`flex items-center gap-1 ${trendColor}`}>
            <TrendIcon className="w-4 h-4" />
            <span className="text-sm font-medium">
              {trend === 'up' ? '+' : trend === 'down' ? '-' : ''}
              {trendDiff.toFixed(1)}%
            </span>
          </div>
        </div>
      </div>

      {/* Main Score Display */}
      <div className="text-center mb-6">
        <div className="relative inline-block">
          <span 
            className="text-7xl font-display font-black"
            style={{ color: getHumidityColor(currentHumidity) }}
          >
            {currentHumidity.toFixed(0)}
          </span>
          <span className="text-2xl font-display text-[var(--foreground-muted)] ml-1">%</span>
        </div>
      </div>

      {/* Zone Cards - Norte, Centro, Sur */}
      <div className="grid grid-cols-3 gap-2 mb-6">
        {(['norte', 'centro', 'sur'] as const).map((zoneName) => {
          const zone = zones[zoneName]
          return (
            <div 
              key={zoneName}
              className="p-3 rounded-xl border transition-all"
              style={{ 
                borderColor: getHumidityColor(zone.humedad),
                backgroundColor: `${getHumidityColor(zone.humedad)}10`,
              }}
            >
              <div className="flex items-center gap-1 mb-1">
                <MapPin className="w-3 h-3" style={{ color: getHumidityColor(zone.humedad) }} />
                <span className="text-xs font-medium capitalize">{zoneName}</span>
              </div>
              <div 
                className="text-2xl font-display font-bold"
                style={{ color: getHumidityColor(zone.humedad) }}
              >
                {zone.humedad.toFixed(0)}%
              </div>
              <div className="text-[10px] text-[var(--foreground-muted)]">
                {getEstadoLabel(zone.estado)} {getEstadoEmoji(zone.estado)}
              </div>
              <div className="text-[10px] text-[var(--foreground-subtle)]">
                {zone.temperatura.toFixed(1)}C
              </div>
            </div>
          )
        })}
      </div>

      {/* Last Reading Alert */}
      {lastReading && (
        <div 
          className="p-3 rounded-lg mb-4 flex items-center justify-between"
          style={{ 
            backgroundColor: `${getHumidityColor(lastReading.humedad)}15`,
            borderLeft: `3px solid ${getHumidityColor(lastReading.humedad)}`,
          }}
        >
          <div className="flex items-center gap-2">
            <span 
              className="w-2 h-2 rounded-full animate-pulse"
              style={{ backgroundColor: getHumidityColor(lastReading.humedad) }}
            />
            <span className="text-sm">
              Ultima lectura: <strong className="capitalize">{lastReading.zona}</strong>
            </span>
          </div>
          <span 
            className="text-sm font-bold"
            style={{ color: getHumidityColor(lastReading.humedad) }}
          >
            {lastReading.humedad.toFixed(1)}%
          </span>
        </div>
      )}

      {/* Mini chart */}
      <div className="pt-4 border-t border-[var(--border)]">
        <div className="flex items-center gap-2 mb-3">
          <History className="w-4 h-4 text-[var(--foreground-muted)]" />
          <span className="text-sm text-[var(--foreground-muted)]">Historial reciente</span>
        </div>
        
        <div className="flex items-end justify-between h-16 gap-1">
          {history.map((value, index) => (
            <div 
              key={index}
              className="flex-1 rounded-t-sm transition-all duration-300"
              style={{ 
                height: `${((value - minHistory) / range) * 100}%`,
                minHeight: '4px',
                backgroundColor: getHumidityColor(value),
                opacity: index === history.length - 1 ? 1 : 0.5,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
