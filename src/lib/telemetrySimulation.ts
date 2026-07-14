import { TelemetryData, ZoneState, calculateHumidityLevel, calculateHumidityZones } from './telemetry'

export interface SimulationOptions {
  interval: number
  zones: readonly ['norte', 'centro', 'sur']
}

// Factory function for simulation updates.
// Used by hooks/use-telemetry.ts as a graceful fallback when the UDP/WebSocket
// bridge (udp_websocket_bridge.py) is unreachable, so the UI keeps moving
// instead of freezing on stale data.
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
    estado: estado as ZoneState,
    temperatura: newZones[currentZone].temperatura,
    timestamp: new Date().toISOString(),
  }

  return {
    ...prev,
    zones: newZones,
    humidityZones: calculateHumidityZones(newZones),
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
