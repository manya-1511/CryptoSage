"use client";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { firmwareApi } from "@/lib/api";
import {
  formatBytes,
  formatDate,
  getStatusColor,
  getExtensionIcon,
} from "@/lib/utils";
import {
  Zap,
  Clock,
  HardDrive,
  Hash,
  ChevronLeft,
  FileCode2,
  Loader2,
  AlertCircle,
  Binary,
} from "lucide-react";
import Link from "next/link";
import toast from "react-hot-toast";
import { FileTree } from "@/components/firmware/FileTree";
import type { ExtractionResult } from "@/types/firmware";

function MetaRow({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex justify-between items-start py-2 border-b border-white/5 last:border-0">
      <span className="text-xs text-gray-500">{label}</span>
      <span className="font-mono text-xs text-gray-200 text-right max-w-[60%] break-all">
        {value}
      </span>
    </div>
  );
}

function ComponentBadges({
  summary,
}: {
  summary: ExtractionResult["component_summary"];
}) {
  if (!summary) return null;
  const groups = [
    {
      label: "Filesystems",
      items: summary.filesystems,
      color: "text-blue-400 bg-blue-400/10 border-blue-400/20",
    },
    {
      label: "Compression",
      items: summary.compression,
      color: "text-purple-400 bg-purple-400/10 border-purple-400/20",
    },
    {
      label: "Executables",
      items: summary.executables,
      color: "text-yellow-400 bg-yellow-400/10 border-yellow-400/20",
    },
    {
      label: "Kernels",
      items: summary.kernels,
      color: "text-sage-400 bg-sage-400/10 border-sage-400/20",
    },
    {
      label: "Bootloaders",
      items: summary.bootloaders,
      color: "text-orange-400 bg-orange-400/10 border-orange-400/20",
    },
    {
      label: "Certificates",
      items: summary.certificates,
      color: "text-red-400 bg-red-400/10 border-red-400/20",
    },
  ];
  return (
    <div className="space-y-3">
      {groups
        .filter((g) => g.items.length > 0)
        .map(({ label, items, color }) => (
          <div key={label}>
            <p className="text-xs text-gray-500 mb-1.5">{label}</p>
            <div className="flex flex-wrap gap-1.5">
              {items.map((item) => (
                <span key={item} className={`badge text-xs ${color}`}>
                  {item}
                </span>
              ))}
            </div>
          </div>
        ))}
    </div>
  );
}

