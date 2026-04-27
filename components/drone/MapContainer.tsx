'use client'

import { useState, useEffect, useRef } from 'react'
import { MapPin, Maximize2, Grid3X3, Layers } from 'lucide-react'
import { useTelemetryContext } from '@/contexts/TelemetryContext'

interface Node {
  id: string
  x: number
  y: number
  humidity: number
}

interface DronePosition {
  x: number
  y: number
  rotation: number
}

const INITIAL_NODES: Node[] = [
  { id: 'A1', x: 15, y: 15, humidity: 35 },
  { id: 'A2', x: 50, y: 10, humidity: 62 },
  { id: 'A3', x: 85, y: 15, humidity: 78 },
  { id: 'B1', x: 10, y: 50, humidity: 45 },
  { id: 'B2', x: 50, y: 50, humidity: 28 },
  { id: 'B3', x: 90, y: 50, humidity: 55 },
  { id: 'C1', x: 15, y: 85, humidity: 72 },
  { id: 'C2', x: 50, y: 90, humidity: 41 },
  { id: 'C3', x: 85, y: 85, humidity: 88 },
]

// Hex colors for canvas (Canvas API cannot parse CSS variables)
const HUMIDITY_COLORS = {
  lv0: '#FF3B30', // Critico - rojo
  lv1: '#FF9500', // Bajo - naranja
  lv2: '#FFCC00', // Medio bajo - amarillo
  lv3: '#34C759', // Optimo - esmeralda
  lv4: '#00C7BE', // Alto - turquesa
  lv5: '#AF52DE', // Saturado - purpura
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
  // CSS variables for DOM elements
  if (humidity < 25) return 'var(--lv0)'
  if (humidity < 40) return 'var(--lv1)'
  if (humidity < 55) return 'var(--lv2)'
  if (humidity < 70) return 'var(--lv3)'
  if (humidity < 85) return 'var(--lv4)'
  return 'var(--lv5)'
}

