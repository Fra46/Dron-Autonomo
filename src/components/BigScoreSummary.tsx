import { useMemo } from 'react'
import { Row, Col } from 'react-bootstrap'

interface BigScoreSummaryProps {
  humidity: number
}

export default function BigScoreSummary({ humidity }: BigScoreSummaryProps) {
  const irrigationStatus = useMemo(() => {
    if (humidity < 40) {
      return {
        type: 'opportune' as const,
        label: 'Oportuno',
        description: 'El suelo necesita riego inmediato',
        recommendation: 'Iniciar misión de riego',
        urgency: 'Alta'
      }
    }
    return {
      type: 'strategic' as const,
      label: 'Estratégico',
      description: 'Niveles de humedad adecuados',
      recommendation: 'Programar siguiente revisión',
      urgency: 'Baja'
    }
  }, [humidity])

  const stats = useMemo(() => {
    const nextWindow = humidity < 40 ? 'Ahora' : `${Math.ceil((humidity - 40) / 5)} hrs`
    const priorityAreas = humidity < 40 ? 4 : humidity < 55 ? 2 : 0
    
    return { nextWindow, priorityAreas }
  }, [humidity])

  return (
    <div className="glass panel-card">
      <h3 className="panel-title">Estado del Suelo</h3>
      
      <div className="text-center mb-3">
        <div className={`big-score ${irrigationStatus.type}`}>
          {irrigationStatus.label}
        </div>
        <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem', marginBottom: 0 }}>
          {irrigationStatus.description}
        </p>
      </div>

      <Row className="g-3 mt-2">
        <Col xs={6}>
          <div className="glass-subtle p-3 text-center">
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
              Próxima Ventana
            </div>
            <div style={{ 
              fontFamily: 'var(--font-heading)', 
              fontSize: '1.25rem', 
              fontWeight: 700,
              color: stats.nextWindow === 'Ahora' ? 'var(--lv0)' : 'var(--text-primary)'
            }}>
              {stats.nextWindow}
            </div>
          </div>
        </Col>
        <Col xs={6}>
          <div className="glass-subtle p-3 text-center">
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
              Áreas Prioritarias
            </div>
            <div style={{ 
              fontFamily: 'var(--font-heading)', 
              fontSize: '1.25rem', 
              fontWeight: 700,
              color: stats.priorityAreas > 0 ? 'var(--lv1)' : 'var(--lv3)'
            }}>
              {stats.priorityAreas}
            </div>
          </div>
        </Col>
      </Row>

      <div 
        className="mt-3 p-2 text-center"
        style={{ 
          backgroundColor: irrigationStatus.type === 'opportune' 
            ? 'rgba(255, 59, 48, 0.1)' 
            : 'rgba(52, 199, 89, 0.1)',
          borderRadius: 'var(--border-radius-sm)',
          border: `1px solid ${irrigationStatus.type === 'opportune' ? 'rgba(255, 59, 48, 0.2)' : 'rgba(52, 199, 89, 0.2)'}`
        }}
      >
        <small style={{ color: irrigationStatus.type === 'opportune' ? 'var(--lv0)' : 'var(--lv3)' }}>
          Recomendación: {irrigationStatus.recommendation}
        </small>
      </div>
    </div>
  )
}
