import { useTelemetryContext } from '@/contexts/TelemetryContext'

export default function MissionControl() {
  const { telemetry, startMission, stopMission } = useTelemetryContext()
  const missionActive = telemetry.drone.flightStatus !== 'idle' && telemetry.drone.flightStatus !== 'descenso'

  return (
    <div className="glass panel-card">
      <h3 className="panel-title">Control de Misión</h3>
      
      <button
        className={`mission-btn ${missionActive ? 'active' : ''}`}
        onClick={() => {
          if (missionActive) stopMission()
          else startMission('sur')
        }}
      >
        {missionActive ? (
          <>
            <span style={{ marginRight: '0.5rem' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="6" width="12" height="12" rx="2"/>
              </svg>
            </span>
            Detener Misión
          </>
        ) : (
          <>
            <span style={{ marginRight: '0.5rem' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5,3 19,12 5,21"/>
              </svg>
            </span>
            Iniciar Misión Autónoma
          </>
        )}
      </button>

      {!missionActive && (
        <p 
          className="text-center mt-3 mb-0" 
          style={{ 
            fontSize: '0.875rem', 
            color: 'var(--text-muted)',
            fontStyle: 'italic'
          }}
        >
          El dron despegará, regará y volverá solo
        </p>
      )}

      {missionActive && (
        <div className="mt-3">
          <div className="d-flex justify-content-between align-items-center">
            <small style={{ color: 'var(--text-secondary)' }}>Progreso de misión</small>
            <small style={{ color: 'var(--lv3)' }}>En curso...</small>
          </div>
          <div className="score-bar-container mt-2">
            <div 
              className="score-bar-fill lv3"
              style={{ 
                width: '0%',
                animation: 'progress-fill 30s linear forwards'
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
