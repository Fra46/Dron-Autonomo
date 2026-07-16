export interface DroneCommand {
  type: 'start_mission' | 'stop_mission' | 'emergency_stop' | 'request_status' | 'set_mode'
  target_zone?: string
  mode?: 'auto' | 'manual'
  [key: string]: unknown
}

export interface TelemetryCommand extends DroneCommand {
  // Extensible for future telemetry commands
}