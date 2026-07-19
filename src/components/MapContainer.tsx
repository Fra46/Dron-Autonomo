import { useMemo, useEffect, useRef, useCallback, useState } from 'react'
import { ButtonGroup, Button } from 'react-bootstrap'
import { useTelemetryContext } from '@/contexts/TelemetryContext'
import { calculateHumidityLevel } from '@/lib/telemetry'
import { getHumidityColor } from '@/lib/uiUtils'

interface MapContainerProps {
  missionActive: boolean
  onHumidityChange?: (humidity: number) => void
}

interface ZoneNode {
  id: 'norte' | 'centro' | 'sur'
  x: number
  y: number
  label: string
  humidity: number
}

const ZONE_LAYOUT: Record<ZoneNode['id'], { x: number; y: number }> = {
  norte: { x: 50, y: 20 },
  centro: { x: 50, y: 50 },
  sur: { x: 50, y: 80 },
}

// Posición de la base (agrícola) - Al OESTE de zona centro
const BASE_POSITION = { x: 15, y: 50 }  // x < 50 = oeste, y = 50 = mismo nivel que centro

const getHumidityLevel = calculateHumidityLevel
const getHumidityCanvasColor = (humidity: number) => getHumidityColor(humidity)

export default function MapContainer({ missionActive, onHumidityChange }: MapContainerProps) {
  const { telemetry } = useTelemetryContext()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [showGrid, setShowGrid] = useState(true)

  const zones: ZoneNode[] = useMemo(
    () => [
      { id: 'norte', label: 'Norte', ...ZONE_LAYOUT.norte, humidity: telemetry.zones.norte.humedad },
      { id: 'centro', label: 'Centro', ...ZONE_LAYOUT.centro, humidity: telemetry.zones.centro.humedad },
      { id: 'sur', label: 'Sur', ...ZONE_LAYOUT.sur, humidity: telemetry.zones.sur.humedad },
    ],
    [telemetry.zones]
  )

  const dronePosition = useMemo(
    () => ({
      x: Math.max(0, Math.min(100, telemetry.drone.position.xPct)),
      y: Math.max(0, Math.min(100, telemetry.drone.position.yPct)),
    }),
    [telemetry.drone.position.xPct, telemetry.drone.position.yPct]
  )

  // Posición mostrada (suavizada) para evitar saltos por ejes cuando las
  // actualizaciones llegan separadas por lat/lon. `displayPos` interpola
  // hacia `dronePosition` usando requestAnimationFrame.
  const [displayPos, setDisplayPos] = useState(dronePosition)
  const targetPosRef = useRef(dronePosition)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    targetPosRef.current = dronePosition

    const step = () => {
      const target = targetPosRef.current
      setDisplayPos(prev => {
        const dx = target.x - prev.x
        const dy = target.y - prev.y
        const dist = Math.hypot(dx, dy)
        if (dist < 0.2) {
          // Cerca suficiente: dejar exactamente la posición objetivo
          return target
        }
        const k = 0.18 // factor de suavizado
        return { x: prev.x + dx * k, y: prev.y + dy * k }
      })
      rafRef.current = requestAnimationFrame(step)
    }

    if (rafRef.current == null) rafRef.current = requestAnimationFrame(step)

    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
  }, [dronePosition])

  const targetZone = telemetry.drone.targetZone ?? 'centro'
  const targetPosition = useMemo(() => {
    const hasValidTarget = typeof telemetry.targetPosition?.xPct === 'number' && typeof telemetry.targetPosition?.yPct === 'number'
    if (hasValidTarget) {
      return {
        x: telemetry.targetPosition.xPct,
        y: telemetry.targetPosition.yPct,
      }
    }

    const fallback = ZONE_LAYOUT[targetZone as ZoneNode['id']] ?? ZONE_LAYOUT.centro
    return { x: fallback.x, y: fallback.y }
  }, [telemetry.targetPosition, targetZone])

  useEffect(() => {
    const avgHumidity = zones.reduce((sum, zone) => sum + zone.humidity, 0) / zones.length
    onHumidityChange?.(avgHumidity)
  }, [zones, onHumidityChange])

  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current
    const container = containerRef.current
    if (!canvas || !container) return

    const rect = container.getBoundingClientRect()
    canvas.width = rect.width
    canvas.height = rect.height
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.fillStyle = '#0d0d14'
    ctx.fillRect(0, 0, rect.width, rect.height)

    if (showGrid) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)'
      ctx.lineWidth = 1
      const gridSize = 30
      for (let x = 0; x < rect.width; x += gridSize) {
        ctx.beginPath()
        ctx.moveTo(x, 0)
        ctx.lineTo(x, rect.height)
        ctx.stroke()
      }
      for (let y = 0; y < rect.height; y += gridSize) {
        ctx.beginPath()
        ctx.moveTo(0, y)
        ctx.lineTo(rect.width, y)
        ctx.stroke()
      }
    }

    zones.forEach(zone => {
      const x = (zone.x / 100) * rect.width
      const y = (zone.y / 100) * rect.height
      const radius = 55
      const color = getHumidityColor(zone.humidity)

      const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius)
      gradient.addColorStop(0, `${color}cc`)
      gradient.addColorStop(0.55, `${color}55`)
      gradient.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = gradient
      ctx.beginPath()
      ctx.arc(x, y, radius, 0, Math.PI * 2)
      ctx.fill()

      ctx.strokeStyle = 'rgba(255,255,255,0.35)'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.arc(x, y, 16, 0, Math.PI * 2)
      ctx.stroke()
    })

    // Dibujar marcador de base
    const baseX = (BASE_POSITION.x / 100) * rect.width
    const baseY = (BASE_POSITION.y / 100) * rect.height
    ctx.strokeStyle = '#34C759'
    ctx.lineWidth = 2.5
    ctx.beginPath()
    ctx.arc(baseX, baseY, 20, 0, Math.PI * 2)
    ctx.stroke()
    ctx.fillStyle = 'rgba(52, 199, 89, 0.15)'
    ctx.fill()
    // Símbolo de base (pequeño cuadrado en el centro)
    ctx.fillStyle = '#34C759'
    ctx.fillRect(baseX - 6, baseY - 6, 12, 12)

    if (telemetry.drone.flightStatus !== 'idle') {
      const droneX = (displayPos.x / 100) * rect.width
      const droneY = (displayPos.y / 100) * rect.height
      const targetX = (targetPosition.x / 100) * rect.width
      const targetY = (targetPosition.y / 100) * rect.height

      ctx.strokeStyle = 'rgba(255,255,255,0.8)'
      ctx.lineWidth = 2
      ctx.setLineDash([8, 6])
      ctx.beginPath()
      ctx.moveTo(droneX, droneY)
      ctx.lineTo(targetX, targetY)
      ctx.stroke()
      ctx.setLineDash([])
    }

    ctx.strokeStyle = 'rgba(175, 82, 222, 0.5)'
    ctx.lineWidth = 2
    ctx.setLineDash([10, 5])
    ctx.strokeRect(20, 20, rect.width - 40, rect.height - 40)
    ctx.setLineDash([])
  }, [zones, showGrid, dronePosition, targetPosition, telemetry.drone.flightStatus])

  useEffect(() => {
    drawCanvas()
    const handleResize = () => drawCanvas()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [drawCanvas])

  return (
    <div className="glass panel-card">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h3 className="panel-title">Mapa de Cultivo</h3>
        <ButtonGroup size="sm">
          <Button
            variant={showGrid ? 'outline-light' : 'dark'}
            onClick={() => setShowGrid(!showGrid)}
            style={{ fontSize: '0.75rem' }}
          >
            Grid
          </Button>
        </ButtonGroup>
      </div>

      <div
        ref={containerRef}
        className="map-container"
        style={{ border: '1px solid rgba(255,255,255,0.1)' }}
      >
        <canvas ref={canvasRef} className="map-canvas" />

        {zones.map(zone => (
          <div
            key={zone.id}
            className={`node-marker ${getHumidityLevel(zone.humidity)}`}
            style={{
              left: `${zone.x}%`,
              top: `${zone.y}%`,
              backgroundColor: getHumidityColor(zone.humidity),
            }}
            title={`${zone.label}: ${zone.humidity.toFixed(0)}%`}
          >
            {zone.label}
          </div>
        ))}

        {/* Marcador de base */}
        <div
          className="node-marker"
          style={{
            left: `${BASE_POSITION.x}%`,
            top: `${BASE_POSITION.y}%`,
            backgroundColor: '#34C759',
            border: '2px solid #34C759',
            fontSize: '0.7rem',
            fontWeight: 700,
          }}
          title="Base de despegue/aterrizaje"
        >
          BASE
        </div>

        <div
          className={`drone-icon ${missionActive ? 'flying' : ''}`}
          style={{
              left: `${displayPos.x}%`,
              top: `${displayPos.y}%`,
          }}
          title={`Dron - ${telemetry.drone.flightStatus} - ${telemetry.drone.altitude.toFixed(1)}m`}
        >
          <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="droneGradient" x1="6" y1="6" x2="34" y2="34">
                <stop offset="0%" stopColor="#FF5E57" />
                <stop offset="100%" stopColor="#AF52DE" />
              </linearGradient>
            </defs>
            {/* Brazos en cruz, para que se lea como un dron y no como otro
                punto de humedad identico a los node-marker de las zonas */}
            <line x1="9" y1="9" x2="31" y2="31" stroke="url(#droneGradient)" strokeWidth="2.5" />
            <line x1="31" y1="9" x2="9" y2="31" stroke="url(#droneGradient)" strokeWidth="2.5" />
            {/* 4 rotores en las puntas de los brazos */}
            <circle cx="9" cy="9" r="5.5" fill="none" stroke="url(#droneGradient)" strokeWidth="2" />
            <circle cx="31" cy="9" r="5.5" fill="none" stroke="url(#droneGradient)" strokeWidth="2" />
            <circle cx="9" cy="31" r="5.5" fill="none" stroke="url(#droneGradient)" strokeWidth="2" />
            <circle cx="31" cy="31" r="5.5" fill="none" stroke="url(#droneGradient)" strokeWidth="2" />
            {/* Cuerpo central solido, blanco para contrastar contra el
                gradiente rojo-purpura de las zonas de humedad */}
            <circle cx="20" cy="20" r="7" fill="url(#droneGradient)" stroke="#fff" strokeWidth="2" />
          </svg>
        </div>

        <div className="map-overlay">
          <div className="glass-subtle px-3 py-2" style={{ fontSize: '0.8rem' }}>
            <small style={{ color: 'var(--text-secondary)' }}>
              {missionActive ? `Objetivo: ${targetZone.toUpperCase()}` : 'En espera'}
            </small>
          </div>
        </div>
      </div>


      {/* Level buttons - José Chinchia */}
      <div className="d-flex flex-wrap gap-2 mt-3 justify-content-center">
        {['lv0', 'lv1', 'lv2', 'lv3', 'lv4', 'lv5'].map((level, i) => {
          const labels = ['Crítico', 'Bajo', 'Medio', 'Óptimo', 'Alto', 'Saturado']
          return (
            <button key={level} className={`level-btn ${level}`}>
              {labels[i]}
            </button>
          )
        })}
      </div>
    </div>
  )
}
