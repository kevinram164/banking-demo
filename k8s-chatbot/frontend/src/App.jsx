import { useState, useRef, useEffect } from "react";

const API = ""; // same origin

async function sendMessage(msg) {
  const res = await fetch(`${API}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: msg }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function Message({ role, content, intent }) {
  const isUser = role === "user";
  return (
    <div
      className={`message ${isUser ? "user" : "assistant"}`}
      style={{
        alignSelf: isUser ? "flex-end" : "flex-start",
        maxWidth: "85%",
        padding: "12px 16px",
        borderRadius: "12px",
        backgroundColor: isUser ? "var(--accent-dim)" : "var(--bg-card)",
        border: `1px solid ${isUser ? "var(--accent)" : "var(--border)"}`,
        whiteSpace: "pre-wrap",
        fontFamily: "inherit",
        fontSize: "13px",
      }}
    >
      <div style={{ marginBottom: intent ? "4px" : 0 }}>
        {content}
      </div>
      {intent && (
        <div
          style={{
            fontSize: "11px",
            color: "var(--text-muted)",
            marginTop: "6px",
          }}
        >
          intent: {intent}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const msg = input.trim();
    if (!msg || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setLoading(true);

    try {
      const { reply, intent } = await sendMessage(msg);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: reply, intent },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Lỗi: ${err.message}`,
          intent: null,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        maxWidth: "800px",
        margin: "0 auto",
        width: "100%",
        padding: "24px",
      }}
    >
      <header
        style={{
          padding: "16px 0",
          borderBottom: "1px solid var(--border)",
          marginBottom: "16px",
        }}
      >
        <h1 style={{ margin: 0, fontSize: "1.5rem", color: "var(--accent)" }}>
          K8s Chatbot
        </h1>
        <p style={{ margin: "4px 0 0", fontSize: "12px", color: "var(--text-muted)" }}>
          Ra lệnh quản lý cluster: pods, deployments, logs, restart...
        </p>
      </header>

      <div
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
          paddingBottom: "16px",
        }}
      >
        {messages.length === 0 && (
          <div
            style={{
              color: "var(--text-muted)",
              fontSize: "13px",
              padding: "24px",
            }}
          >
            Ví dụ:
            <ul style={{ margin: "8px 0 0 20px", lineHeight: 1.8 }}>
              <li>Check status pods của ns banking</li>
              <li>Rollout restart deployment của ns banking</li>
              <li>Tìm logs lỗi của auth-service-xxx</li>
            </ul>
          </div>
        )}
        {messages.map((m, i) => (
          <Message
            key={i}
            role={m.role}
            content={m.content}
            intent={m.intent}
          />
        ))}
        {loading && (
          <div
            style={{
              alignSelf: "flex-start",
              padding: "12px 16px",
              color: "var(--text-muted)",
              fontSize: "13px",
            }}
          >
            Đang xử lý...
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={handleSubmit}
        style={{
          display: "flex",
          gap: "8px",
          paddingTop: "16px",
          borderTop: "1px solid var(--border)",
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Nhập lệnh..."
          disabled={loading}
          style={{
            flex: 1,
            padding: "12px 16px",
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            borderRadius: "8px",
            color: "var(--text)",
            fontSize: "14px",
            fontFamily: "inherit",
          }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{
            padding: "12px 24px",
            background: "var(--accent)",
            color: "var(--bg-dark)",
            border: "none",
            borderRadius: "8px",
            fontWeight: 600,
            cursor: loading ? "not-allowed" : "pointer",
            opacity: loading || !input.trim() ? 0.6 : 1,
          }}
        >
          Gửi
        </button>
      </form>
    </div>
  );
}
