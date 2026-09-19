"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  SendIcon,
  MessageSquareIcon,
  Loader2Icon,
  AlertCircleIcon,
  InfoIcon,
} from "lucide-react";
import {
  listFirmware,
  explainFirmware,
  analyzeFirmware,
  isMultipleExplanations,
  type Firmware,
  type ExplanationResponse,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";

type ChatMessage = { role: "user" | "assistant"; text: string };

/**
 * Answers a question about a single firmware's report by matching
 * keywords against the fields CryptoSage's backend actually returned
 * (algorithm, risk score, summary, recommendations, references).
 *
 * This is intentionally NOT a call to an LLM — the backend has no chat
 * endpoint, so rather than fake a "live AI" that isn't there, this stays
 * grounded entirely in the report's own data. It's a lightweight,
 * always-accurate FAQ over one report, not a general-purpose assistant.
 */
function answerFromReport(question: string, report: ExplanationResponse): string {
  const q = question.toLowerCase();

  if (/(algorithm|cipher|crypto)\b.*(use|detect|find|is)/.test(q) || /what.*(algorithm|cipher)/.test(q)) {
    return `This binary (${report.binary_name}) uses **${report.algorithm}**, part of the ${report.algorithm_family} family, detected with ${(report.confidence * 100).toFixed(1)}% confidence.`;
  }

  if (/risk|score|dangerous|safe|critical/.test(q)) {
    return `Its risk score is **${report.risk_score.toFixed(0)}/100**, rated **${report.risk_level}**. ${
      report.risk_level === "Safe" || report.risk_level === "Low"
        ? "That's on the lower end of the scale."
        : "You may want to prioritize the recommendations below."
    }`;
  }

  if (/recommend|fix|remediat|do next|should i/.test(q)) {
    if (!report.recommendations?.length) return "This report doesn't include any specific recommendations.";
    return `Recommended next steps:\n${report.recommendations.map((r) => `• ${r}`).join("\n")}`;
  }

  if (/reference|standard|cite|source/.test(q)) {
    if (!report.references?.length) return "This report doesn't cite any specific standards.";
    return `Referenced standards: ${report.references.join(", ")}.`;
  }

  if (/summary|explain|overview|why/.test(q)) {
    return report.summary;
  }

  if (/confidence|sure|certain/.test(q)) {
    return `The model is ${(report.confidence * 100).toFixed(1)}% confident in this algorithm classification.`;
  }

  // Fallback: return the summary since it's the most generally useful answer.
  return `Here's what this report says: ${report.summary}\n\nYou can also ask about the algorithm, risk score, recommendations, or references.`;
}

export default function ReportChat({ initialFirmwareId }: { initialFirmwareId?: number }) {
  const [firmwareList, setFirmwareList] = useState<Firmware[] | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(initialFirmwareId ?? null);
  const [reports, setReports] = useState<ExplanationResponse[] | null>(null);
  const [activeReportIdx, setActiveReportIdx] = useState(0);
  const [loadingReport, setLoadingReport] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listFirmware()
      .then(setFirmwareList)
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  const loadReport = useCallback(async (id: number) => {
    setLoadingReport(true);
    setError(null);
    setMessages([]);
    try {
      let data;
      try {
        data = await explainFirmware(id);
      } catch {
        await analyzeFirmware(id);
        data = await explainFirmware(id);
      }
      const list = isMultipleExplanations(data) ? data.explanations : [data];
      setReports(list);
      setActiveReportIdx(0);
      setMessages([
        {
          role: "assistant",
          text: `I've loaded the report for ${list[0].binary_name}. Ask me about its algorithm, risk score, recommendations, or references.`,
        },
      ]);
    } catch (err) {
      setError(getErrorMessage(err));
      setReports(null);
    } finally {
      setLoadingReport(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) loadReport(selectedId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const activeReport = reports?.[activeReportIdx];

  const send = () => {
    if (!input.trim() || !activeReport) return;
    const question = input.trim();
    setMessages((prev) => [
      ...prev,
      { role: "user", text: question },
      { role: "assistant", text: answerFromReport(question, activeReport) },
    ]);
    setInput("");
  };

  return (
    <div className="w-full max-w-3xl mx-auto space-y-4">
      <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-500/30 rounded-xl px-4 py-3">
        <InfoIcon className="h-4 w-4 shrink-0 text-violet-600 dark:text-violet-300" />
        <span>
          This assistant only answers from the selected firmware&apos;s own analysis report — it
          won&apos;t guess beyond what CryptoSage actually found.
        </span>
      </div>

      {error && (
        <Card className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-500/30 flex items-center gap-2">
          <AlertCircleIcon className="h-4 w-4 text-red-600 dark:text-red-400 shrink-0" />
          <span className="text-sm text-red-600 dark:text-red-300">{error}</span>
        </Card>
      )}

      <Card className="p-4 bg-white/90 dark:bg-black/80 border border-violet-500/30">
        <label className="text-xs font-bold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2 block">
          Firmware Report
        </label>
        <select
          className="w-full rounded-lg border border-violet-500/30 bg-transparent px-3 py-2 text-sm text-gray-900 dark:text-white"
          value={selectedId ?? ""}
          onChange={(e) => setSelectedId(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="" disabled>
            {firmwareList === null ? "Loading firmware…" : "Select a firmware…"}
          </option>
          {firmwareList?.map((fw) => (
            <option key={fw.id} value={fw.id}>
              {fw.filename}
            </option>
          ))}
        </select>

        {reports && reports.length > 1 && (
          <div className="flex flex-wrap gap-2 mt-3">
            {reports.map((r, i) => (
              <button
                key={r.binary_name + i}
                onClick={() => setActiveReportIdx(i)}
                className={`px-3 py-1 rounded-full text-xs font-bold border transition-colors ${
                  i === activeReportIdx
                    ? "bg-violet-600 text-white border-violet-600"
                    : "border-violet-500/30 text-gray-600 dark:text-gray-300 hover:bg-violet-500/10"
                }`}
              >
                {r.binary_name}
              </button>
            ))}
          </div>
        )}
      </Card>

      <Card className="bg-white/90 dark:bg-black/80 border border-violet-500/30 flex flex-col h-[420px]">
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
          {!selectedId && (
            <div className="h-full flex flex-col items-center justify-center text-center gap-3 text-gray-500 dark:text-gray-500">
              <MessageSquareIcon className="h-8 w-8" />
              <p className="text-sm">Pick a firmware above to start asking about its report.</p>
            </div>
          )}

          {loadingReport && (
            <div className="h-full flex items-center justify-center">
              <Loader2Icon className="h-6 w-6 text-violet-500 animate-spin" />
            </div>
          )}

          {!loadingReport &&
            messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-line ${
                    m.role === "user"
                      ? "bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white"
                      : "bg-violet-50 dark:bg-violet-900/30 text-gray-800 dark:text-gray-200 border border-violet-200 dark:border-violet-500/20"
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}
        </div>

        <div className="border-t border-violet-500/20 p-3 flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            disabled={!activeReport}
            placeholder={activeReport ? "Ask about this report…" : "Select a firmware first"}
            className="flex-1 rounded-xl border border-violet-500/30 bg-transparent px-4 py-2 text-sm text-gray-900 dark:text-white disabled:opacity-50"
          />
          <Button onClick={send} disabled={!activeReport || !input.trim()} size="icon">
            <SendIcon className="h-4 w-4" />
          </Button>
        </div>
      </Card>
    </div>
  );
}
