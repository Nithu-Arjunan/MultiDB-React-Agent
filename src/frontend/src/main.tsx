import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type ToolCall = {
  tool: string;
  input: string;
  output: string;
};

type ChatResponse = {
  answer: string;
  tool_calls: ToolCall[];
  warnings: string[];
  elapsed_ms: number;
};

type TraceEvent = {
  type: string;
  label: string;
  detail: string;
};

type ChatTurn = {
  id: number;
  question: string;
  response: ChatResponse;
  traceEvents: TraceEvent[];
};

type AuthUser = {
  sub: string;
  email: string;
  name: string;
  picture: string;
};

type AuthResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
};

type GoogleCredentialResponse = {
  credential: string;
};

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: GoogleCredentialResponse) => void;
          }) => void;
          renderButton: (
            element: HTMLElement,
            options: { theme: string; size: string; width: number }
          ) => void;
        };
      };
    };
  }
}

const TOKEN_KEY = "skynova-auth-token";
const USER_KEY = "skynova-auth-user";

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isCheckingSession, setIsCheckingSession] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function validateStoredSession() {
      const token = window.localStorage.getItem(TOKEN_KEY);
      if (!token) {
        setIsCheckingSession(false);
        return;
      }

      try {
        const response = await fetch("/auth/me", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          removeStoredSession();
          setIsLoggedIn(false);
          return;
        }
        if (!cancelled) {
          setIsLoggedIn(true);
        }
      } catch {
        removeStoredSession();
        if (!cancelled) {
          setIsLoggedIn(false);
        }
      } finally {
        if (!cancelled) {
          setIsCheckingSession(false);
        }
      }
    }

    validateStoredSession();

    return () => {
      cancelled = true;
    };
  }, []);

  if (isCheckingSession) {
    return (
      <main className="login-shell">
        <section className="login-panel" aria-live="polite">
          <div className="brand-mark">SN</div>
          <p className="muted">Checking session...</p>
        </section>
      </main>
    );
  }

  if (!isLoggedIn) {
    return <LoginPage onLogin={() => setIsLoggedIn(true)} />;
  }

  return <ChatPage onLogout={() => setIsLoggedIn(false)} />;
}

function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function setupGoogleLogin() {
      try {
        const response = await fetch("/auth/config");
        const config = (await response.json()) as { google_client_id: string };
        if (!config.google_client_id) {
          throw new Error("Google client ID is not configured.");
        }

        await waitForGoogleIdentity();
        if (cancelled) {
          return;
        }

        window.google?.accounts.id.initialize({
          client_id: config.google_client_id,
          callback: handleGoogleCredential,
        });

        const button = document.getElementById("google-signin-button");
        if (button) {
          window.google?.accounts.id.renderButton(button, {
            theme: "outline",
            size: "large",
            width: 320,
          });
        }
        setIsLoading(false);
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : "Google login failed.";
        setError(message);
        setIsLoading(false);
      }
    }

    async function handleGoogleCredential(googleResponse: GoogleCredentialResponse) {
      try {
        setError("");
        const response = await fetch("/auth/google", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ credential: googleResponse.credential }),
        });

        if (!response.ok) {
          throw new Error("Google sign-in was rejected.");
        }

        const auth = (await response.json()) as AuthResponse;
        window.localStorage.setItem(TOKEN_KEY, auth.access_token);
        window.localStorage.setItem(USER_KEY, JSON.stringify(auth.user));
        onLogin();
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : "Google login failed.";
        setError(message);
      }
    }

    setupGoogleLogin();

    return () => {
      cancelled = true;
    };
  }, [onLogin]);

  return (
    <main className="login-shell">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="brand-mark">SN</div>
        <h1 id="login-title">SkyNova Agent</h1>
        <div className="login-form">
          <div id="google-signin-button" className="google-button-slot" />
          {isLoading && <p className="muted">Loading Google sign-in...</p>}
          {error && <p className="form-error">{error}</p>}
        </div>
      </section>
    </main>
  );
}

