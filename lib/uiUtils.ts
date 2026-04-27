// UI utilities for telemetry display
export function getBatteryColor(battery: number): string {
  if (battery > 60) return 'text-[var(--lv3)]'
  if (battery > 30) return 'text-[var(--lv2)]'
  if (battery > 15) return 'text-[var(--lv1)]'
  return 'text-[var(--lv0)]'
}

export function getSignalColor(signal: number): string {
  if (signal > 80) return 'text-[var(--lv3)]'
  if (signal > 50) return 'text-[var(--lv2)]'
  return 'text-[var(--lv0)]'
}

export function formatCoord(coord: number, type: 'lat' | 'lng'): string {
  const direction = type === 'lat' ? (coord >= 0 ? 'N' : 'S') : (coord >= 0 ? 'E' : 'W')
  return `${Math.abs(coord).toFixed(4)}°${direction}`
}

export const flightStatusColors: Record<string, string> = {
  idle: 'bg-[var(--lv2)]',
  ascenso: 'bg-[var(--lv1)]',
  navegando: 'bg-[var(--lv4)]',
  regando: 'bg-[var(--lv3)]',
  retorno: 'bg-[var(--lv5)]',
  descenso: 'bg-[var(--lv1)]',
}

export const flightStatusLabels: Record<string, string> = {
  idle: 'En reposo',
  ascenso: 'Ascendiendo',
  navegando: 'Navegando',
  regando: 'Regando',
  retorno: 'Retornando',
  descenso: 'Descendiendo',
}
