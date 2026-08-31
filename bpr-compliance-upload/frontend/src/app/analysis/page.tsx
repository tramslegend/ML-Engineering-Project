"use client";

import { useEffect, useRef, useState } from "react";
import { Database, Sparkles, Send, Terminal, Workflow, ChevronDown } from "lucide-react";
import AuthShell from "@/components/AuthShell";
import AnalysisChart from "@/components/AnalysisChart";
import Markdown from "@/components/Markdown";
import { AnalysisResult, runAnalysis } from "@/lib/api";

const EXAMPLE_QUESTIONS = [
  "How many transactions are currently flagged and open, and what's the average transaction amount overall?",
  "Which customers have the most escalated flags, and what rules did they trigger?",
  "Visualize a bar chart of flagged transaction count by rule triggered.",
];

interface ChatMessage {
  id: string;
  question: string;
  status: "loading" | "done" | "error";
  result?: AnalysisResult;
  error?: string;
}

function AgentDetail({ result }: { result: AnalysisResult }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2.5 border-t border-bpr-hairline pt-2.5">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 text-[11.5px] text-bpr-ink2/50 transition-colors hover:text-bpr-navy"
      >
        <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} strokeWidth={2} />
        {open ? "Hide" : "Show"} agent detail
      </button>
      {open && (
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          <div className="rounded-lg border border-bpr-hairline bg-bpr-parchment/50 p-2.5">
            <p className="mb-1 flex items-center gap-1.5 text-[10.5px] font-medium uppercase tracking-wide text-bpr-ink2/50">
              <Database className="h-3 w-3" strokeWidth={1.75} /> SQL Agent
            </p>
            <div className="text-[12px] text-bpr-ink2/75">
              {result.sql_result ? <Markdown>{result.sql_result}</Markdown> : "— skipped —"}
            </div>
          </div>
          <div className="rounded-lg border border-bpr-hairline bg-bpr-parchment/50 p-2.5">
            <p className="mb-1 flex items-center gap-1.5 text-[10.5px] font-medium uppercase tracking-wide text-bpr-ink2/50">
              <Terminal className="h-3 w-3" strokeWidth={1.75} /> Python Agent
            </p>
            <div className="text-[12px] text-bpr-ink2/75">
              <Markdown>{result.python_result}</Markdown>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AnalysisPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  // One thread per page load -- the backend uses this to restore conversation
  // memory (LangGraph checkpointing) across turns, so follow-ups like "break
  // that down by month" can resolve against what was actually asked before.
  const threadIdRef = useRef<string>(crypto.randomUUID());

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const busy = messages.some((m) => m.status === "loading");

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    const id = crypto.randomUUID();
    setMessages((prev) => [...prev, { id, question, status: "loading" }]);
    setInput("");
    try {
      const result = await runAnalysis(question, threadIdRef.current);
      setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, status: "done", result } : m)));
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === id ? { ...m, status: "error", error: err instanceof Error ? err.message : "Analysis failed" } : m
        )
      );
    }
  }

  return (
    <AuthShell eyebrow="LangGraph · SQL Agent · Python Agent" title="Compliance Analysis">
      <div className="flex h-[calc(100vh-172px)] flex-col">
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-bpr-brass/15">
                <Sparkles className="h-5 w-5 text-bpr-brass" strokeWidth={1.75} />
              </div>
              <p className="text-[15px] font-medium text-bpr-navy">Ask anything about compliance data</p>
              <p className="mt-1.5 max-w-sm text-[12.5px] leading-relaxed text-bpr-ink2/50">
                A LangGraph pipeline routes your question through a LangChain SQL Agent (read-only Postgres) and a
                LangChain pandas/Python agent, then synthesizes both into one answer.
              </p>
              <div className="mt-6 flex max-w-xl flex-wrap justify-center gap-2">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => ask(q)}
                    className="rounded-full border border-bpr-hairline bg-bpr-card px-3.5 py-2 text-left text-[12.5px] text-bpr-ink2/80 transition-colors hover:border-bpr-brass/40 hover:text-bpr-navy"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-5 pb-4">
              {messages.map((m) => (
                <div key={m.id} className="space-y-3">
                  <div className="flex justify-end">
                    <div className="max-w-[80%] rounded-2xl rounded-tr-md bg-bpr-navy px-4 py-2.5 text-[13.5px] leading-relaxed text-bpr-parchment">
                      {m.question}
                    </div>
                  </div>

                  <div className="flex items-start gap-2.5">
                    <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-bpr-brass/15">
                      <Sparkles className="h-3.5 w-3.5 text-bpr-brass" strokeWidth={1.75} />
                    </div>
                    <div className="min-w-0 max-w-[85%] flex-1 rounded-2xl rounded-tl-md border border-bpr-hairline bg-bpr-card px-4 py-3">
                      {m.status === "loading" && (
                        <p className="flex items-center gap-2 text-[13px] text-bpr-ink2/60">
                          <Workflow className="h-4 w-4 animate-pulse text-bpr-brass" strokeWidth={1.75} />
                          Running SQL Agent → Python Agent → synthesis...
                        </p>
                      )}
                      {m.status === "error" && <p className="text-[13px] text-bpr-rose">{m.error}</p>}
                      {m.status === "done" && m.result && (
                        <div>
                          <div className="text-[13.5px] text-bpr-ink2/90">
                            <Markdown>{m.result.final_answer}</Markdown>
                          </div>

                          {m.result.chart_data && m.result.chart_data.length > 0 && (
                            <div className="mt-3 h-64 rounded-lg border border-bpr-hairline bg-bpr-parchment/40 p-2">
                              <AnalysisChart chartType={m.result.chart_type ?? "bar"} data={m.result.chart_data} />
                            </div>
                          )}

                          <AgentDetail result={m.result} />
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(input);
          }}
          className="mx-auto mt-3 flex w-full max-w-3xl shrink-0 items-center gap-2 rounded-2xl border border-bpr-hairline bg-bpr-card px-3.5 py-2.5 shadow-ledger"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Message Compliance Analysis..."
            disabled={busy}
            className="flex-1 bg-transparent text-[13.5px] outline-none placeholder:text-bpr-ink2/40 disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-bpr-navy text-bpr-parchment transition-colors hover:bg-bpr-navyLight disabled:opacity-40"
          >
            <Send className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
        </form>
      </div>
    </AuthShell>
  );
}
