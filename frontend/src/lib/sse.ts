/**
 * SSE (Server-Sent Events) client wrapper.
 * Supports Last-Event-ID for resume capability (RF-08).
 */

import { API_URL } from "./constants";

export interface SSEOptions {
  /** Called when connection opens */
  onOpen?: () => void;
  /** Called on each event */
  onMessage: (event: MessageEvent) => void;
  /** Called on error */
  onError?: (error: Event) => void;
  /** Last event ID for resume */
  lastEventId?: string;
}

export interface SSEConnection {
  /** Close the connection */
  close: () => void;
  /** Get the EventSource instance */
  source: EventSource;
}

/**
 * Create an SSE connection with resume capability.
 *
 * @param path - API path to connect to
 * @param options - SSE options
 * @returns SSE connection object
 */
export function createSSEConnection(
  path: string,
  options: SSEOptions
): SSEConnection {
  const url = new URL(`${API_URL}${path}`);

  // Add Last-Event-ID as query param if provided (for resume)
  if (options.lastEventId) {
    url.searchParams.set("last_event_id", options.lastEventId);
  }

  const source = new EventSource(url.toString());

  source.onopen = () => {
    options.onOpen?.();
  };

  source.onmessage = (event) => {
    options.onMessage(event);
  };

  source.onerror = (error) => {
    options.onError?.(error);
  };

  return {
    close: () => source.close(),
    source,
  };
}

/**
 * Parse SSE event data as JSON.
 *
 * @param event - MessageEvent from SSE
 * @returns Parsed JSON data
 */
export function parseSSEEvent<T>(event: MessageEvent): T {
  return JSON.parse(event.data as string) as T;
}
