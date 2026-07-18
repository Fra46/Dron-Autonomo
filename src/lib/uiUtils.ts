import { HumidityLevel, calculateHumidityLevel } from './telemetry'

// UI utilities for telemetry display
export const HUMIDITY_COLORS: Record<HumidityLevel, string> = {
  lv0: '#FF3B30',
  lv1: '#FF9500',
  lv2: '#FFCC00',
  lv3: '#34C759',
  lv4: '#00C7BE',
  lv5: '#AF52DE',
}

export function getHumidityColor(humidity: number): string {
  return HUMIDITY_COLORS[calculateHumidityLevel(humidity)]
}
