"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import ReportCard from "@/components/firmware/ReportCard";
import { motion, AnimatePresence } from "framer-motion";
import {
  UploadCloudIcon,
  FileIcon,
  AlertCircleIcon,
  Loader2Icon,
  ShieldCheckIcon,
  MessageSquareIcon,
} from "lucide-react";
import {
  uploadFirmware,
  analyzeFirmware,
  explainFirmware,
  isDuplicateResponse,
  isMultipleExplanations,
  type ExplanationResponse,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import Link from "next/link";

type Stage = "idle" | "uploading" | "analyzing" | "explaining" | "done" | "error";

const stageLabel: Record<Stage, string> = {
  idle: "",
  uploading: "Uploading firmware…",
  analyzing: "Extracting & analyzing binaries…",
  explaining: "Running prediction, risk scoring & explanation…",
  done: "Analysis complete",
  error: "Analysis failed",
};

export default function FirmwareUploadWidget() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const existingId = searchParams.get("id");

  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<ExplanationResponse[] | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const [firmwareId, setFirmwareId] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const reset = useCallback(() => {
    setFile(null);
    setStage("idle");
    setError(null);
    setResults(null);
    setActiveIdx(0);
    setFirmwareId(null);
    router.replace("/analyze");
  }, [router]);

  const handleFile = (f: File) => {
    const validExt = [".bin", ".img", ".elf"].some((ext) => f.name.toLowerCase().endsWith(ext));
    if (!validExt) {
      setError("Firmware must be a .bin, .img, or .elf file.");
      return;
    }
    setError(null);
    setFile(f);
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  }, []);

  const runExplainPipeline = useCallback(async (id: number, opts?: { skipAnalyze?: boolean }) => {
    try {
      if (!opts?.skipAnalyze) {
        setStage("analyzing");
        await analyzeFirmware(id);
      }

      setStage("explaining");
      let explainData;
      try {
        explainData = await explainFirmware(id);
      } catch (err) {
        // If explain 404s because analysis hasn't run yet, fall back to
        // running the analysis step then retry once.
        if (opts?.skipAnalyze) {
          setStage("analyzing");
          await analyzeFirmware(id);
          setStage("explaining");
          explainData = await explainFirmware(id);
        } else {
          throw err;
        }
      }

      const list = isMultipleExplanations(explainData) ? explainData.explanations : [explainData];
      setResults(list);
      setActiveIdx(0);
      setFirmwareId(id);
      setStage("done");
    } catch (err) {
      setError(getErrorMessage(err));
      setStage("error");
    }
  }, []);

  // If an ?id= is present (re-run from Firmware History), skip the upload
  // step entirely and jump straight to explain (falling back to analyze
  // first if no feature vectors exist yet).
  useEffect(() => {
    if (existingId && stage === "idle") {
      const id = Number(existingId);
      if (!Number.isNaN(id)) {
        setFirmwareId(id);
        runExplainPipeline(id, { skipAnalyze: true });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingId]);

  const runFullPipeline = async () => {
    if (!file) return;
    setError(null);

    try {
      setStage("uploading");
      const uploadData = await uploadFirmware(file);

      if (isDuplicateResponse(uploadData)) {
        // Already-uploaded firmware — go straight to explain, which will
        // fall back to analyze if this particular firmware was never
        // actually analyzed before.
        await runExplainPipeline(uploadData.id, { skipAnalyze: true });
        return;
      }

      await runExplainPipeline(uploadData.id);
    } catch (err) {
      setError(getErrorMessage(err));
      setStage("error");
    }
  };

  const active = results?.[activeIdx];
  const inProgress = stage === "uploading" || stage === "analyzing" || stage === "explaining";

  return (
    <div className="w-full max-w-4xl mx-auto px-4 py-4 flex flex-col justify-center flex-1">
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mb-6 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-500/30 rounded-lg flex items-start gap-2"
          >
            <AlertCircleIcon className="h-4 w-4 text-red-600 dark:text-red-400 mt-0.5" />
            <div className="flex-1 text-sm text-red-600 dark:text-red-300">{error}</div>
            <button onClick={() => setError(null)} className="text-red-600 hover:text-red-800">
              ✕
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="text-center mb-4">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          Analyze Your{" "}
          <span className="bg-gradient-to-r from-violet-600 to-fuchsia-600 dark:from-violet-400 dark:to-fuchsia-400 bg-clip-text text-transparent">
            Firmware Image
          </span>
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Cryptographic detection, risk scoring & evidence-backed explanation
        </p>
      </div>

      {stage === "idle" || (stage === "error" && !existingId) ? (
        <>
          <Card
            onDragOver={(e) => {
              e.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            className={`p-10 border-2 border-dashed transition-all cursor-pointer bg-white/90 dark:bg-black/80 ${
              dragActive
                ? "border-violet-500 bg-violet-50/50 dark:bg-violet-900/10"
                : "border-violet-500/30 hover:border-violet-500/50"
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".bin,.img,.elf"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
              }}
            />
            <div className="flex flex-col items-center text-center gap-3">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-violet-100 to-fuchsia-100 dark:from-violet-900/40 dark:to-fuchsia-900/40 shadow-[0_0_20px_rgba(139,92,246,0.3)]">
                <UploadCloudIcon className="h-8 w-8 text-violet-600 dark:text-violet-300" />
              </div>
              {file ? (
                <div className="flex items-center gap-2 text-gray-800 dark:text-gray-200">
                  <FileIcon className="h-4 w-4" />
                  <span className="text-sm font-medium">{file.name}</span>
                </div>
              ) : (
                <>
                  <p className="text-sm font-medium text-gray-800 dark:text-gray-200">
                    Drop a firmware image or click to browse
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-500">
                    .bin, .img, or .elf — up to 500MB
                  </p>
                </>
              )}
            </div>
          </Card>

          <div className="flex justify-center mt-6">
            <Button onClick={runFullPipeline} disabled={!file} size="lg" className="min-w-[220px]">
              <ShieldCheckIcon className="mr-2 h-5 w-5" />
              Run Full Analysis
            </Button>
          </div>
        </>
      ) : inProgress ? (
        <Card className="p-10 bg-white/90 dark:bg-black/80 border border-violet-500/30">
          <div className="flex flex-col items-center gap-4">
            <Loader2Icon className="h-10 w-10 text-violet-600 dark:text-violet-300 animate-spin" />
            <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{stageLabel[stage]}</p>
            <div className="flex gap-2">
              {(["uploading", "analyzing", "explaining"] as Stage[]).map((s) => (
                <div
                  key={s}
                  className={`h-1.5 w-12 rounded-full ${s === stage ? "bg-violet-500" : "bg-violet-500/20"}`}
                />
              ))}
            </div>
          </div>
        </Card>
      ) : stage === "error" ? (
        <Card className="p-10 bg-white/90 dark:bg-black/80 border border-red-500/30 text-center space-y-4">
          <p className="text-sm text-gray-700 dark:text-gray-300">
            This firmware could not be analyzed. See the error above for details.
          </p>
          <Button variant="outline" onClick={reset}>
            Try Another Firmware
          </Button>
        </Card>
      ) : (
        <div className="space-y-4">
          {results && results.length > 1 && (
            <div className="flex flex-wrap gap-2 justify-center">
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

          <div className="flex flex-wrap justify-center gap-3 pt-2">
            {firmwareId && (
              <Link href={`/assistant?firmwareId=${firmwareId}`}>
                <Button variant="outline">
                  <MessageSquareIcon className="mr-2 h-4 w-4" />
                  Ask About This Report
                </Button>
              </Link>
            )}
            <Button variant="outline" onClick={reset}>
              Analyze Another Firmware
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
