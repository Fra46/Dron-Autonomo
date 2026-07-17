import { Navbar, Container, Badge } from 'react-bootstrap'
import { useTelemetryContext } from '@/contexts/TelemetryContext'

const FLIGHT_STATUS_LABELS: Record<string, string> = {
  idle: 'En Espera',
  ascenso: 'Despegando',
  navegando: 'En Vuelo',
  regando: 'Regando',
  retorno: 'Regresando',
  descenso: 'Aterrizando',
}

const FLIGHT_STATUS_SHORT: Record<string, string> = {
  idle: 'En',
  ascenso: 'Sub',
  navegando: 'Vu',
  regando: 'Rg',
  retorno: 'Rt',
  descenso: 'At',
}

function getBatteryColor(level: number) {
  if (level > 60) return 'var(--lv3)'
  if (level > 30) return 'var(--lv2)'
  return 'var(--lv0)'
}

function getLatencyColor(ms: number | null) {
  if (ms === null) return 'var(--text-muted)'
  if (ms < 100) return 'var(--lv3)'
  if (ms < 300) return 'var(--lv2)'
  return 'var(--lv0)'
}

function getSignalColor(signal: number) {
  if (signal > 80) return 'var(--lv3)'
  if (signal > 50) return 'var(--lv2)'
  return 'var(--lv0)'
}

export default function TelemetryBar() {
  const { telemetry, isConnected, connectionError } = useTelemetryContext()
  const missionActive = ['ascenso', 'navegando', 'regando', 'retorno'].includes(telemetry.drone.flightStatus)

  const battery = telemetry.drone.battery ?? 100
  const signal = telemetry.signal ?? 0
  const altitude = telemetry.drone.altitude ?? 0
  const speed = telemetry.speed ?? 0
  const temperature = telemetry.temperature ?? 0
  const currentFlightStatus = telemetry.drone.flightStatus ?? 'idle'
  const latencyMs = telemetry.pwaLatencyMs

  return (
    <Navbar expand="lg" fixed="top" className="app-navbar glass">
      <Container fluid className="px-3 px-lg-4">
        <Navbar.Brand href="#" className="app-brand">
          <span className="app-brand-icon" aria-hidden="true">🚁</span>
          <span className="app-brand-text">
            <span className="app-brand-title">AgroDron</span>
            <span className="app-brand-subtitle d-none d-sm-inline">
              Riego autónomo inteligente
            </span>
          </span>

          <Badge
            bg="dark"
            className="flight-status-badge ms-2"
            style={{ border: `1px solid ${missionActive ? 'var(--lv3)' : 'var(--text-muted)'}` }}
          >
            <span
              className={`status-dot ${missionActive ? 'online' : 'offline'}`}
              aria-hidden="true"
            />
            <span className="flight-status-label">
              {FLIGHT_STATUS_LABELS[currentFlightStatus] ?? currentFlightStatus}
            </span>
          </Badge>
        </Navbar.Brand>

        <div className="d-flex align-items-center gap-2 order-lg-3">
          <Navbar.Toggle aria-controls="main-navbar-telemetry" className="navbar-toggle-sm" />
        </div>

        <Navbar.Collapse id="main-navbar-telemetry" className="order-lg-2">
          <div className="telemetry-chip-row">
            <div className="telemetry-chip">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={getBatteryColor(battery)} strokeWidth="2">
                <rect x="1" y="6" width="18" height="12" rx="2" ry="2" />
                <line x1="23" y1="10" x2="23" y2="14" />
                <rect x="3" y="8" width={`${(battery / 100) * 14}`} height="8" fill={getBatteryColor(battery)} rx="1" />
              </svg>
              <div className="telemetry-chip-text">
                <span className="telemetry-chip-label">Batería</span>
                <span className="telemetry-chip-value" style={{ color: getBatteryColor(battery) }}>
                  {battery.toFixed(0)}%
                </span>
              </div>
            </div>

            <div className="telemetry-chip">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={getSignalColor(signal)} strokeWidth="2">
                <path d="M2 20h.01M7 20v-4M12 20v-8M17 20v-12M22 20v-16" />
              </svg>
              <div className="telemetry-chip-text">
                <span className="telemetry-chip-label">Señal UDP</span>
                <span className="telemetry-chip-value">{signal.toFixed(0)}%</span>
              </div>
            </div>

            <div className="telemetry-chip">
              <div className="telemetry-chip-text">
                <span className="telemetry-chip-label">Altitud</span>
                <span className="telemetry-chip-value">{altitude.toFixed(1)} m</span>
              </div>
            </div>

            <div className="telemetry-chip">
              <div className="telemetry-chip-text">
                <span className="telemetry-chip-label">Velocidad</span>
                <span className="telemetry-chip-value">{speed.toFixed(1)} m/s</span>
              </div>
            </div>

            <div className="telemetry-chip">
              <div className="telemetry-chip-text">
                <span className="telemetry-chip-label">Temperatura</span>
                <span className="telemetry-chip-value">{temperature.toFixed(0)}°C</span>
              </div>
            </div>

            <div className="telemetry-chip">
              <div className="telemetry-chip-text">
                <span className="telemetry-chip-label">Latencia</span>
                <span className="telemetry-chip-value" style={{ color: getLatencyColor(latencyMs) }}>
                  {latencyMs === null ? '—' : `${latencyMs.toFixed(0)} ms`}
                </span>
              </div>
            </div>

            {!isConnected && connectionError && (
              <div className="telemetry-chip telemetry-chip-error">
                ⚠️ {connectionError}
              </div>
            )}
          </div>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  )
}