export function MapContainer() {
  const { telemetry } = useTelemetryContext()
  const isFlying = telemetry.flightStatus !== 'idle'
  const isIrrigating = telemetry.irrigationStatus === 'active'
  
  // Use telemetry node readings if available, otherwise use initial nodes
  const [nodes, setNodes] = useState<Node[]>(INITIAL_NODES)
  const [dronePos, setDronePos] = useState<DronePosition>({ x: 50, y: 95, rotation: 0 })
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [showGrid, setShowGrid] = useState(true)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  // Sync nodes with telemetry data
  useEffect(() => {
    if (telemetry.nodeReadings.length > 0) {
      setNodes(telemetry.nodeReadings.map(reading => ({
        id: reading.id,
        x: reading.x,
        y: reading.y,
        humidity: reading.humidity,
      })))
    }
  }, [telemetry.nodeReadings])

  // Simulate drone movement when flying
  useEffect(() => {
    if (!isFlying) {
      setDronePos({ x: 50, y: 95, rotation: 0 })
      return
    }

    let nodeIndex = 0
    const lowHumidityNodes = nodes.filter(n => n.humidity < 50)
    
    const interval = setInterval(() => {
      if (lowHumidityNodes.length === 0) return
      
      const targetNode = lowHumidityNodes[nodeIndex % lowHumidityNodes.length]
      
      if (targetNode) {
        setDronePos(prev => {
          const dx = targetNode.x - prev.x
          const dy = targetNode.y - prev.y
          const distance = Math.sqrt(dx * dx + dy * dy)
          
          if (distance < 3) {
            // Water the node if irrigating
            if (isIrrigating) {
              setNodes(prevNodes => 
                prevNodes.map(n => 
                  n.id === targetNode.id 
                    ? { ...n, humidity: Math.min(100, n.humidity + 15) }
                    : n
                )
              )
            }
            nodeIndex++
            return prev
          }
          
          const speed = 2
          const vx = (dx / distance) * speed
          const vy = (dy / distance) * speed
          const rotation = Math.atan2(dy, dx) * (180 / Math.PI) + 90
          
          return {
            x: prev.x + vx,
            y: prev.y + vy,
            rotation,
          }
        })
      }
    }, 100)

    return () => clearInterval(interval)
  }, [isFlying, isIrrigating, nodes])

  // Draw terrain zones
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * 2
    canvas.height = rect.height * 2
    ctx.scale(2, 2)
    
    ctx.clearRect(0, 0, rect.width, rect.height)
    
    // Draw humidity zones with gradients
    nodes.forEach(node => {
      const x = (node.x / 100) * rect.width
      const y = (node.y / 100) * rect.height
      const radius = 60
      
      const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius)
      const color = getHumidityColor(node.humidity, true) // Use hex colors for canvas
      gradient.addColorStop(0, color + '66') // 40% opacity in hex
      gradient.addColorStop(0.5, color + '33') // 20% opacity in hex
      gradient.addColorStop(1, 'rgba(0,0,0,0)')
      
      ctx.fillStyle = gradient
      ctx.beginPath()
      ctx.arc(x, y, radius, 0, Math.PI * 2)
      ctx.fill()
    })
  }, [nodes])

  return (
    <div className="relative w-full h-full min-h-[400px] rounded-2xl overflow-hidden glass glow animate-fadeUp-delay-2">
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between p-4 bg-gradient-to-b from-[var(--bg)]/80 to-transparent">
        <div className="flex items-center gap-2">
          <MapPin className="w-5 h-5 text-[var(--gradient-end)]" />
          <span className="font-display font-semibold">Terreno de Cultivo</span>
          <span className="text-xs text-[var(--foreground-muted)] ml-2">
            ({telemetry.coordinates.latitude.toFixed(4)}, {telemetry.coordinates.longitude.toFixed(4)})
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setShowGrid(!showGrid)}
            className={`p-2 rounded-lg transition-colors ${showGrid ? 'bg-[var(--gradient-end)]/20 text-[var(--gradient-end)]' : 'text-[var(--foreground-muted)] hover:text-foreground'}`}
          >
            <Grid3X3 className="w-4 h-4" />
          </button>
          <button className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-foreground transition-colors">
            <Layers className="w-4 h-4" />
          </button>
          <button className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-foreground transition-colors">
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>
      </div>
      
      {/* Map Area */}
      <div className="relative w-full h-full bg-[var(--bg-elevated)]">
        {/* Canvas for humidity zones */}
        <canvas 
          ref={canvasRef}
          className="absolute inset-0 w-full h-full"
        />
        
        {/* Grid overlay */}
        {showGrid && (
          <div 
            className="absolute inset-0 opacity-20"
            style={{
              backgroundImage: `
                linear-gradient(to right, var(--border) 1px, transparent 1px),
                linear-gradient(to bottom, var(--border) 1px, transparent 1px)
              `,
              backgroundSize: '10% 10%',
            }}
          />
        )}
        
        {/* Boundary polygon */}
        <svg className="absolute inset-0 w-full h-full">
          <defs>
            <linearGradient id="boundaryGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="var(--gradient-start)" stopOpacity="0.5" />
              <stop offset="100%" stopColor="var(--gradient-end)" stopOpacity="0.5" />
            </linearGradient>
          </defs>
          <polygon 
            points="10%,10% 90%,10% 95%,50% 90%,90% 10%,90% 5%,50%"
            fill="none"
            stroke="url(#boundaryGradient)"
            strokeWidth="2"
            strokeDasharray="5,5"
          />
        </svg>
        
        {/* Nodes */}
        {nodes.map((node) => (
          <button
            key={node.id}
            onClick={() => setSelectedNode(selectedNode?.id === node.id ? null : node)}
            className="absolute transform -translate-x-1/2 -translate-y-1/2 group transition-transform hover:scale-110"
            style={{ 
              left: `${node.x}%`, 
              top: `${node.y}%`,
            }}
          >
            <div 
              className="w-6 h-6 rounded-full border-2 border-white/50 flex items-center justify-center transition-all"
              style={{ backgroundColor: getHumidityColor(node.humidity) }}
            >
              <span className="text-[8px] font-bold text-white">{node.id}</span>
            </div>
            
            {/* Tooltip */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 rounded-lg glass text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              <span className="font-mono">{node.humidity.toFixed(0)}%</span>
            </div>
          </button>
        ))}
        
        {/* Drone */}
        <div 
          className="absolute transform -translate-x-1/2 -translate-y-1/2 transition-all duration-100 ease-linear z-20"
          style={{ 
            left: `${dronePos.x}%`, 
            top: `${dronePos.y}%`,
            transform: `translate(-50%, -50%) rotate(${dronePos.rotation}deg)`,
          }}
        >
          <div className="relative">
            {/* Drone body */}
            <div className={`w-10 h-10 ${isFlying ? 'animate-pulse' : ''}`}>
              <svg viewBox="0 0 40 40" className="w-full h-full">
                <defs>
                  <linearGradient id="droneGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="var(--gradient-start)" />
                    <stop offset="100%" stopColor="var(--gradient-end)" />
                  </linearGradient>
                </defs>
                {/* Drone arms */}
                <line x1="8" y1="8" x2="32" y2="32" stroke="url(#droneGradient)" strokeWidth="2" />
                <line x1="32" y1="8" x2="8" y2="32" stroke="url(#droneGradient)" strokeWidth="2" />
                {/* Drone propellers */}
                <circle cx="8" cy="8" r="5" fill="url(#droneGradient)" opacity="0.7" />
                <circle cx="32" cy="8" r="5" fill="url(#droneGradient)" opacity="0.7" />
                <circle cx="8" cy="32" r="5" fill="url(#droneGradient)" opacity="0.7" />
                <circle cx="32" cy="32" r="5" fill="url(#droneGradient)" opacity="0.7" />
                {/* Drone center */}
                <circle cx="20" cy="20" r="6" fill="var(--bg)" stroke="url(#droneGradient)" strokeWidth="2" />
              </svg>
            </div>
            
            {/* Spray effect when watering */}
            {isIrrigating && (
              <div className="absolute top-full left-1/2 -translate-x-1/2 mt-1">
                <div className="w-6 h-12 bg-gradient-to-b from-[var(--lv4)]/60 to-transparent rounded-full blur-sm animate-pulse" />
              </div>
            )}
          </div>
        </div>
        
        {/* Selected node panel */}
        {selectedNode && (
          <div className="absolute bottom-4 left-4 right-4 p-4 glass rounded-xl animate-fadeUp">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm text-[var(--foreground-muted)]">Nodo {selectedNode.id}</span>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-2xl font-display font-bold">{selectedNode.humidity.toFixed(0)}%</span>
                  <span className="text-sm text-[var(--foreground-muted)]">humedad</span>
                </div>
              </div>
              <div 
                className="w-12 h-12 rounded-full"
                style={{ backgroundColor: getHumidityColor(selectedNode.humidity) }}
              />
            </div>
          </div>
        )}
      </div>
      
      {/* Legend */}
      <div className="absolute bottom-4 right-4 flex items-center gap-3 px-3 py-2 glass rounded-lg text-xs">
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-[var(--lv0)]" />
          <span>Critico</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-[var(--lv3)]" />
          <span>Optimo</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-[var(--lv5)]" />
          <span>Saturado</span>
        </div>
      </div>
    </div>
  )
}
