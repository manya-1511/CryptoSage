import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { FirmwareStatus, ExtractionStatus } from "@/types/firmware";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function getStatusColor(
  status: FirmwareStatus | ExtractionStatus,
): string {
  const map: Record<string, string> = {
    pending: "text-yellow-400 bg-yellow-400/10 border-yellow-400/30",
    validating: "text-blue-400 bg-blue-400/10 border-blue-400/30",
    valid: "text-green-400 bg-green-400/10 border-green-400/30",
    invalid: "text-red-400 bg-red-400/10 border-red-400/30",
    extracting: "text-purple-400 bg-purple-400/10 border-purple-400/30",
    extracted: "text-sage-400 bg-sage-400/10 border-sage-400/30",
    failed: "text-red-500 bg-red-500/10 border-red-500/30",
    running: "text-purple-400 bg-purple-400/10 border-purple-400/30",
    completed: "text-sage-400 bg-sage-400/10 border-sage-400/30",
  };
  return map[status] ?? "text-gray-400 bg-gray-400/10 border-gray-400/30";
}

export function getExtensionIcon(ext: string): string {
  const map: Record<string, string> = {
    ".bin": "🔲",
    ".img": "💿",
    ".elf": "⚡",
    ".hex": "🔣",
  };
  return map[ext] ?? "📦";
}
