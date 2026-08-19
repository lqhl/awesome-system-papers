export function devWebsocketExpression(remoteDevHost: string | undefined, wsPort: number) {
  if (remoteDevHost) {
    return JSON.stringify(`wss://${remoteDevHost}:${wsPort}`)
  }

  return `(window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.hostname + ":${wsPort}"`
}
