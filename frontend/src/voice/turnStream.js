// Client for POST /api/student/interviews/{id}/turn (Server-Sent Events over fetch, so it can carry a JSON body
// and the auth cookie). Calls handlers[eventName](data) as events arrive; resolves when the stream ends.
import { ApiError } from "../api";

/** Pure SSE parser: feed text chunks, get complete {event, data} objects back. */
export function createSseParser() {
  let buf = "";
  return (chunk) => {
    buf += chunk.replace(/\r\n/g, "\n");
    const out = [];
    let i;
    while ((i = buf.indexOf("\n\n")) !== -1) {
      const block = buf.slice(0, i);
      buf = buf.slice(i + 2);
      let event = "message";
      const data = [];
      for (const line of block.split("\n")) {
        if (line.startsWith(":")) continue; // keep-alive comment
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
      }
      if (data.length) {
        try { out.push({ event, data: JSON.parse(data.join("\n")) }); } catch { /* ignore malformed block */ }
      }
    }
    return out;
  };
}

export async function streamTurn(sessionId, body, handlers, { signal } = {}) {
  let res;
  try {
    res = await fetch(`/api/student/interviews/${sessionId}/turn`, {
      method: "POST", credentials: "include", signal,
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError("Cannot reach the server. Is the backend running?", 0);
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try { detail = (await res.json()).detail || detail; } catch { /* not JSON */ }
    if (res.status === 401) window.dispatchEvent(new Event("hs:unauthorized"));
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), res.status);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parse = createSseParser();
  let finished = false;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const { event, data } of parse(decoder.decode(value, { stream: true }))) {
      if (event === "done" || event === "error") finished = true;
      handlers[event]?.(data);
    }
  }
  if (!finished) throw new ApiError("The connection to the interviewer was interrupted.", 0);
}
