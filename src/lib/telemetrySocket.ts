import { TelemetryCommand } from './commands'

const SHARED_TOKEN = import.meta.env.VITE_SHARED_TOKEN as string | undefined

export type TelemetrySocketCommand = TelemetryCommand

export interface TelemetrySocket {
  sendCommand: (command: TelemetrySocketCommand) => boolean
  readyState: () => number
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
  const pendingCommands: TelemetrySocketCommand[] = []

  const flushPendingCommands = () => {
    while (pendingCommands.length > 0) {
      const nextCommand = pendingCommands.shift()
      if (!nextCommand) continue
      if (socket.readyState === WebSocket.OPEN) {
        const withToken = { ...nextCommand, token: nextCommand.token ?? SHARED_TOKEN }
        socket.send(JSON.stringify(withToken))
      } else {
        break
      }
    }
  }

  socket.onopen = () => {
    flushPendingCommands()
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
      const withToken = { ...command, token: command.token ?? SHARED_TOKEN }
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(withToken))
        return true
      }

      pendingCommands.push(command)
      return true
    },
    readyState: () => socket.readyState,
    close: () => {
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close()
      }
    },
  }
}
