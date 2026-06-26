"use client";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { firmwareApi } from "@/lib/api";
import { formatBytes, getStatusColor } from "@/lib/utils";
import {
  Upload,
  CheckCircle2,
  XCircle,
  FileCode2,
  Loader2,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";
import toast from "react-hot-toast";
import type { UploadResponse } from "@/types/firmware";

const ACCEPTED_TYPES = {
  "application/octet-stream": [".bin", ".img", ".elf"],
  "application/x-elf": [".elf"],
  "text/plain": [".hex"],
  "application/x-hex": [".hex"],
};
const MAX_SIZE = 512 * 1024 * 1024; // 512 MB

export default function UploadPage() {
  const qc = useQueryClient();
  const [result, setResult] = useState<UploadResponse | null>(null);

  const mutation = useMutation({
    mutationFn: firmwareApi.upload,
    onSuccess: (data) => {
      setResult(data);
      qc.invalidateQueries({ queryKey: ["firmware"] });
      toast.success("Firmware uploaded successfully");
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail ?? "Upload failed");
    },
  });

  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted.length > 0) {
        setResult(null);
        mutation.mutate(accepted[0]);
      }
    },
    [mutation],
  );

  const { getRootProps, getInputProps, isDragActive, fileRejections } =
    useDropzone({
      onDrop,
      accept: ACCEPTED_TYPES,
      maxSize: MAX_SIZE,
      multiple: false,
      disabled: mutation.isPending,
    });

  return (
    <div className="max-w-2xl space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">Upload Firmware</h1>
        <p className="text-gray-500 text-sm mt-1">
          Supports .bin, .img, .elf, .hex — up to 512 MB
        </p>
      </div>

      {/* Drop Zone */}
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-xl p-12 text-center cursor-pointer
          transition-all duration-300
          ${
            isDragActive
              ? "border-sage-400 bg-sage-400/5 glow-green"
              : "border-white/10 hover:border-white/20 bg-crypto-800"
          }
          ${mutation.isPending ? "opacity-60 cursor-not-allowed" : ""}
        `}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-4">
          {mutation.isPending ? (
            <Loader2 className="w-12 h-12 text-sage-400 animate-spin" />
          ) : (
            <div className="w-14 h-14 rounded-full bg-sage-600/10 border border-sage-500/20 flex items-center justify-center">
              <Upload className="w-7 h-7 text-sage-400" />
            </div>
          )}
          <div>
            {mutation.isPending ? (
              <p className="text-gray-300 font-medium">
                Uploading & validating…
              </p>
            ) : isDragActive ? (
              <p className="text-sage-400 font-medium">Drop it here!</p>
            ) : (
              <>
                <p className="text-gray-300 font-medium">
                  Drag & drop firmware here, or{" "}
                  <span className="text-sage-400">browse</span>
                </p>
                <p className="text-gray-600 text-sm mt-1">
                  .bin · .img · .elf · .hex
                </p>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Rejection errors */}
      {fileRejections.length > 0 && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-sm text-red-400">
          {fileRejections[0].errors.map((e) => e.message).join(", ")}
        </div>
      )}

      {/* Upload result card */}
      {result && (
        <div
          className={`card border ${
            result.validation_passed
              ? "border-green-500/20 bg-green-500/5"
              : "border-red-500/20 bg-red-500/5"
          } animate-fade-in`}
        >
          <div className="flex items-start gap-3 mb-4">
            {result.validation_passed ? (
              <CheckCircle2 className="w-5 h-5 text-green-400 shrink-0 mt-0.5" />
            ) : (
              <XCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            )}
            <div>
              <p className="font-medium text-white">{result.message}</p>
              <p className="text-xs text-gray-500 mt-0.5 font-mono">
                {result.firmware.original_filename}
              </p>
            </div>
            <span
              className={`badge ml-auto ${getStatusColor(result.firmware.status)}`}
            >
              {result.firmware.status}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm mb-4">
            {[
              ["Size", formatBytes(result.firmware.file_size)],
              ["Extension", result.firmware.file_extension],
              ["MIME", result.firmware.mime_type ?? "—"],
              ["Architecture", result.firmware.architecture ?? "—"],
              [
                "SHA-256",
                (result.firmware.sha256_hash?.slice(0, 16) ?? "—") + "…",
              ],
              ["MD5", (result.firmware.md5_hash?.slice(0, 16) ?? "—") + "…"],
            ].map(([k, v]) => (
              <div key={k} className="bg-white/5 rounded-lg p-3">
                <p className="text-xs text-gray-500 mb-1">{k}</p>
                <p className="font-mono text-xs text-gray-200 truncate">{v}</p>
              </div>
            ))}
          </div>

          {result.validation_passed && (
            <Link
              href={`/firmware/${result.firmware.id}`}
              className="btn-primary w-full justify-center"
            >
              View Firmware & Extract
              <ArrowRight className="w-4 h-4" />
            </Link>
          )}
        </div>
      )}

      {/* Format reference */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-300 mb-3">
          Supported Formats
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {[
            { ext: ".bin", desc: "Raw binary firmware blobs" },
            { ext: ".img", desc: "Disk / flash images" },
            { ext: ".elf", desc: "ELF executables (ARM, x86, MIPS…)" },
            { ext: ".hex", desc: "Intel HEX records" },
          ].map(({ ext, desc }) => (
            <div key={ext} className="flex items-center gap-2 text-sm">
              <FileCode2 className="w-4 h-4 text-sage-400 shrink-0" />
              <span className="font-mono text-sage-400">{ext}</span>
              <span className="text-gray-500 text-xs">{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
