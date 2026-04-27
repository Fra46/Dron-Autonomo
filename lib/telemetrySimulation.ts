import { TelemetryData, ZoneState, calculateHumidityLevel } from './telemetry'

export interface SimulationOptions {
  interval: number
  zones: readonly ['norte', 'centro', 'sur']
}

export class TelemetrySimulator {
  private intervalId: NodeJS.Timeout | null = null
  private currentZoneIndex = 0
  private options: SimulationOptions

  constructor(options: SimulationOptions) {
    this.options = options
  }

  start(onUpdate: (newTelemetry: TelemetryData) => void): void {
    if (this.intervalId) return

    console.log('[TelemetrySimulator] Iniciando simulacion')

    this.intervalId = setInterval(() => {
      const currentZone = this.options.zones[this.currentZoneIndex]
      this.currentZoneIndex = (this.currentZoneIndex + 1) % this.options.zones.length

      onUpdate(this.generateTelemetryUpdate(currentZone))
    }, this.options.interval)
  }

  stop(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId)
      this.intervalId = null
      console.log('[TelemetrySimulator] Simulacion detenida')
    }
  }

  private generateTelemetryUpdate(currentZone: string): TelemetryData {
    // This would be called with previous telemetry, but for simplicity, generate full state
    // In real implementation, pass previous state
    throw new Error('Implement with previous state')
  }
}

// Factory function for simulation updates
export function createSimulationUpdate(prev: TelemetryData, zones: readonly ['norte', 'centro', 'sur']): TelemetryData {
  const currentZone = zones[Math.floor(Math.random() * zones.length)]

  const newHumedad = Math.max(5, Math.min(95,
    prev.zones[currentZone].humedad + (Math.random() - 0.5) * 8
  ))

  const estado = newHumedad >= 70 ? 'humedo'
    : newHumedad >= 50 ? 'normal'
    : newHumedad >= 30 ? 'seco'
    : 'muy_seco'

  const newZones = {
    ...prev.zones,
    [currentZone]: {
      humedad: newHumedad,
      estado: estado as ZoneState,
      temperatura: 28 + Math.random() * 10,
      nivel: calculateHumidityLevel(newHumedad),
    },
  }

  const avgHumidity = (newZones.norte.humedad + newZones.centro.humedad + newZones.sur.humedad) / 3

  // Simulate drone state
  let newFlightStatus = prev.drone.flightStatus
  let targetZone = prev.drone.targetZone

  if (estado === 'muy_seco' && newFlightStatus === 'idle') {
    newFlightStatus = 'ascenso'
    targetZone = currentZone
  } else if (newFlightStatus === 'ascenso') {
    newFlightStatus = 'navegando'
  } else if (newFlightStatus === 'navegando') {
    newFlightStatus = 'regando'
  } else if (newFlightStatus === 'regando' && estado !== 'muy_seco') {
    newFlightStatus = 'retorno'
  } else if (newFlightStatus === 'retorno') {
    newFlightStatus = 'descenso'
  } else if (newFlightStatus === 'descenso') {
    newFlightStatus = 'idle'
    targetZone = null
  }

  const newReading = {
    zona: currentZone,
    humedad: newHumedad,
    estado,
    temperatura: newZones[currentZone].temperatura,
    timestamp: new Date().toISOString(),
  }

  return {
    ...prev,
    zones: newZones,
    humidityZones: prev.humidityZones, // Assume calculateHumidityZones is called elsewhere
    averageHumidity: avgHumidity,
    drone: {
      ...prev.drone,
      flightStatus: newFlightStatus,
      targetZone,
      battery: Math.max(0, prev.drone.battery - (newFlightStatus !== 'idle' ? 0.1 : 0)),
      waterLevel: Math.max(0, prev.drone.waterLevel - (newFlightStatus === 'regando' ? 0.5 : 0)),
    },
    lastReading: newReading,
    history: [...prev.history.slice(-9), newReading],
    timestamp: Date.now(),
    lastSync: Date.now(),
  }
}
