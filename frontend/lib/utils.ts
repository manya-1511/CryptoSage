import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Extracts a human-readable error message from an Axios/fetch-style
 * error thrown by lib/api.ts calls against the CryptoSage backend.
 * The FastAPI backend returns either `{ detail: string }` or
 * `{ detail: { message: string, failures: [...] } }`.
 */
export function getErrorMessage(error: unknown): string {
  if (error && typeof error === "object" && "response" in error) {
    const response = (error as { response?: { data?: unknown } }).response;
    const data = response?.data as
      | { detail?: string | { message?: string } }
      | undefined;

    if (typeof data?.detail === "string") return data.detail;
    if (data?.detail && typeof data.detail === "object" && data.detail.message) {
      return data.detail.message;
    }
  }

  if (error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}

export function formatDate(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function riskColorClasses(level: string): string {
  const map: Record<string, string> = {
    Safe: "text-violet-600 dark:text-violet-300 border-violet-500/30 bg-violet-50 dark:bg-violet-900/20",
    Low: "text-purple-600 dark:text-purple-300 border-purple-500/30 bg-purple-50 dark:bg-purple-900/20",
    Medium: "text-amber-600 dark:text-amber-300 border-amber-500/30 bg-amber-50 dark:bg-amber-900/20",
    High: "text-orange-600 dark:text-orange-300 border-orange-500/30 bg-orange-50 dark:bg-orange-900/20",
    Critical: "text-red-600 dark:text-red-300 border-red-500/30 bg-red-50 dark:bg-red-900/20",
  };
  return map[level] || map.Medium;
}
