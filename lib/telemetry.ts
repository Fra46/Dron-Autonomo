export type ZoneName = 'norte' | 'centro' | 'sur'
export type ZoneState = 'humedo' | 'normal' | 'seco' | 'muy_seco'
export type HumidityLevel = 'lv0' | 'lv1' | 'lv2' | 'lv3' | 'lv4' | 'lv5'
export type FlightStatus = 'idle' | 'ascenso' | 'navegando' | 'regando' | 'retorno' | 'descenso'
export type IrrigationStatus = 'active' | 'idle' | 'paused'

export interface Coordinates {
  latitude: number
  longitude: number
  altitude: number
}

export interface ZoneData {
  humedad: number
  estado: ZoneState
  temperatura: number
  nivel: HumidityLevel
}

export interface DroneState {
  flightStatus: FlightStatus
  battery: number
  position: Coordinates
  targetZone: string | null
  waterLevel: number
}

export interface TelemetryNodeReading {
  id: string
  x: number
  y: number
  humidity: number
}

export interface TelemetryZones {
  norte: ZoneData
  centro: ZoneData
  sur: ZoneData
}

export interface TelemetryData {
  zones: TelemetryZones
  humidityZones: Record<HumidityLevel, number>
  averageHumidity: number
  drone: DroneState
  lastReading: {
    zona: string
    humedad: number
    estado: ZoneState
    temperatura: number
    timestamp: string
  } | null
  history: Array<{
    zona: string
    humedad: number
    estado: ZoneState
    temperatura: number
    timestamp: string
  }>
  timestamp: number
  lastSync: number
  coordinates: Coordinates
  signal: number
  temperature: number
  speed: number
  waterLevel: number
  irrigationStatus: IrrigationStatus
  nodeReadings: TelemetryNodeReading[]
}

const DEFAULT_COORDINATES: Coordinates = {
  latitude: 0,
  longitude: 0,
  altitude: 0,
}

export const DEFAULT_TELEMETRY: TelemetryData = {
  zones: {
    norte:  { humedad: 75, estado: 'humedo',  temperatura: 30, nivel: 'lv4' },
    centro: { humedad: 50, estado: 'normal',  temperatura: 32, nivel: 'lv2' },
    sur:    { humedad: 25, estado: 'seco',    temperatura: 35, nivel: 'lv1' },
  },
  humidityZones: {
    lv0: 0,
    lv1: 1,
    lv2: 1,
    lv3: 0,
    lv4: 1,
    lv5: 0,
  },
  averageHumidity: 50,
  drone: {
    flightStatus: 'idle',
    battery: 100,
    position: DEFAULT_COORDINATES,
    targetZone: null,
    waterLevel: 100,
  },
  lastReading: null,
  history: [],
  timestamp: Date.now(),
  lastSync: Date.now(),
  coordinates: DEFAULT_COORDINATES,
  signal: 100,
  temperature: 25,
  speed: 0,
  waterLevel: 100,
  irrigationStatus: 'idle',
  nodeReadings: [],
}

export const calculateHumidityLevel = (humedad: number): HumidityLevel => {
  if (humedad < 25) return 'lv0'
  if (humedad < 40) return 'lv1'
  if (humedad < 55) return 'lv2'
  if (humedad < 70) return 'lv3'
  if (humedad < 85) return 'lv4'
  return 'lv5'
}

export const calculateHumidityZones = (zones: TelemetryZones): Record<HumidityLevel, number> => {
  const counts: Record<HumidityLevel, number> = {
    lv0: 0,
    lv1: 0,
    lv2: 0,
    lv3: 0,
    lv4: 0,
    lv5: 0,
  }

  Object.values(zones).forEach(zone => {
    counts[calculateHumidityLevel(zone.humedad)]++
  })

  return counts
}

const normalizeZone = (raw: any, defaultZone: ZoneData): ZoneData => {
  const humedad = typeof raw?.humedad === 'number' ? raw.humedad : defaultZone.humedad
  const estado = typeof raw?.estado === 'string' ? raw.estado : defaultZone.estado
  const temperatura = typeof raw?.temperatura === 'number' ? raw.temperatura : defaultZone.temperatura
  return {
    humedad,
    estado: estado as ZoneState,
    temperatura,
    nivel: calculateHumidityLevel(humedad),
  }
}

