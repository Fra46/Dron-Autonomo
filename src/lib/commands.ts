export interface DroneCommand {
  type: 'auth' | 'start_mission' | 'stop_mission' | 'emergency_stop' | 'request_status' | 'set_mode'
  target_zone?: string
  mode?: 'auto' | 'manual'
  [key: string]: unknown
  token?: string
}

export interface TelemetryCommand extends DroneCommand {
  // Extensible for future telemetry commands
}