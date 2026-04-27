import { useTelemetryContext } from '@/contexts/TelemetryContext'
import { Row, Col, Badge } from 'react-bootstrap'

const FLIGHT_STATUS_LABELS: Record<string, string> = {
  idle: 'En Espera',
  ascenso: 'Despegando',
  navegando: 'En Vuelo',
  regando: 'Regando',
  retorno: 'Regresando',
  descenso: 'Aterrizando',
}

export default function TelemetryBar() {
  const { telemetry, isConnected, connectionError } = useTelemetryContext()
  const missionActive = telemetry.drone.flightStatus !== 'idle' && telemetry.drone.flightStatus !== 'descenso'

  const battery = telemetry.drone.battery ?? 100
  const signal = telemetry.signal ?? 0
  const altitude = telemetry.drone.position.altitude ?? 0
  const speed = telemetry.speed ?? 0
  const temperature = telemetry.temperature ?? 0
  const currentFlightStatus = telemetry.drone.flightStatus ?? 'idle'

  const getBatteryColor = (level: number) => {
    if (level > 60) return 'var(--lv3)'
    if (level > 30) return 'var(--lv2)'
    return 'var(--lv0)'
  }

  const getSignalBars = (signalValue: number) => {
    const bars = Math.min(4, Math.max(0, Math.ceil(signalValue / 25)))
    return Array.from({ length: 4 }, (_, i) => (
      <div
        key={i}
        style={{
          width: '4px',
          height: `${(i + 1) * 4}px`,
          backgroundColor: i < bars ? 'var(--lv3)' : 'var(--text-muted)',
          borderRadius: '1px'
        }}
      />
    ))
  }

  return (
    <div className="telemetry-bar glass">
      <Row className="align-items-center g-3">
        <Col xs={6} md={2}>
          <div className="telemetry-item">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={getBatteryColor(battery)} strokeWidth="2">
              <rect x="1" y="6" width="18" height="12" rx="2" ry="2"/>
              <line x1="23" y1="10" x2="23" y2="14"/>
              <rect x="3" y="8" width={`${(battery / 100) * 14}`} height="8" fill={getBatteryColor(battery)} rx="1"/>
            </svg>
            <div>
              <div className="telemetry-label">Batería</div>
              <div className="telemetry-value" style={{ color: getBatteryColor(battery) }}>
                {battery.toFixed(0)}%
              </div>
            </div>
          </div>
        </Col>

        <Col xs={6} md={2}>
          <div className="telemetry-item">
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: '2px', height: '20px' }}>
              {getSignalBars(signal)}
            </div>
            <div>
              <div className="telemetry-label">Señal UDP</div>
              <div className="telemetry-value">{signal.toFixed(0)}%</div>
            </div>
          </div>
        </Col>

        <Col xs={4} md={2}>
          <div className="telemetry-item">
            <div>
              <div className="telemetry-label">Altitud</div>
              <div className="telemetry-value">{altitude.toFixed(1)}m</div>
            </div>
          </div>
        </Col>

        <Col xs={4} md={2}>
          <div className="telemetry-item">
            <div>
              <div className="telemetry-label">Velocidad</div>
              <div className="telemetry-value">{speed.toFixed(1)} m/s</div>
            </div>
          </div>
        </Col>

        <Col xs={4} md={2}>
          <div className="telemetry-item">
            <div>
              <div className="telemetry-label">Temp</div>
              <div className="telemetry-value">{temperature.toFixed(0)}°C</div>
            </div>
          </div>
        </Col>

        <Col xs={12} md={2} className="text-md-end">
          <Badge 
            bg="dark" 
            className="px-3 py-2"
            style={{ 
              border: `1px solid ${missionActive ? 'var(--lv3)' : 'var(--text-muted)'}`,
              fontSize: '0.75rem'
            }}
          >
            <span 
              className={`status-dot ${missionActive ? 'online' : 'offline'}`}
              style={{ display: 'inline-block', marginRight: '8px' }}
            />
            {FLIGHT_STATUS_LABELS[currentFlightStatus] ?? currentFlightStatus}
          </Badge>
          {!isConnected && connectionError && (
            <div className="mt-1" style={{ color: 'var(--lv0)', fontSize: '0.75rem' }}>
              ⚠️ {connectionError}
            </div>
          )}
        </Col>
      </Row>
    </div>
  )
}
