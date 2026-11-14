/**
 * HAMMY — Observatory State & WebSocket Hook (`web/src/hooks/usePetObservatory.ts`).
 * Manages REST hydration, WebSocket state streaming, and auto-reconnection state restoration.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchPet,
  fetchPetEvents,
  fetchPetState,
  pauseSimulation,
  resumeSimulation,
} from "../api";
import { ConnectionStatus, Pet, PetState, WorldEvent } from "../types";

export function usePetObservatory(petId: string, token?: string) {
  const [pet, setPet] = useState<Pet | null>(null);
  const [state, setState] = useState<PetState | null>(null);
  const [events, setEvents] = useState<WorldEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("disconnected");

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  // Initial REST data hydration
  const refresh = useCallback(async () => {
    try {
      const [petData, stateData, eventsData] = await Promise.all([
        fetchPet(petId, token),
        fetchPetState(petId, token),
        fetchPetEvents(petId, 50, token),
      ]);
      setPet(petData);
      setState(stateData);
      setEvents(eventsData);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load pet observatory data");
    } finally {
      setLoading(false);
    }
  }, [petId, token]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // WebSocket Connection & Reconnection Management
  useEffect(() => {
    let unmounted = false;

    function connectWebSocket() {
      if (unmounted) return;

      const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const wsUrl = `${wsProtocol}//${host}/api/v1/pets/${petId}/ws${
        token ? `?token=${encodeURIComponent(token)}` : ""
      }`;

      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          if (unmounted) return;
          setConnectionStatus("connected");
        };

        ws.onmessage = (event) => {
          if (unmounted) return;
          try {
            const data = JSON.parse(event.data);
            if (data.type === "snapshot") {
              // Server state snapshot received upon initial connect or reconnect
              setState((prev) => {
                if (!prev) return prev;
                return {
                  ...prev,
                  version: data.version ?? prev.version,
                  sim_time_sec: data.sim_time_sec ?? prev.sim_time_sec,
                  drives: data.drives ?? prev.drives,
                  position_xyz: data.position_xyz ?? prev.position_xyz,
                  is_paused: data.is_paused ?? prev.is_paused,
                };
              });
            } else if (data.type === "event" && data.event) {
              setEvents((prev) => [data.event, ...prev.slice(0, 49)]);
            }
          } catch (e) {
            console.error("Error parsing WebSocket message:", e);
          }
        };

        ws.onclose = () => {
          if (unmounted) return;
          setConnectionStatus("reconnecting");
          // Reconnect after 3 seconds
          reconnectTimeoutRef.current = window.setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = () => {
          if (unmounted) return;
          ws.close();
        };
      } catch (e) {
        if (!unmounted) {
          setConnectionStatus("disconnected");
          reconnectTimeoutRef.current = window.setTimeout(connectWebSocket, 3000);
        }
      }
    }

    connectWebSocket();

    return () => {
      unmounted = true;
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [petId, token]);

  const handlePause = async () => {
    await pauseSimulation(petId, token);
    await refresh();
  };

  const handleResume = async () => {
    await resumeSimulation(petId, token);
    await refresh();
  };

  return {
    pet,
    state,
    events,
    loading,
    error,
    connectionStatus,
    pause: handlePause,
    resume: handleResume,
    refresh,
  };
}

