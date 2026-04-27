import { useState, useEffect, useRef, useCallback } from 'react'
import { ButtonGroup, Button } from 'react-bootstrap'

interface MapContainerProps {
  missionActive: boolean
  onHumidityChange?: (humidity: number) => void
}

interface SensorNode {
  id: number
  x: number
  y: number
  humidity: number
}

// Colores hex para canvas
const HUMIDITY_COLORS = {
  lv0: '#FF3B30',
  lv1: '#FF9500',
  lv2: '#FFCC00',
  lv3: '#34C759',
  lv4: '#00C7BE',
  lv5: '#AF52DE',
}

const getHumidityColor = (humidity: number, forCanvas = false) => {
  if (forCanvas) {
    if (humidity < 25) return HUMIDITY_COLORS.lv0
    if (humidity < 40) return HUMIDITY_COLORS.lv1
    if (humidity < 55) return HUMIDITY_COLORS.lv2
    if (humidity < 70) return HUMIDITY_COLORS.lv3
    if (humidity < 85) return HUMIDITY_COLORS.lv4
    return HUMIDITY_COLORS.lv5
  }
  if (humidity < 25) return 'var(--lv0)'
  if (humidity < 40) return 'var(--lv1)'
  if (humidity < 55) return 'var(--lv2)'
  if (humidity < 70) return 'var(--lv3)'
  if (humidity < 85) return 'var(--lv4)'
  return 'var(--lv5)'
}

const getHumidityLevel = (humidity: number) => {
  if (humidity < 25) return 'lv0'
  if (humidity < 40) return 'lv1'
  if (humidity < 55) return 'lv2'
  if (humidity < 70) return 'lv3'
  if (humidity < 85) return 'lv4'
  return 'lv5'
}

const INITIAL_NODES: SensorNode[] = [
  { id: 1, x: 15, y: 20, humidity: 35 },
  { id: 2, x: 50, y: 15, humidity: 62 },
  { id: 3, x: 85, y: 20, humidity: 45 },
  { id: 4, x: 20, y: 50, humidity: 28 },
  { id: 5, x: 50, y: 50, humidity: 55 },
  { id: 6, x: 80, y: 50, humidity: 72 },
  { id: 7, x: 15, y: 80, humidity: 88 },
  { id: 8, x: 50, y: 85, humidity: 40 },
  { id: 9, x: 85, y: 80, humidity: 33 },
]

