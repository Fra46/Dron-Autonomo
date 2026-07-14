import { useState } from 'react'
import { useTelemetryContext } from '@/contexts/TelemetryContext'

type MissionZone = 'norte' | 'centro' | 'sur'

const ZONE_LABELS: Record<MissionZone, string> = {
  norte: 'Norte',
  centro: 'Centro',
  sur: 'Sur',
}

export default function MissionControl() {
  const { telemetry, startMission, stopMission } = useTelemetryContext()
  const [selectedZone, setSelectedZone] = useState<MissionZone>('sur')
  const activeTargetZone = telemetry.drone.targetZone ?? selectedZone

  const status = telemetry.drone.flightStatus
  const isReturning = status === 'retorno'
  const missionActive = ['ascenso', 'navegando', 'regando', 'retorno'].includes(status)
  const canStop = ['ascenso', 'navegando', 'regando'].includes(status)

  const buttonLabel = isReturning
    ? 'Regresando a base...'
    : missionActive
    ? 'Detener Misión'
    : `Iniciar misión a ${ZONE_LABELS[selectedZone]}`

  return (
    <div className="glass panel-card">
      <h3 className="panel-title">Control de Misión</h3>

      {!missionActive && (
        <div className="zone-selection mb-3">
          <small className="text-secondary">Selecciona una zona objetivo</small>
          <div className="d-flex gap-2 flex-wrap mt-2">
            {(['sur', 'centro', 'norte'] as MissionZone[]).map(zone => (
              <button
                key={zone}
                type="button"
                className={`mission-zone-btn ${selectedZone === zone ? 'active' : ''}`}
                onClick={() => setSelectedZone(zone)}
              >
                {ZONE_LABELS[zone]}
              </button>
            ))}
          </div>
        </div>
      )}

      <button
        className={`mission-btn ${missionActive ? 'active' : ''}`}
        disabled={isReturning}
        onClick={() => {
          if (!missionActive) {
            startMission(selectedZone)
          } else if (canStop) {
            stopMission()
          }
        }}
      >
        <span style={{ marginRight: '0.5rem' }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            {missionActive ? (
              <rect x="6" y="6" width="12" height="12" rx="2" />
            ) : (
              <polygon points="5,3 19,12 5,21" />
            )}
          </svg>
        </span>
        {buttonLabel}
      </button>

      {!missionActive && (
        <p
          className="text-center mt-3 mb-0"
          style={{
            fontSize: '0.875rem',
            color: 'var(--text-muted)',
            fontStyle: 'italic',
          }}
        >
          El dron despegará, regará la zona seleccionada y regresará a base.
        </p>
      )}

      {missionActive && (
        <div className="mt-3">
          <div className="d-flex justify-content-between align-items-center mb-2">
            <small style={{ color: 'var(--text-secondary)' }}>Zona objetivo</small>
            <small style={{ color: 'var(--lv4)' }}>{ZONE_LABELS[activeTargetZone]}</small>
          </div>
          <div className="d-flex justify-content-between align-items-center">
            <small style={{ color: 'var(--text-secondary)' }}>Progreso de misión</small>
            <small style={{ color: 'var(--lv3)' }}>
              {isReturning ? 'Regresando...' : 'En curso...'}
            </small>
          </div>
          <div className="score-bar-container mt-2">
            <div
              className="score-bar-fill lv3"
              style={{
                width: '0%',
                animation: 'progress-fill 30s linear forwards',
              }}
            />
          </div>
          <style>{`
            @keyframes progress-fill {
              from { width: 0%; }
              to { width: 100%; }
            }
          `}</style>
        </div>
      )}
    </div>
  )
}
