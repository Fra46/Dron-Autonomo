'use client'

import { useMemo } from 'react'
import { Zap, Target, Clock, CheckCircle2, AlertTriangle, MapPin, Thermometer } from 'lucide-react'
import { useTelemetryContext } from '@/contexts/TelemetryContext'

type IrrigationType = 'strategic' | 'opportune'

export function BigScoreSummary() {
  const { telemetry } = useTelemetryContext()
  
  const { averageHumidity, humidityZones, drone, zones } = telemetry
  
  // Calculate irrigation recommendation based on telemetry data
  const irrigationAnalysis = useMemo(() => {
    const criticalZones = humidityZones.lv0 + humidityZones.lv1
    const totalZones = Object.values(humidityZones).reduce((sum, count) => sum + count, 0)
    
    // Find which zone is most critical
    let mostCriticalZone: string | null = null
    let lowestHumidity = 100
    
    for (const [zoneName, zoneData] of Object.entries(zones)) {
      if (zoneData.humedad < lowestHumidity) {
        lowestHumidity = zoneData.humedad
        mostCriticalZone = zoneName
      }
    }
    
    // Determine if irrigation is strategic (urgent) or opportunistic (preventive)
    const type: IrrigationType = averageHumidity < 50 || criticalZones > 0 
      ? 'strategic' 
      : 'opportune'
    
    // Calculate confidence based on data consistency
    const confidence = Math.min(99, Math.max(60, 
      85 + (totalZones > 0 ? 10 : 0) - (criticalZones * 2)
    ))
    
    // Calculate areas that need irrigation
    const areasToIrrigate = criticalZones + Math.floor(humidityZones.lv2 / 2)
    
    // Calculate next optimal irrigation window
    const now = new Date()
    const optimalHour = averageHumidity < 40 ? 0 : averageHumidity < 60 ? 2 : 4
    const nextWindow = new Date(now.getTime() + optimalHour * 60 * 60 * 1000)
    const windowTime = nextWindow.toLocaleTimeString('es-ES', { 
      hour: '2-digit', 
      minute: '2-digit' 
    })
    
    return {
      type,
      confidence,
      nextWindow: optimalHour === 0 ? 'AHORA' : windowTime,
      areasToIrrigate: Math.max(1, areasToIrrigate),
      criticalZones,
      isUrgent: type === 'strategic' && criticalZones > 0,
      mostCriticalZone,
      lowestHumidity,
    }
  }, [averageHumidity, humidityZones, zones])

  const isStrategic = irrigationAnalysis.type === 'strategic'
  const isIrrigating = drone.flightStatus === 'regando'

  return (
    <div className="glass rounded-2xl p-6 glow-accent animate-fadeUp-delay-3 overflow-hidden relative">
      {/* Background glow effect */}
      <div 
        className="absolute inset-0 opacity-10"
        style={{
          background: isStrategic 
            ? 'radial-gradient(circle at 30% 50%, var(--gradient-start), transparent 70%)'
            : 'radial-gradient(circle at 70% 50%, var(--lv3), transparent 70%)',
        }}
      />
      
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            {isStrategic ? (
              <div className="w-10 h-10 rounded-xl bg-gradient flex items-center justify-center animate-pulse-glow">
                <Zap className="w-5 h-5 text-white" />
              </div>
            ) : (
              <div className="w-10 h-10 rounded-xl bg-[var(--lv3)] flex items-center justify-center">
                <Target className="w-5 h-5 text-white" />
              </div>
            )}
            <div>
              <h3 className="font-display font-semibold">Recomendacion de Riego</h3>
              <span className="text-sm text-[var(--foreground-muted)]">
                Analisis en tiempo real via UDP
              </span>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            {/* Drone status indicator */}
            {drone.flightStatus !== 'idle' && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--lv4)]/20">
                <span className="w-2 h-2 rounded-full bg-[var(--lv4)] animate-pulse" />
                <span className="text-sm font-mono text-[var(--lv4)] capitalize">{drone.flightStatus}</span>
              </div>
            )}
            
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--bg-elevated)]">
              <CheckCircle2 className="w-4 h-4 text-[var(--lv3)]" />
              <span className="text-sm font-mono">{irrigationAnalysis.confidence.toFixed(0)}%</span>
            </div>
          </div>
        </div>

        {/* Urgent alert with target zone */}
        {irrigationAnalysis.isUrgent && (
          <div 
            className="mb-6 p-4 rounded-xl flex items-center gap-3 animate-pulse"
            style={{ backgroundColor: 'var(--lv0)15', border: '1px solid var(--lv0)40' }}
          >
            <AlertTriangle className="w-5 h-5" style={{ color: 'var(--lv0)' }} />
            <div className="flex-1">
              <span className="font-semibold" style={{ color: 'var(--lv0)' }}>
                Alerta de Riego Urgente
              </span>
              <p className="text-sm text-[var(--foreground-muted)]">
                Zona <strong className="capitalize">{irrigationAnalysis.mostCriticalZone}</strong> con{' '}
                <strong>{irrigationAnalysis.lowestHumidity.toFixed(0)}%</strong> de humedad
              </p>
            </div>
            {irrigationAnalysis.mostCriticalZone && (
              <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-[var(--lv0)]/20">
                <MapPin className="w-3 h-3" style={{ color: 'var(--lv0)' }} />
                <span className="text-xs font-medium capitalize" style={{ color: 'var(--lv0)' }}>
                  {irrigationAnalysis.mostCriticalZone}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Big Score Typography */}
        <div className="text-center py-6 sm:py-8">
          <p className="text-xs sm:text-sm uppercase tracking-widest text-[var(--foreground-muted)] mb-3">
            Estado del Suelo
          </p>
          <div className="relative inline-block w-full">
            <h2 
              className={`text-3xl xs:text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-display font-black tracking-tight leading-none break-words ${isStrategic ? 'text-gradient' : ''}`}
              style={!isStrategic ? { color: 'var(--lv3)' } : undefined}
            >
              {isStrategic ? 'ESTRATEGICO' : 'OPORTUNO'}
            </h2>
            
            {/* Animated underline */}
            <div 
              className={`mt-3 mx-auto h-1 rounded-full ${isStrategic ? 'bg-gradient' : 'bg-[var(--lv3)]'}`}
              style={{
                width: '80%',
                maxWidth: '300px',
                animation: 'pulse-glow 2s ease-in-out infinite',
              }}
            />
          </div>
          
          <p className="mt-4 sm:mt-6 text-sm sm:text-base text-[var(--foreground-muted)] max-w-md mx-auto px-4">
            {isStrategic 
              ? 'Se requiere riego inmediato. Niveles de humedad por debajo del umbral optimo.'
              : 'Condiciones favorables. Riego preventivo recomendado para mantener niveles.'}
          </p>
        </div>

        {/* Zone summary cards */}
        <div className="grid grid-cols-3 gap-2 mb-6">
          {(['norte', 'centro', 'sur'] as const).map((zoneName) => {
            const zone = zones[zoneName]
            const isCritical = zone.estado === 'muy_seco' || zone.estado === 'seco'
            const isTarget = drone.targetZone === zoneName
            
            return (
              <div 
                key={zoneName}
                className={`relative p-3 rounded-xl border-2 transition-all ${isTarget ? 'ring-2 ring-offset-2 ring-[var(--lv4)]' : ''}`}
                style={{ 
                  borderColor: isCritical ? 'var(--lv0)' : 'var(--border)',
                  backgroundColor: isCritical ? 'var(--lv0)10' : 'var(--bg-elevated)',
                }}
              >
                {isTarget && (
                  <span className="absolute -top-2 -right-2 w-4 h-4 bg-[var(--lv4)] rounded-full flex items-center justify-center">
                    <Target className="w-2.5 h-2.5 text-white" />
                  </span>
                )}
                <div className="flex items-center gap-1 mb-1">
                  <MapPin className="w-3 h-3 text-[var(--foreground-muted)]" />
                  <span className="text-xs font-medium capitalize">{zoneName}</span>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-xl font-display font-bold" style={{ 
                    color: isCritical ? 'var(--lv0)' : 'var(--foreground)' 
                  }}>
                    {zone.humedad.toFixed(0)}%
                  </span>
                </div>
                <div className="flex items-center gap-1 mt-1">
                  <Thermometer className="w-3 h-3 text-[var(--foreground-subtle)]" />
                  <span className="text-[10px] text-[var(--foreground-subtle)]">
                    {zone.temperatura.toFixed(1)}C
                  </span>
                </div>
              </div>
            )
          })}
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-[var(--bg-elevated)] rounded-xl p-4">
            <div className="flex items-center gap-2 text-[var(--foreground-muted)] mb-2">
              <Clock className="w-4 h-4" />
              <span className="text-sm">Proxima ventana</span>
            </div>
            <span 
              className={`text-2xl font-display font-bold ${
                irrigationAnalysis.nextWindow === 'AHORA' ? 'text-[var(--lv0)] animate-pulse' : ''
              }`}
            >
              {irrigationAnalysis.nextWindow}
            </span>
          </div>
          
          <div className="bg-[var(--bg-elevated)] rounded-xl p-4">
            <div className="flex items-center gap-2 text-[var(--foreground-muted)] mb-2">
              <Target className="w-4 h-4" />
              <span className="text-sm">Zona objetivo</span>
            </div>
            <span className="text-2xl font-display font-bold capitalize">
              {drone.targetZone || 'Ninguna'}
            </span>
          </div>
          
          <div className="bg-[var(--bg-elevated)] rounded-xl p-4">
            <div className="flex items-center gap-2 text-[var(--foreground-muted)] mb-2">
              <Zap className="w-4 h-4" />
              <span className="text-sm">Humedad prom.</span>
            </div>
            <span 
              className="text-2xl font-display font-bold"
              style={{ color: averageHumidity < 40 ? 'var(--lv0)' : averageHumidity < 60 ? 'var(--lv2)' : 'var(--lv3)' }}
            >
              {averageHumidity.toFixed(0)}%
            </span>
          </div>
          
          <div className="bg-[var(--bg-elevated)] rounded-xl p-4">
            <div className="flex items-center gap-2 text-[var(--foreground-muted)] mb-2">
              <AlertTriangle className="w-4 h-4" />
              <span className="text-sm">Zonas criticas</span>
            </div>
            <span 
              className="text-2xl font-display font-bold"
              style={{ color: irrigationAnalysis.criticalZones > 0 ? 'var(--lv0)' : 'var(--lv3)' }}
            >
              {irrigationAnalysis.criticalZones}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