export default function MapContainer({ missionActive, onHumidityChange }: MapContainerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [nodes, setNodes] = useState<SensorNode[]>(INITIAL_NODES)
  const [dronePosition, setDronePosition] = useState({ x: 50, y: 95 })
  const [showGrid, setShowGrid] = useState(true)
  const [isIrrigating, setIsIrrigating] = useState(false)

  // Simulación de movimiento del dron
  useEffect(() => {
    if (!missionActive) {
      setDronePosition({ x: 50, y: 95 })
      setIsIrrigating(false)
      return
    }

    let nodeIndex = 0
    const visitNodes = () => {
      if (nodeIndex < nodes.length) {
        const target = nodes[nodeIndex]
        setDronePosition({ x: target.x, y: target.y })
        
        setTimeout(() => {
          setIsIrrigating(true)
          setNodes(prev => prev.map((n, i) => 
            i === nodeIndex ? { ...n, humidity: Math.min(95, n.humidity + 15 + Math.random() * 10) } : n
          ))
          setTimeout(() => {
            setIsIrrigating(false)
            nodeIndex++
            visitNodes()
          }, 1500)
        }, 1000)
      } else {
        setDronePosition({ x: 50, y: 95 })
      }
    }

    const timeout = setTimeout(visitNodes, 1000)
    return () => clearTimeout(timeout)
  }, [missionActive, nodes.length])

  // Calcular humedad promedio
  useEffect(() => {
    const avgHumidity = nodes.reduce((sum, n) => sum + n.humidity, 0) / nodes.length
    if (onHumidityChange) {
      onHumidityChange(avgHumidity)
    }
  }, [nodes, onHumidityChange])

  // Simulación de variación de humedad
  useEffect(() => {
    const interval = setInterval(() => {
      setNodes(prev => prev.map(node => ({
        ...node,
        humidity: Math.max(10, Math.min(95, node.humidity + (Math.random() - 0.6) * 2))
      })))
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  // Dibujar canvas
  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current
    const container = containerRef.current
    if (!canvas || !container) return

    const rect = container.getBoundingClientRect()
    canvas.width = rect.width
    canvas.height = rect.height
    
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Fondo
    ctx.fillStyle = '#0d0d14'
    ctx.fillRect(0, 0, rect.width, rect.height)

    // Grid
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

    // Zonas de humedad
    nodes.forEach(node => {
      const x = (node.x / 100) * rect.width
      const y = (node.y / 100) * rect.height
      const radius = 60
      
      const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius)
      const color = getHumidityColor(node.humidity, true)
      gradient.addColorStop(0, color + '66')
      gradient.addColorStop(0.5, color + '33')
      gradient.addColorStop(1, 'rgba(0,0,0,0)')
      
      ctx.fillStyle = gradient
      ctx.beginPath()
      ctx.arc(x, y, radius, 0, Math.PI * 2)
      ctx.fill()
    })

    // Área de cultivo
    ctx.strokeStyle = 'rgba(175, 82, 222, 0.5)'
    ctx.lineWidth = 2
    ctx.setLineDash([10, 5])
    ctx.beginPath()
    const padding = 30
    ctx.moveTo(padding, padding)
    ctx.lineTo(rect.width - padding, padding)
    ctx.lineTo(rect.width - padding, rect.height - padding)
    ctx.lineTo(padding, rect.height - padding)
    ctx.closePath()
    ctx.stroke()
    ctx.setLineDash([])

    // Efecto de riego
    if (isIrrigating) {
      const droneX = (dronePosition.x / 100) * rect.width
      const droneY = (dronePosition.y / 100) * rect.height
      
      for (let i = 0; i < 12; i++) {
        const angle = (i / 12) * Math.PI * 2
        const dist = 20 + Math.random() * 30
        const dropX = droneX + Math.cos(angle) * dist
        const dropY = droneY + Math.sin(angle) * dist + 20
        
        ctx.fillStyle = 'rgba(0, 199, 190, 0.6)'
        ctx.beginPath()
        ctx.arc(dropX, dropY, 2 + Math.random() * 2, 0, Math.PI * 2)
        ctx.fill()
      }
    }
  }, [nodes, showGrid, isIrrigating, dronePosition])

  useEffect(() => {
    drawCanvas()
    const handleResize = () => drawCanvas()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [drawCanvas])

  return (
    <div className="glass panel-card">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h3 className="panel-title mb-0">Mapa de Cultivo</h3>
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
        
        {/* Nodos de sensores */}
        {nodes.map(node => (
          <div
            key={node.id}
            className={`node-marker ${getHumidityLevel(node.humidity)}`}
            style={{
              left: `${node.x}%`,
              top: `${node.y}%`,
              backgroundColor: getHumidityColor(node.humidity),
            }}
            title={`Nodo ${node.id}: ${node.humidity.toFixed(0)}%`}
          >
            {node.id}
          </div>
        ))}

        {/* Dron */}
        <div
          className={`drone-icon ${missionActive ? 'flying' : ''}`}
          style={{
            left: `${dronePosition.x}%`,
            top: `${dronePosition.y}%`,
          }}
        >
          <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="20" cy="20" r="8" fill="url(#droneGradient)" />
            <circle cx="8" cy="8" r="5" stroke="#FF5E57" strokeWidth="2" fill="none">
              <animate attributeName="r" values="4;6;4" dur="0.5s" repeatCount="indefinite" />
            </circle>
            <circle cx="32" cy="8" r="5" stroke="#FF5E57" strokeWidth="2" fill="none">
              <animate attributeName="r" values="4;6;4" dur="0.5s" repeatCount="indefinite" />
            </circle>
            <circle cx="8" cy="32" r="5" stroke="#AF52DE" strokeWidth="2" fill="none">
              <animate attributeName="r" values="4;6;4" dur="0.5s" repeatCount="indefinite" />
            </circle>
            <circle cx="32" cy="32" r="5" stroke="#AF52DE" strokeWidth="2" fill="none">
              <animate attributeName="r" values="4;6;4" dur="0.5s" repeatCount="indefinite" />
            </circle>
            <line x1="12" y1="12" x2="28" y2="28" stroke="white" strokeWidth="2" />
            <line x1="28" y1="12" x2="12" y2="28" stroke="white" strokeWidth="2" />
            <defs>
              <linearGradient id="droneGradient" x1="12" y1="12" x2="28" y2="28">
                <stop offset="0%" stopColor="#FF5E57" />
                <stop offset="100%" stopColor="#AF52DE" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* Overlay info */}
        <div className="map-overlay">
          <div className="glass-subtle px-3 py-2">
            <small style={{ color: 'var(--text-secondary)' }}>
              {missionActive ? 'Misión en progreso...' : 'Virtual Planet - Simulación'}
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
