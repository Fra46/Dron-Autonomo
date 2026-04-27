import { useState, useEffect } from 'react'
import { useTelemetryContext } from '@/contexts/TelemetryContext'

const getHumidityLevel = (humidity: number) => {
  if (humidity < 25) return 'lv0'
  if (humidity < 40) return 'lv1'
  if (humidity < 55) return 'lv2'
  if (humidity < 70) return 'lv3'
  if (humidity < 85) return 'lv4'
  return 'lv5'
}

const getLevelLabel = (level: string) => {
  const labels: Record<string, string> = {
    lv0: 'Crítico',
    lv1: 'Bajo',
    lv2: 'Medio Bajo',
    lv3: 'Óptimo',
    lv4: 'Alto',
    lv5: 'Saturado'
  }
  return labels[level] || 'Desconocido'
}

const HUMIDITY_COLORS: Record<string, string> = {
  lv0: '#FF3B30',
  lv1: '#FF9500',
  lv2: '#FFCC00',
  lv3: '#34C759',
  lv4: '#00C7BE',
  lv5: '#AF52DE',
}

export default function ScorePanel() {
  const { telemetry } = useTelemetryContext()
  const humidity = telemetry.averageHumidity
  const [history, setHistory] = useState<number[]>([humidity, humidity, humidity, humidity, humidity, humidity, humidity, humidity])
  const [trend, setTrend] = useState<'up' | 'down' | 'stable'>('stable')

  useEffect(() => {
    setHistory(prev => {
      const newHistory = [...prev.slice(-7), humidity]
      
      if (newHistory.length >= 2) {
        const diff = newHistory[newHistory.length - 1] - newHistory[newHistory.length - 2]
        if (diff > 2) setTrend('up')
        else if (diff < -2) setTrend('down')
        else setTrend('stable')
      }
      
      return newHistory
    })
  }, [humidity])

  const level = getHumidityLevel(humidity)
  const maxHistory = Math.max(...history, 100)

  return (
    <div className="glass panel-card">
      <h3 className="panel-title">Nivel de Humedad Actual</h3>
      
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div>
          <span 
            style={{ 
              fontSize: '2.5rem', 
              fontFamily: 'var(--font-heading)',
              fontWeight: 700,
              color: HUMIDITY_COLORS[level]
            }}
          >
            {humidity.toFixed(0)}%
          </span>
          <span 
            style={{ 
              marginLeft: '0.5rem',
              fontSize: '0.875rem',
              color: 'var(--text-secondary)'
            }}
          >
            {getLevelLabel(level)}
          </span>
        </div>
        
        <div style={{ color: HUMIDITY_COLORS[level] }}>
          {trend === 'up' && (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 19V5M5 12l7-7 7 7"/>
            </svg>
          )}
          {trend === 'down' && (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 5v14M5 12l7 7 7-7"/>
            </svg>
          )}
          {trend === 'stable' && (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M5 12h14"/>
            </svg>
          )}
        </div>
      </div>

      {/* Score Bar */}
      <div className="score-bar-container">
        <div 
          className={`score-bar-fill ${level}`}
          style={{ width: `${humidity}%` }}
        />
      </div>

      {/* Escala de niveles */}
      <div className="d-flex justify-content-between mt-2" style={{ fontSize: '0.625rem', color: 'var(--text-muted)' }}>
        <span>0%</span>
        <span>25%</span>
        <span>50%</span>
        <span>75%</span>
        <span>100%</span>
      </div>

      {/* Historial */}
      <div className="humidity-history">
        {history.map((value, i) => (
          <div
            key={i}
            className="history-bar"
            style={{
              height: `${(value / maxHistory) * 100}%`,
              backgroundColor: HUMIDITY_COLORS[getHumidityLevel(value)],
              opacity: 0.4 + (i / history.length) * 0.6
            }}
          />
        ))}
      </div>
      
      <div className="text-center mt-2" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
        Historial de los últimos 8 ciclos
      </div>
    </div>
  )
}
