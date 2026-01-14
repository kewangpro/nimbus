import { useEffect, useRef } from 'react';

const SOCKET_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/api/v1/ws';

export const useWebSocket = (onMessage: (data: unknown) => void) => {
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Generate a random client ID
    const clientId = Math.random().toString(36).substring(7);
    ws.current = new WebSocket(`${SOCKET_URL}/${clientId}`);

    ws.current.onopen = () => {
      console.log('WebSocket Connected');
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (e) {
        console.error('Failed to parse WebSocket message', e);
      }
    };

    ws.current.onclose = () => {
      console.log('WebSocket Disconnected');
    };

    return () => {
      ws.current?.close();
    };
  }, [onMessage]);
};
