'use client'

import { useTelemetryContext } from '@/contexts/TelemetryContext'

interface LevelButtonProps {
  level: 'lv0' | 'lv1' | 'lv2' | 'lv3' | 'lv4' | 'lv5'
  count: number
  label: string
  isActive: boolean
  zones: string[]
}

const LEVEL_CONFIG = {
  lv0: { label: 'Critico', color: '#ef4444', description: '0-25%' },
  lv1: { label: 'Bajo', color: '#f97316', description: '25-40%' },
  lv2: { label: 'Moderado', color: '#eab308', description: '40-55%' },
  lv3: { label: 'Optimo', color: '#22c55e', description: '55-70%' },
  lv4: { label: 'Alto', color: '#06b6d4', description: '70-85%' },
  lv5: { label: 'Saturado', color: '#8b5cf6', description: '85-100%' },
}

function LevelButton({ level, count, label, isActive, zones }: LevelButtonProps) {
  const config = LEVEL_CONFIG[level]
  
  // Determinar si es nivel critico (rojo) o saturado (purpura)
  const isCritical = level === 'lv0' || level === 'lv1'
  const isSaturated = level === 'lv5'
  
  return (
    <button
      className={`
        relative flex flex-col items-center justify-center
        p-3 rounded-xl transition-all duration-300
        border-2 min-w-[70px]
        ${isActive 
          ? 'scale-105 shadow-lg' 
          : 'opacity-60 hover:opacity-80 hover:scale-102'
        }
      `}
      style={{
        borderColor: config.color,
        backgroundColor: isActive ? `${config.color}20` : 'var(--bg-elevated)',
        boxShadow: isActive ? `0 0 20px -5px ${config.color}` : 'none',
      }}
    >
      {/* Count badge */}
      <span 
        className="text-2xl font-display font-black"
        style={{ color: config.color }}
      >
        {count}
      </span>
      
      {/* Label */}
      <span 
        className="text-xs font-medium mt-1"
        style={{ color: isActive ? config.color : 'var(--foreground-muted)' }}
      >
        {label}
      </span>
      
      {/* Range indicator */}
      <span className="text-[10px] text-[var(--foreground-subtle)] mt-0.5">
        {config.description}
      </span>
      
      {/* Zone names if active */}
      {isActive && zones.length > 0 && (
        <div className="mt-1 flex flex-wrap justify-center gap-0.5">
          {zones.map(zone => (
            <span 
              key={zone}
              className="text-[8px] px-1 py-0.5 rounded capitalize"
              style={{ 
                backgroundColor: `${config.color}30`,
                color: config.color,
              }}
            >
              {zone}
            </span>
          ))}
        </div>
      )}
      
      {/* Active indicator dot */}
      {isActive && count > 0 && (
        <span 
          className={`absolute -top-1 -right-1 w-3 h-3 rounded-full ${isCritical ? 'animate-pulse' : ''}`}
          style={{ backgroundColor: config.color }}
        />
      )}
    </button>
  )
}

export function LevelButtons() {
  const { telemetry } = useTelemetryContext()
  const { humidityZones, zones } = telemetry
  
  // Calculate total nodes and which zones belong to which level
  const totalNodes = Object.values(humidityZones).reduce((sum, count) => sum + count, 0)
  
  // Map zones to their humidity levels
  const getZonesForLevel = (level: string): string[] => {
    const result: string[] = []
    for (const [zoneName, zoneData] of Object.entries(zones)) {
      if (zoneData.nivel === level) {
        result.push(zoneName)
      }
    }
    return result
  }
  
  // Check for critical zones requiring irrigation
  const criticalCount = humidityZones.lv0 + humidityZones.lv1
  
  return (
    <div className="glass rounded-2xl p-6 animate-fadeUp-delay-2">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display font-semibold">Zonas de Humedad</h3>
        <span className="text-sm text-[var(--foreground-muted)]">
          {totalNodes} zonas activas
        </span>
      </div>
      
      {/* Level Buttons Grid - De rojo (lv0) a purpura (lv5) */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
        <LevelButton 
          level="lv0" 
          count={humidityZones.lv0} 
          label="LV0"
          isActive={humidityZones.lv0 > 0}
          zones={getZonesForLevel('lv0')}
        />
        <LevelButton 
          level="lv1" 
          count={humidityZones.lv1} 
          label="LV1"
          isActive={humidityZones.lv1 > 0}
          zones={getZonesForLevel('lv1')}
        />
        <LevelButton 
          level="lv2" 
          count={humidityZones.lv2} 
          label="LV2"
          isActive={humidityZones.lv2 > 0}
          zones={getZonesForLevel('lv2')}
        />
        <LevelButton 
          level="lv3" 
          count={humidityZones.lv3} 
          label="LV3"
          isActive={humidityZones.lv3 > 0}
          zones={getZonesForLevel('lv3')}
        />
        <LevelButton 
          level="lv4" 
          count={humidityZones.lv4} 
          label="LV4"
          isActive={humidityZones.lv4 > 0}
          zones={getZonesForLevel('lv4')}
        />
        <LevelButton 
          level="lv5" 
          count={humidityZones.lv5} 
          label="LV5"
          isActive={humidityZones.lv5 > 0}
          zones={getZonesForLevel('lv5')}
        />
      </div>
      
      {/* Alert for critical zones */}
      {criticalCount > 0 && (
        <div 
          className="mt-4 p-3 rounded-lg flex items-center gap-3"
          style={{ backgroundColor: '#ef444420' }}
        >
          <span 
            className="w-2 h-2 rounded-full animate-pulse"
            style={{ backgroundColor: '#ef4444' }}
          />
          <span className="text-sm" style={{ color: '#ef4444' }}>
            {criticalCount} zona(s) requieren riego urgente
          </span>
        </div>
      )}
      
      {/* Status bar showing distribution - De rojo a purpura */}
      <div className="mt-4 h-3 rounded-full overflow-hidden flex bg-[var(--bg-elevated)]">
        {(['lv0', 'lv1', 'lv2', 'lv3', 'lv4', 'lv5'] as const).map((level) => {
          const count = humidityZones[level]
          if (count === 0 || totalNodes === 0) return null
          const width = (count / totalNodes) * 100
          return (
            <div
              key={level}
              className="h-full transition-all duration-500"
              style={{ 
                width: `${width}%`,
                backgroundColor: LEVEL_CONFIG[level].color,
              }}
            />
          )
        })}
      </div>
      
      {/* Legend */}
      <div className="mt-3 flex flex-wrap justify-center gap-x-4 gap-y-1 text-[10px] text-[var(--foreground-muted)]">
        <span style={{ color: '#ef4444' }}>Critico</span>
        <span>-</span>
        <span style={{ color: '#f97316' }}>Bajo</span>
        <span>-</span>
        <span style={{ color: '#eab308' }}>Moderado</span>
        <span>-</span>
        <span style={{ color: '#22c55e' }}>Optimo</span>
        <span>-</span>
        <span style={{ color: '#06b6d4' }}>Alto</span>
        <span>-</span>
        <span style={{ color: '#8b5cf6' }}>Saturado</span>
      </div>
    </div>
  )
}
