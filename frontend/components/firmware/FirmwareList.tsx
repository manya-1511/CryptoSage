"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  FileIcon,
  Loader2Icon,
  AlertCircleIcon,
  UploadCloudIcon,
  ChevronRightIcon,
} from "lucide-react";
import { listFirmware, type Firmware } from "@/lib/api";
import { getErrorMessage, formatDate } from "@/lib/utils";

export default function FirmwareList() {
  const [firmware, setFirmware] = useState<Firmware[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await listFirmware();
        if (!cancelled) setFirmware(data);
      } catch (err) {
        if (!cancelled) setError(getErrorMessage(err));
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="flex items-center justify-between flex-wrap gap-4"
      >
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
            Firmware History
          </h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Every firmware you&apos;ve uploaded, most recent first
          </p>
        </div>
        <Link href="/analyze">
          <Button>
            <UploadCloudIcon className="mr-2 h-4 w-4" />
            Upload New Firmware
          </Button>
        </Link>
      </motion.div>

      {error && (
        <Card className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-500/30 flex items-center gap-2">
          <AlertCircleIcon className="h-4 w-4 text-red-600 dark:text-red-400" />
          <span className="text-sm text-red-600 dark:text-red-300">{error}</span>
        </Card>
      )}

      {!firmware && !error && (
        <Card className="p-10 bg-white/90 dark:bg-black/80 border border-violet-500/30 flex flex-col items-center gap-3">
          <Loader2Icon className="h-8 w-8 text-violet-600 dark:text-violet-300 animate-spin" />
          <p className="text-sm text-gray-600 dark:text-gray-400">Loading firmware history…</p>
        </Card>
      )}

      {firmware && firmware.length === 0 && (
        <Card className="p-10 bg-white/90 dark:bg-black/80 border border-violet-500/30 flex flex-col items-center gap-3 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-violet-100 to-fuchsia-100 dark:from-violet-900/40 dark:to-fuchsia-900/40">
            <FileIcon className="h-6 w-6 text-violet-600 dark:text-violet-300" />
          </div>
          <p className="text-sm font-medium text-gray-800 dark:text-gray-200">No firmware uploaded yet</p>
          <p className="text-sm text-gray-500 dark:text-gray-500 max-w-sm">
            Upload your first firmware image to get algorithm detection, a
            risk score, and a cited security explanation.
          </p>
          <Link href="/analyze" className="mt-2">
            <Button>
              <UploadCloudIcon className="mr-2 h-4 w-4" />
              Upload Firmware
            </Button>
          </Link>
        </Card>
      )}

      {firmware && firmware.length > 0 && (
        <div className="space-y-3">
          {firmware.map((fw, index) => (
            <motion.div
              key={fw.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
            >
              <Link href={`/firmware/${fw.id}`}>
                <Card className="p-4 sm:p-5 bg-white/90 dark:bg-black/80 border border-violet-500/30 hover:border-violet-500/50 transition-all duration-300 hover:shadow-[0_0_30px_rgba(139,92,246,0.2)] cursor-pointer">
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-fuchsia-100 dark:from-violet-900/40 dark:to-fuchsia-900/40">
                        <FileIcon className="h-5 w-5 text-violet-600 dark:text-violet-300" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-gray-900 dark:text-white truncate">
                          {fw.filename}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-500 truncate">
                          {formatDate(fw.upload_time)} · {fw.file_hash.slice(0, 12)}…
                        </p>
                      </div>
                    </div>
                    <ChevronRightIcon className="h-5 w-5 text-gray-400 shrink-0" />
                  </div>
                </Card>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
