"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import ReportCard from "@/components/firmware/ReportCard";
import {
  ArrowLeftIcon,
  Loader2Icon,
  AlertCircleIcon,
  MessageSquareIcon,
  RefreshCwIcon,
} from "lucide-react";
import {
  getFirmware,
  analyzeFirmware,
  explainFirmware,
  isMultipleExplanations,
  type Firmware,
  type ExplanationResponse,
} from "@/lib/api";
import { getErrorMessage, formatDate } from "@/lib/utils";

export default function FirmwareReport({ firmwareId }: { firmwareId: number }) {
  const [firmware, setFirmware] = useState<Firmware | null>(null);
  const [results, setResults] = useState<ExplanationResponse[] | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const meta = await getFirmware(firmwareId);
      setFirmware(meta);

      let data;
      try {
        data = await explainFirmware(firmwareId);
      } catch {
        // No feature vectors yet for this firmware — run the extraction
        // step first, then retry.
        await analyzeFirmware(firmwareId);
        data = await explainFirmware(firmwareId);
      }

      const list = isMultipleExplanations(data) ? data.explanations : [data];
      setResults(list);
      setActiveIdx(0);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [firmwareId]);

  useEffect(() => {
    load();
  }, [load]);

  const active = results?.[activeIdx];

  return (
    <div className="space-y-6 max-w-4xl mx-auto w-full">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between flex-wrap gap-3">
        <Link href="/firmware" className="inline-flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-violet-600 dark:hover:text-violet-300">
          <ArrowLeftIcon className="h-4 w-4" />
          Back to Firmware History
        </Link>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCwIcon className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Re-run
        </Button>
      </motion.div>

      {firmware && (
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white truncate">
            {firmware.filename}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-500 mt-1">
            Uploaded {formatDate(firmware.upload_time)} · {firmware.file_hash.slice(0, 16)}…
          </p>
        </div>
      )}

      {error && (
        <Card className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-500/30 flex items-center gap-2">
          <AlertCircleIcon className="h-4 w-4 text-red-600 dark:text-red-400 shrink-0" />
          <span className="text-sm text-red-600 dark:text-red-300">{error}</span>
        </Card>
      )}

      {loading && (
        <Card className="p-10 bg-white/90 dark:bg-black/80 border border-violet-500/30 flex flex-col items-center gap-3">
          <Loader2Icon className="h-8 w-8 text-violet-600 dark:text-violet-300 animate-spin" />
          <p className="text-sm text-gray-600 dark:text-gray-400">Loading report…</p>
        </Card>
      )}

      {!loading && results && (
        <div className="space-y-4">
          {results.length > 1 && (
            <div className="flex flex-wrap gap-2">
              {results.map((r, i) => (
                <button
                  key={r.binary_name + i}
                  onClick={() => setActiveIdx(i)}
                  className={`px-3 py-1.5 rounded-full text-xs font-bold border transition-colors ${
                    i === activeIdx
                      ? "bg-violet-600 text-white border-violet-600"
                      : "border-violet-500/30 text-gray-600 dark:text-gray-300 hover:bg-violet-500/10"
                  }`}
                >
                  {r.binary_name}
                </button>
              ))}
            </div>
          )}

          {active && <ReportCard result={active} />}

          <div className="flex justify-center pt-2">
            <Link href={`/assistant?firmwareId=${firmwareId}`}>
              <Button variant="outline">
                <MessageSquareIcon className="mr-2 h-4 w-4" />
                Ask About This Report
              </Button>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