function ChatPage({ onLogout }: { onLogout: () => void }) {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const latestTurn = turns[0];
  const canSubmit = question.trim().length > 0 && !isLoading;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }

    const currentQuestion = question.trim();
    setQuestion("");
    setIsLoading(true);
    setError("");

    try {
      const token = window.localStorage.getItem(TOKEN_KEY);
      if (!token) {
        throw new Error("Please sign in again.");
      }

      const turnId = Date.now();
      setTurns((existing) => [
        {
          id: turnId,
          question: currentQuestion,
          response: { answer: "", tool_calls: [], warnings: [], elapsed_ms: 0 },
          traceEvents: [],
        },
        ...existing,
      ]);

      const response = await fetch("/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ question: currentQuestion })
      });

      if (response.status === 401) {
        removeStoredSession();
        onLogout();
        throw new Error("Your session expired. Please sign in again.");
      }

      if (!response.ok) {
        throw new Error(`Request failed with ${response.status}`);
      }

      await readSseStream(response, (event) => {
        setTurns((existing) =>
          existing.map((turn) =>
            turn.id === turnId ? applyStreamEventToTurn(turn, event) : turn
          )
        );
      });
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Request failed.";
      setError(message);
      setQuestion(currentQuestion);
    } finally {
      setIsLoading(false);
    }
  }

  function logout() {
    removeStoredSession();
    onLogout();
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">SkyNova</p>
          <h1>Multi DB React Agent</h1>
        </div>
        <button className="ghost-button" type="button" onClick={logout}>
          Logout
        </button>
      </header>

      <section className="workspace">
        <form className="composer" onSubmit={submit}>
          <label htmlFor="question">Question</label>
          <div className="composer-row">
            <textarea
              id="question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about flights, support tickets, reviews, activity logs, or policies."
              rows={3}
            />
            <button type="submit" disabled={!canSubmit}>
              {isLoading ? "Sending" : "Ask"}
            </button>
          </div>
          {error && <p className="form-error">{error}</p>}
        </form>

        <div className="results-grid">
          <section className="answer-pane" aria-live="polite">
            <h2>Answer</h2>
            {isLoading && <p className="muted">Thinking...</p>}
            {!isLoading && !latestTurn && <p className="muted">No question submitted yet.</p>}
            {latestTurn && <ChatResult turn={latestTurn} />}
          </section>

          <section className="history-pane">
            <h2>History</h2>
            <div className="history-list">
              {turns.map((turn) => (
                <button
                  className="history-item"
                  key={turn.id}
                  type="button"
                  onClick={() => setTurns([turn, ...turns.filter((item) => item.id !== turn.id)])}
                >
                  {turn.question}
                </button>
              ))}
              {turns.length === 0 && <p className="muted">No previous turns.</p>}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}