export default function FirmwareDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { data: fw, isLoading: fwLoading } = useQuery({
    queryKey: ["firmware", id],
    queryFn: () => firmwareApi.getById(id),
    refetchInterval: (data) =>
      data?.state?.data?.status === "extracting" ? 2000 : false,
  });

  const { data: extractions } = useQuery({
    queryKey: ["extractions", id],
    queryFn: () => firmwareApi.listExtractions(id),
    enabled: !!fw,
    refetchInterval: (data) => {
      const items = data?.state?.data;
      const running = items?.some(
        (e: ExtractionResult) => e.status === "running",
      );
      return running ? 2000 : false;
    },
  });

  const extractMutation = useMutation({
    mutationFn: () => firmwareApi.extract(id),
    onSuccess: () => {
      toast.success("Extraction started");
      qc.invalidateQueries({ queryKey: ["firmware", id] });
      qc.invalidateQueries({ queryKey: ["extractions", id] });
    },
    onError: (err: any) =>
      toast.error(err?.response?.data?.detail ?? "Extraction failed"),
  });

  const latestExtraction = extractions?.[0];

  if (fwLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-sage-400" />
      </div>
    );
  }
  if (!fw) {
    return (
      <div className="text-center py-24 text-gray-500">
        <AlertCircle className="w-12 h-12 mx-auto mb-3 opacity-40" />
        <p>Firmware not found.</p>
      </div>
    );
  }

  const canExtract = ["valid", "extracted", "failed"].includes(fw.status);

  return (
    <div className="space-y-6 animate-fade-in max-w-5xl">
      {/* Back */}
      <Link href="/firmware" className="btn-ghost text-sm -ml-2">
        <ChevronLeft className="w-4 h-4" />
        Back to Library
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="text-3xl">
            {getExtensionIcon(fw.file_extension)}
          </span>
          <div>
            <h1 className="text-xl font-bold text-white break-all">
              {fw.original_filename}
            </h1>
            <p className="text-gray-500 text-sm font-mono mt-0.5">{fw.id}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className={`badge ${getStatusColor(fw.status)}`}>
            {fw.status}
          </span>
          {canExtract && (
            <button
              onClick={() => extractMutation.mutate()}
              disabled={extractMutation.isPending || fw.status === "extracting"}
              className="btn-primary"
            >
              {extractMutation.isPending || fw.status === "extracting" ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Extracting…
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  Extract
                </>
              )}
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Metadata */}
        <div className="col-span-1 card space-y-0">
          <h2 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
            <FileCode2 className="w-4 h-4 text-sage-400" />
            Metadata
          </h2>
          <MetaRow label="Size" value={formatBytes(fw.file_size)} />
          <MetaRow label="Extension" value={fw.file_extension} />
          <MetaRow label="MIME" value={fw.mime_type} />
          <MetaRow label="Architecture" value={fw.architecture} />
          <MetaRow label="Endianness" value={fw.endianness} />
          <MetaRow label="Vendor" value={fw.vendor} />
          <MetaRow label="Version" value={fw.version} />
          <MetaRow label="Uploaded" value={formatDate(fw.created_at)} />
        </div>

        {/* Hashes */}
        <div className="col-span-2 card">
          <h2 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
            <Hash className="w-4 h-4 text-sage-400" />
            Integrity
          </h2>
          <div className="space-y-3">
            {[
              { label: "SHA-256", value: fw.sha256_hash },
              { label: "MD5", value: fw.md5_hash },
            ].map(({ label, value }) => (
              <div key={label}>
                <p className="text-xs text-gray-500 mb-1">{label}</p>
                <p className="font-mono text-xs bg-white/5 rounded px-3 py-2 text-gray-300 break-all">
                  {value ?? "—"}
                </p>
              </div>
            ))}
          </div>

          {fw.validation_error && (
            <div className="mt-4 bg-red-500/10 border border-red-500/20 rounded-lg p-3 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <p className="text-xs text-red-300">{fw.validation_error}</p>
            </div>
          )}
        </div>
      </div>

      {/* Extraction Results */}
      {latestExtraction && (
        <div className="card space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
              <Binary className="w-4 h-4 text-sage-400" />
              Extraction Results
            </h2>
            <div className="flex items-center gap-3 text-xs text-gray-500">
              {latestExtraction.duration_seconds && (
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {latestExtraction.duration_seconds}s
                </span>
              )}
              <span className="flex items-center gap-1">
                <HardDrive className="w-3 h-3" />
                {latestExtraction.total_files_extracted} files ·{" "}
                {formatBytes(latestExtraction.total_size_extracted)}
              </span>
              <span
                className={`badge ${getStatusColor(latestExtraction.status)}`}
              >
                {latestExtraction.status}
              </span>
            </div>
          </div>

          {latestExtraction.status === "running" && (
            <div className="flex items-center gap-2 text-purple-400 text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              Extraction in progress…
            </div>
          )}

          {latestExtraction.status === "failed" && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-xs text-red-300">
              {latestExtraction.error_message}
            </div>
          )}

          {latestExtraction.status === "completed" && (
            <div className="grid grid-cols-2 gap-4">
              {/* Signatures */}
              <div>
                <p className="text-xs text-gray-500 mb-2 font-medium uppercase tracking-wide">
                  Binwalk Signatures (
                  {latestExtraction.scan_results?.length ?? 0})
                </p>
                <div className="space-y-1 max-h-64 overflow-y-auto pr-1">
                  {(latestExtraction.scan_results ?? []).map((sig, i) => (
                    <div
                      key={i}
                      className="bg-white/3 rounded px-3 py-2 text-xs"
                    >
                      <span className="text-sage-400 font-mono">
                        {sig.hex_offset}
                      </span>
                      <span className="text-gray-400 ml-2 text-xs">
                        {sig.description}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Components */}
              <div>
                <p className="text-xs text-gray-500 mb-2 font-medium uppercase tracking-wide">
                  Detected Components
                </p>
                <ComponentBadges summary={latestExtraction.component_summary} />
              </div>
            </div>
          )}

          {latestExtraction.file_tree && (
            <div>
              <p className="text-xs text-gray-500 mb-2 font-medium uppercase tracking-wide">
                Extracted File Tree
              </p>
              <div className="bg-black/20 rounded-lg p-3 border border-white/5">
                <FileTree tree={latestExtraction.file_tree} />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
