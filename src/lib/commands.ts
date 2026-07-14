export interface DroneCommand {
  type: 'start_mission' | 'stop_mission' | 'emergency_stop'
  target_zone?: string
  [key: string]: unknown
}

export interface TelemetryCommand extends DroneCommand {
  // Extensible for future telemetry commands
}