function ChatResult({ turn }: { turn: ChatTurn }) {
  const toolCount = turn.response.tool_calls.length;
  const elapsed = useMemo(() => `${turn.response.elapsed_ms} ms`, [turn.response.elapsed_ms]);

  return (
    <article className="chat-result">
      <section className="result-section">
        <h3>User question</h3>
        <p>{turn.question}</p>
      </section>

      <section className="result-section">
        <h3>Final answer</h3>
        <div className="answer-text">{formatFinalAnswer(turn.response.answer)}</div>
      </section>

      <section className="result-section">
        <div className="trace-heading">
          <h3>Agent trace</h3>
          <span>{turn.traceEvents.length} events</span>
        </div>
        <div className="agent-event-list">
          {turn.traceEvents.map((event, index) => (
            <div className="agent-event" key={`${event.type}-${index}`}>
              <strong>{event.label}</strong>
              <span>{event.detail}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="result-section">
        <div className="trace-heading">
          <h3>Tool call trace</h3>
          <span>{toolCount} calls</span>
        </div>
        {toolCount === 0 ? (
          <p className="muted">No tools were called.</p>
        ) : (
          <div className="trace-list">
            {turn.response.tool_calls.map((call, index) => (
              <details className="trace-item" key={`${call.tool}-${index}`} open={index === 0}>
                <summary>
                  <span>{call.tool}</span>
                  <small>Call {index + 1}</small>
                </summary>
                <TraceBlock label="Arguments" value={call.input} />
                <TraceBlock label="Returned" value={call.output} />
              </details>
            ))}
          </div>
        )}
      </section>

      {turn.response.warnings.length > 0 && (
        <section className="result-section warning-section">
          <h3>Warnings</h3>
          <ul>
            {turn.response.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      )}

      <p className="elapsed">Elapsed: {elapsed}</p>
    </article>
  );
}

function TraceBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="trace-block">
      <span>{label}</span>
      <pre>{formatTraceValue(value)}</pre>
    </div>
  );
}

function formatTraceValue(value: string) {
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}

function formatFinalAnswer(answer: string) {
  if (!answer.trim()) {
    return <p className="muted">Waiting for final answer...</p>;
  }

  const markdownTable = formatMarkdownTableAnswer(answer);
  if (markdownTable) {
    return markdownTable;
  }

  return answer.split(/\n{2,}/).map((paragraph, index) => (
    <p key={`${paragraph}-${index}`}>{paragraph}</p>
  ));
}

function formatMarkdownTableAnswer(answer: string) {
  const lines = answer
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const tableStart = lines.findIndex((line) => line.startsWith("|") && line.endsWith("|"));
  if (tableStart < 0 || tableStart + 2 >= lines.length) {
    return null;
  }

  const intro = lines.slice(0, tableStart).join(" ");
  const headers = splitMarkdownTableRow(lines[tableStart]);
  const separator = lines[tableStart + 1];
  if (!separator.includes("---")) {
    return null;
  }

  const rows = lines
    .slice(tableStart + 2)
    .filter((line) => line.startsWith("|") && line.endsWith("|"))
    .map(splitMarkdownTableRow);

  if (!headers.length || !rows.length) {
    return null;
  }

  return (
    <>
      {intro && <p>{intro}</p>}
      <div className="answer-card-grid">
        {rows.map((row, rowIndex) => (
          <div className="answer-card" key={`${row.join("-")}-${rowIndex}`}>
            {headers.map((header, index) => (
              <div className="answer-field" key={`${header}-${index}`}>
                <span>{humanizeHeader(header)}</span>
                <strong>{row[index] || "N/A"}</strong>
              </div>
            ))}
          </div>
        ))}
      </div>
    </>
  );
}

function splitMarkdownTableRow(row: string) {
  return row
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function humanizeHeader(header: string) {
  return header.replace(/_/g, " ");
}

async function readSseStream(
  response: Response,
  onEvent: (event: Record<string, unknown>) => void
) {
  if (!response.body) {
    throw new Error("Streaming response is not available.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const messages = buffer.split("\n\n");
    buffer = messages.pop() ?? "";

    for (const message of messages) {
      const dataLine = message
        .split("\n")
        .find((line) => line.startsWith("data: "));
      if (!dataLine) {
        continue;
      }
      onEvent(JSON.parse(dataLine.slice(6)) as Record<string, unknown>);
    }
  }
}

function applyStreamEventToTurn(turn: ChatTurn, event: Record<string, unknown>): ChatTurn {
  const type = String(event.type ?? "message");

  if (type === "thinking") {
    return appendTraceEvent(turn, {
      type,
      label: "Thinking",
      detail: String(event.message ?? "Agent started."),
    });
  }

  if (type === "action") {
    const tool = String(event.tool ?? "tool");
    const input = JSON.stringify(event.input ?? {}, null, 2);
    return appendTraceEvent(
      {
        ...turn,
        response: {
          ...turn.response,
          tool_calls: [...turn.response.tool_calls, { tool, input, output: "" }],
        },
      },
      { type, label: "Action", detail: `${tool} called.` }
    );
  }

  if (type === "observation") {
    const tool = String(event.tool ?? "tool");
    const output = String(event.output ?? "");
    const toolCalls = [...turn.response.tool_calls];
    const index = findLastToolCallIndex(toolCalls, tool);
    if (index >= 0) {
      toolCalls[index] = { ...toolCalls[index], output };
    } else {
      toolCalls.push({ tool, input: "", output });
    }
    return appendTraceEvent(
      { ...turn, response: { ...turn.response, tool_calls: toolCalls } },
      { type, label: "Observation", detail: `${tool} returned data.` }
    );
  }

  if (type === "answer") {
    return appendTraceEvent(
      {
        ...turn,
        response: { ...turn.response, answer: String(event.answer ?? "") },
      },
      { type, label: "Answer", detail: "Final answer received." }
    );
  }

  if (type === "done") {
    return appendTraceEvent(
      {
        ...turn,
        response: {
          ...turn.response,
          elapsed_ms: Number(event.elapsed_ms ?? 0),
        },
      },
      { type, label: "Done", detail: "Stream complete." }
    );
  }

  if (type === "error") {
    return appendTraceEvent(turn, {
      type,
      label: "Error",
      detail: String(event.message ?? "Streaming failed."),
    });
  }

  return turn;
}

function appendTraceEvent(turn: ChatTurn, event: TraceEvent): ChatTurn {
  return { ...turn, traceEvents: [...turn.traceEvents, event] };
}

function findLastToolCallIndex(toolCalls: ToolCall[], tool: string) {
  for (let index = toolCalls.length - 1; index >= 0; index -= 1) {
    if (toolCalls[index].tool === tool) {
      return index;
    }
  }
  return -1;
}

function removeStoredSession() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

function waitForGoogleIdentity() {
  return new Promise<void>((resolve, reject) => {
    const started = Date.now();
    const timer = window.setInterval(() => {
      if (window.google?.accounts?.id) {
        window.clearInterval(timer);
        resolve();
        return;
      }

      if (Date.now() - started > 8000) {
        window.clearInterval(timer);
        reject(new Error("Google sign-in script did not load."));
      }
    }, 100);
  });
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
