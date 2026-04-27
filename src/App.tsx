import { Container } from 'react-bootstrap'
import { TelemetryProvider, useTelemetryContext } from '@/contexts/TelemetryContext'
import TelemetryBar from './components/TelemetryBar'
import MapContainer from './components/MapContainer'
import ScorePanel from './components/ScorePanel'
import BigScoreSummary from './components/BigScoreSummary'
import MissionControl from './components/MissionControl'

function AppContent() {
  const { telemetry } = useTelemetryContext()
  const missionActive = telemetry.drone.flightStatus !== 'idle' && telemetry.drone.flightStatus !== 'descenso'

  return (
    <div className="app-container">
      <TelemetryBar />
      
      <Container fluid className="main-content">
        <header className="text-center fade-up mb-4">
          <h1 className="main-title">AgroDron</h1>
          <p className="subtitle">Sistema Autónomo de Riego Inteligente</p>
        </header>

        <div className="row g-4">
          <div className="col-lg-8">
            <div className="fade-up delay-1">
              <MapContainer missionActive={missionActive} />
            </div>
          </div>
          
          <div className="col-lg-4">
            <div className="d-flex flex-column gap-4">
              <div className="fade-up delay-2">
                <ScorePanel />
              </div>
              
              <div className="fade-up delay-3">
                <BigScoreSummary humidity={telemetry.averageHumidity} />
              </div>
              
              <div className="fade-up delay-4">
                <MissionControl />
              </div>
            </div>
          </div>
        </div>
      </Container>
    </div>
  )
}

export default function App() {
  return (
    <TelemetryProvider>
      <AppContent />
    </TelemetryProvider>
  )
}
