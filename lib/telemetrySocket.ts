import { TelemetryCommand } from './commands'

export type TelemetrySocketCommand = TelemetryCommand

export interface TelemetrySocket {
  sendCommand: (command: TelemetrySocketCommand) => void
  close: () => void
}

export interface TelemetrySocketHandlers {
  onOpen?: () => void
  onMessage: (message: string) => void
  onError?: (error: Event | Error) => void
  onClose?: () => void
}

export function createTelemetrySocket(
  wsUrl: string,
  handlers: TelemetrySocketHandlers,
): TelemetrySocket | null {
  if (typeof window === 'undefined') {
    return null
  }

  const socket = new WebSocket(wsUrl)

  socket.onopen = () => {
    handlers.onOpen?.()
  }

  socket.onmessage = event => {
    handlers.onMessage(event.data.toString())
  }

  socket.onerror = event => {
    handlers.onError?.(event)
  }

  socket.onclose = () => {
    handlers.onClose?.()
  }

  return {
    sendCommand: command => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(command))
      }
    },
    close: () => {
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close()
      }
    },
  }
}
