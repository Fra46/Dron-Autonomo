import thresholds from '../../shared/humidity_thresholds.json'
import type { HumidityLevel, ZoneState } from './telemetry'

const ZONE_STATE_THRESHOLDS: Record<ZoneState, number> = thresholds.zoneStateThresholds
const HUMIDITY_LEVEL_THRESHOLDS: Array<{ level: HumidityLevel; max: number }> = thresholds.humidityLevelThresholds
export const FUZZY_PARAMS = thresholds.fuzzy as {
  dry: { start: number; end: number }
  very_dry: { start: number; end: number }
  activation: number
}

export const calculateHumidityLevel = (humedad: number): HumidityLevel => {
  for (const { level, max } of HUMIDITY_LEVEL_THRESHOLDS) {
    if (humedad < max) {
      return level
    }
  }
  return 'lv5'
}

export const interpretHumedad = (humedad: number): ZoneState => {
  if (humedad >= ZONE_STATE_THRESHOLDS.humedo) return 'humedo'
  if (humedad >= ZONE_STATE_THRESHOLDS.normal) return 'normal'
  if (humedad >= ZONE_STATE_THRESHOLDS.seco) return 'seco'
  return 'muy_seco'
}
