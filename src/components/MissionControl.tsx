import { useState } from 'react'
import { useTelemetryContext } from '@/contexts/TelemetryContext'

type MissionZone = 'norte' | 'centro' | 'sur'

const ZONE_LABELS: Record<MissionZone, string> = {
  norte: 'Norte',
  centro: 'Centro',
  sur: 'Sur',
}

export default function MissionControl() {
  const { telemetry, startMission, stopMission, emergencyStop, requestStatus, setMode } = useTelemetryContext()
  const [selectedZone, setSelectedZone] = useState<MissionZone>('sur')
  const [syncing, setSyncing] = useState(false)
  const rawTargetZone = telemetry.drone.targetZone
  const activeTargetZone: MissionZone =
    rawTargetZone === 'norte' || rawTargetZone === 'centro' || rawTargetZone === 'sur'
      ? rawTargetZone
      : selectedZone

  const status = telemetry.drone.flightStatus
  const isReturning = status === 'retorno'
  const missionActive = ['ascenso', 'navegando', 'regando', 'retorno'].includes(status)
  const canStop = ['ascenso', 'navegando', 'regando'].includes(status)
  const isAuto = telemetry.drone.mode === 'auto'

  const buttonLabel = isReturning
    ? 'Regresando a base...'
    : missionActive
    ? 'Detener Misión'
    : `Iniciar misión a ${ZONE_LABELS[selectedZone]}`

  return (
    <div className="glass panel-card">
      <h3 className="panel-title">Control de Misión</h3>

      {/* Modo de operacion: 2 formas de controlar el dron.
          - AUTO: el dron riega por su cuenta en cuanto detecta suelo seco,
            sin esperar ningun boton, hasta que se desactive este modo.
          - MANUAL: el dron solo despega cuando el granjero presiona el boton
            de mision de abajo. */}
      <div className="mode-toggle mb-3">
        <div>
          <div className="mode-toggle-title">Modo automático</div>
          <div className="mode-toggle-subtitle">
            {isAuto
              ? 'El dron riega por su cuenta cualquier zona seca que detecte.'
              : 'El dron solo actúa cuando presionas "Iniciar misión".'}
          </div>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={isAuto}
          className={`mode-switch ${isAuto ? 'on' : 'off'}`}
          onClick={() => setMode(isAuto ? 'manual' : 'auto')}
        >
          <span className="mode-switch-thumb" />
        </button>
      </div>

      {!isAuto && !missionActive && (
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

      {!isAuto && (
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
          <span className="mission-btn-icon">
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
      )}

      {missionActive && (
        <button
          type="button"
          onClick={() => emergencyStop()}
          className="emergency-stop-btn"
        >
          Parada de emergencia
        </button>
      )}

      <button
        type="button"
        disabled={syncing}
        onClick={() => {
          setSyncing(true)
          requestStatus()
          setTimeout(() => setSyncing(false), 800)
        }}
        className="sync-status-btn"
      >
        {syncing ? 'Sincronizando…' : 'Sincronizar estado'}
      </button>

      {!missionActive && (
        <p className="mission-idle-hint">
          {isAuto
            ? 'En espera: despegará solo en cuanto una zona baje de humedad.'
            : 'El dron despegará, regará la zona seleccionada y regresará a base.'}
        </p>
      )}

      {missionActive && (
        <div className="mission-progress mt-3">
          <div className="d-flex justify-content-between align-items-center mb-2">
            <small className="mission-progress-label">Zona objetivo</small>
            <small className="mission-progress-zone">{ZONE_LABELS[activeTargetZone]}</small>
          </div>
          <div className="d-flex justify-content-between align-items-center">
            <small className="mission-progress-label">Progreso de misión</small>
            <small className="mission-progress-value">
              {isReturning ? 'Regresando... ' : ''}
              {Math.round((telemetry.drone.missionProgress ?? 0) * 100)}%
            </small>
          </div>
          <div className="score-bar-container mt-2">
            <div
              className="score-bar-fill lv3"
              style={{ width: `${Math.max(4, (telemetry.drone.missionProgress ?? 0) * 100)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}