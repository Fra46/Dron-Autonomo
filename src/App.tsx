import { Container } from 'react-bootstrap'
import { TelemetryProvider, useTelemetryContext } from '@/contexts/TelemetryContext'
import { ThemeProvider } from '@/contexts/ThemeContext'
import TelemetryBar from './components/TelemetryBar'
import MapContainer from './components/MapContainer'
import BigScoreSummary from './components/BigScoreSummary'
import MissionControl from './components/MissionControl'
import FloatingThemeToggle from './components/FloatingThemeToggle'

function AppContent() {
  const { telemetry } = useTelemetryContext()
  const missionActive = ['ascenso', 'navegando', 'regando', 'retorno'].includes(telemetry.drone.flightStatus)

  return (
    <div className="app-container">
      <TelemetryBar />
      <FloatingThemeToggle />
      
      <Container fluid className="main-content">
        <div className="row g-4">
          <div className="col-lg-8">
            <div className="fade-up delay-1">
              <MapContainer missionActive={missionActive} />
            </div>

            {/* En móvil: mostrar MissionControl bajo el mapa */}
            <div className="fade-up delay-3 d-lg-none" style={{ marginTop: '1rem' }}>
              <MissionControl />
            </div>
          </div>

          <div className="col-lg-4">
            <div className="d-flex flex-column gap-4">
              {/* En escritorio: MissionControl arriba de Estado del Suelo */}
              <div className="fade-up delay-2 d-none d-lg-block">
                <MissionControl />
              </div>

              <div className="fade-up delay-2">
                <BigScoreSummary humidity={telemetry.averageHumidity} />
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
    <ThemeProvider>
      <TelemetryProvider>
        <AppContent />
      </TelemetryProvider>
    </ThemeProvider>
  )
}
