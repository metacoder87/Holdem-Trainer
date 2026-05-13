import { useEffect, useRef, useState } from "react";
import { WS_URL, type GameHandState } from "./client";

type SocketStatus = "idle" | "connecting" | "open" | "closed" | "error";

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

  useEffect(() => {
    if (!sessionId) {
      setStatus("idle");
      setState(null);
      return;
    }

    const url = `${WS_URL}/ws/sessions/${encodeURIComponent(sessionId)}`;
    setStatus("connecting");

    let cancelled = false;
    let socket: WebSocket;
    try {
      socket = new WebSocket(url);
    } catch {
      setStatus("error");
      return;
    }

    socketRef.current = socket;

    socket.addEventListener("open", () => {
      if (!cancelled) setStatus("open");
    });
    socket.addEventListener("error", () => {
      if (!cancelled) setStatus("error");
    });
    socket.addEventListener("close", () => {
      if (!cancelled) setStatus("closed");
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

    return () => {
      cancelled = true;
      try {
        socket.close();
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
