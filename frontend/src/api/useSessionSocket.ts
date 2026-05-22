import { useEffect, useRef, useState } from "react";
import { WS_URL, type GameHandState } from "./client";

type SocketStatus = "idle" | "connecting" | "reconnecting" | "open" | "closed" | "error";

export type SessionSocket = {
  status: SocketStatus;
  state: GameHandState | null;
  send: (payload: Record<string, unknown>) => void;
  startHand: () => void;
  submitInput: (value: number | string | boolean) => void;
  refresh: () => void;
};

export function useSessionSocket(sessionId: string | null): SessionSocket {
  const [status, setStatus] = useState<SocketStatus>("idle");
  const [state, setState] = useState<GameHandState | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const retryRef = useRef(0);

  useEffect(() => {
    if (!sessionId) {
      setStatus("idle");
      setState(null);
      return;
    }

    let cancelled = false;
    const url = `${WS_URL}/ws/sessions/${encodeURIComponent(sessionId)}`;

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const connect = () => {
      if (cancelled) return;
      clearReconnectTimer();
      setStatus(retryRef.current > 0 ? "reconnecting" : "connecting");

      let socket: WebSocket;
      try {
        socket = new WebSocket(url);
      } catch {
        scheduleReconnect();
        return;
      }

      socketRef.current = socket;

      socket.addEventListener("open", () => {
        if (cancelled) return;
        retryRef.current = 0;
        setStatus("open");
        socket.send(JSON.stringify({ action: "snapshot" }));
      });
      socket.addEventListener("error", () => {
        if (!cancelled) setStatus("error");
      });
      socket.addEventListener("close", () => {
        if (cancelled) return;
        if (socketRef.current !== socket) return;
        socketRef.current = null;
        scheduleReconnect();
      });
      socket.addEventListener("message", (event) => {
        if (cancelled) return;
        try {
          const payload = JSON.parse(event.data);
          if (payload && payload.session_id) {
            setState(payload as GameHandState);
          } else if (payload && typeof payload.error === "string") {
            // server-side error for an action; surface via state.error
            setState((prev) =>
              prev ? { ...prev, error: payload.error } : prev
            );
          }
        } catch {
          // ignore non-JSON frames
        }
      });
    };

    const scheduleReconnect = () => {
      if (cancelled) return;
      if (reconnectTimerRef.current !== null) return;
      retryRef.current += 1;
      setStatus("reconnecting");
      const baseDelay = Math.min(1000 * 2 ** Math.min(retryRef.current - 1, 5), 30000);
      const jitter = Math.floor(Math.random() * 250);
      reconnectTimerRef.current = window.setTimeout(connect, baseDelay + jitter);
    };

    retryRef.current = 0;
    connect();

    return () => {
      cancelled = true;
      clearReconnectTimer();
      try {
        socketRef.current?.close();
      } catch {
        // ignore
      }
      socketRef.current = null;
    };
  }, [sessionId]);

  const send = (payload: Record<string, unknown>) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify(payload));
  };

  return {
    status,
    state,
    send,
    startHand: () => send({ action: "start" }),
    submitInput: (value) => send({ action: "input", value }),
    refresh: () => send({ action: "snapshot" })
  };
}
