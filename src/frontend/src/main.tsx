import React, { FormEvent, useMemo, useState } from "react";
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

const SESSION_KEY = "skynova-demo-login";

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(
    () => window.localStorage.getItem(SESSION_KEY) === "true"
  );

  if (!isLoggedIn) {
    return <LoginPage onLogin={() => setIsLoggedIn(true)} />;
  }

  return <ChatPage onLogout={() => setIsLoggedIn(false)} />;
}

function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim() || !password.trim()) {
      setError("Enter a username and password.");
      return;
    }
    window.localStorage.setItem(SESSION_KEY, "true");
    onLogin();
  }

  return (
    <main className="login-shell">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="brand-mark">SN</div>
        <h1 id="login-title">SkyNova Agent</h1>
        <form className="login-form" onSubmit={submit}>
          <label>
            Username
            <input
              autoComplete="username"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label>
            Password
            <input
              autoComplete="current-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error && <p className="form-error">{error}</p>}
          <button type="submit">Login</button>
        </form>
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
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: currentQuestion })
      });

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
    window.localStorage.removeItem(SESSION_KEY);
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
  return answer.split(/\n{2,}/).map((paragraph, index) => (
    <p key={`${paragraph}-${index}`}>{paragraph}</p>
  ));
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

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