const normalizeDroneState = (raw: any): DroneState => ({
  flightStatus: (raw?.flightStatus ?? raw?.flight_status ?? 'idle') as FlightStatus,
  battery: typeof raw?.battery === 'number' ? raw.battery : 100,
  position: {
    latitude: typeof raw?.position?.x === 'number' ? raw.position.x : raw?.position?.latitude ?? 0,
    longitude: typeof raw?.position?.y === 'number' ? raw.position.y : raw?.position?.longitude ?? 0,
    altitude: typeof raw?.position?.z === 'number' ? raw.position.z : raw?.position?.altitude ?? 0,
  },
  targetZone: raw?.targetZone ?? raw?.target_zone ?? null,
  waterLevel: typeof raw?.waterLevel === 'number' ? raw.waterLevel : raw?.water_level ?? 100,
})

const normalizeCoordinates = (raw: any): Coordinates => ({
  latitude: typeof raw?.latitude === 'number' ? raw.latitude : raw?.lat ?? 0,
  longitude: typeof raw?.longitude === 'number' ? raw.longitude : raw?.lng ?? 0,
  altitude: typeof raw?.altitude === 'number' ? raw.altitude : 0,
})

const normalizeLastReading = (raw: any): TelemetryData['lastReading'] => {
  if (!raw) return null
  return {
    zona: raw.zona ?? raw.zone ?? 'centro',
    humedad: typeof raw.humedad === 'number' ? raw.humedad : 0,
    estado: (raw.estado ?? raw.state ?? 'normal') as ZoneState,
    temperatura: typeof raw.temperatura === 'number' ? raw.temperatura : 0,
    timestamp: raw.timestamp ?? new Date().toISOString(),
  }
}

const normalizeNodeReadings = (raw: any): TelemetryNodeReading[] => {
  if (!Array.isArray(raw)) return []
  return raw.map(item => ({
    id: String(item.id ?? item.zone ?? 'unknown'),
    x: typeof item.x === 'number' ? item.x : item.longitude ?? 0,
    y: typeof item.y === 'number' ? item.y : item.latitude ?? 0,
    humidity: typeof item.humidity === 'number' ? item.humidity : 0,
  }))
}

export const parseTelemetryMessage = (data: string): Partial<TelemetryData> | null => {
  try {
    const parsed = JSON.parse(data)

    if (parsed.type === 'initial_state' || parsed.type === 'telemetry_update') {
      const zones = {
        norte: normalizeZone(parsed.zones?.norte, DEFAULT_TELEMETRY.zones.norte),
        centro: normalizeZone(parsed.zones?.centro, DEFAULT_TELEMETRY.zones.centro),
        sur: normalizeZone(parsed.zones?.sur, DEFAULT_TELEMETRY.zones.sur),
      }

      const humidityZones = parsed.humidityZones ?? calculateHumidityZones(zones)
      const averageHumidity = typeof parsed.averageHumidity === 'number'
        ? parsed.averageHumidity
        : (zones.norte.humedad + zones.centro.humedad + zones.sur.humedad) / 3

      const drone = parsed.drone ? normalizeDroneState(parsed.drone) : DEFAULT_TELEMETRY.drone
      const coordinates = parsed.coordinates ? normalizeCoordinates(parsed.coordinates) : DEFAULT_COORDINATES
      const lastReading = normalizeLastReading(parsed.lastReading)
      const humidity = typeof parsed.signal === 'number' ? parsed.signal : DEFAULT_TELEMETRY.signal
      const temperature = typeof parsed.temperature === 'number' ? parsed.temperature : DEFAULT_TELEMETRY.temperature
      const speed = typeof parsed.speed === 'number' ? parsed.speed : DEFAULT_TELEMETRY.speed
      const irrigationStatus = (parsed.irrigationStatus ?? 'idle') as IrrigationStatus
      const nodeReadings = normalizeNodeReadings(parsed.nodeReadings)

      return {
        zones,
        humidityZones,
        averageHumidity,
        drone,
        lastReading,
        history: Array.isArray(parsed.history) ? parsed.history : DEFAULT_TELEMETRY.history,
        coordinates,
        signal: humidity,
        temperature,
        speed,
        waterLevel: drone.waterLevel,
        irrigationStatus,
        nodeReadings,
        timestamp: Date.now(),
        lastSync: Date.now(),
      }
    }

    if (parsed.type === 'drone_status_update') {
      const drone = normalizeDroneState(parsed.drone)
      return {
        drone,
        waterLevel: drone.waterLevel,
        timestamp: Date.now(),
        lastSync: Date.now(),
      }
    }

    return null
  } catch (error) {
    console.error('[Telemetry] Error parsing WS message:', error)
    return null
  }
}
