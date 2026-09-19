"use client";

import { motion } from "framer-motion";
import { ScanLineIcon } from "lucide-react";

function AnalysisIntro() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
      className="relative z-10 mb-4 overflow-hidden rounded-3xl border border-violet-500/30 bg-white/80 dark:bg-black/80 backdrop-blur-xl p-8 flex items-center justify-between shadow-[0_0_40px_rgba(139,92,246,0.2)]"
    >
      <div className="absolute inset-0 bg-gradient-to-br from-violet-400/5 via-fuchsia-400/5 to-violet-500/5 pointer-events-none" />

      <div className="relative space-y-4 max-w-xl">
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-100 to-fuchsia-100 dark:from-violet-900/40 dark:to-fuchsia-900/40 rounded-full border border-violet-200 dark:border-violet-500/30"
        >
          <motion.div
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="w-2 h-2 bg-violet-500 rounded-full shadow-[0_0_10px_rgba(139,92,246,0.8)]"
          />
          <span className="text-sm font-bold text-violet-700 dark:text-violet-300">
            Analysis Engine Ready
          </span>
        </motion.div>

        <div>
          <h1 className="mb-2 text-4xl font-bold text-gray-900 dark:text-white">
            Firmware Cryptographic Analysis
          </h1>
          <p className="text-gray-600 dark:text-gray-300">
            Upload a firmware image and CryptoSage extracts it, detects every
            cryptographic algorithm inside, scores the security risk, and
            explains the findings with evidence-backed citations.
          </p>
        </div>
      </div>

      <div className="hidden lg:block relative">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          className="absolute inset-0 bg-gradient-to-br from-violet-400/20 to-fuchsia-400/10 rounded-full blur-2xl"
        />
        <div className="relative flex h-32 w-32 items-center justify-center rounded-full bg-gradient-to-br from-violet-100 to-fuchsia-100 dark:from-violet-900/40 dark:to-fuchsia-900/40 shadow-[0_0_30px_rgba(139,92,246,0.3)]">
          <ScanLineIcon className="h-16 w-16 text-violet-600 dark:text-violet-300" strokeWidth={1.5} />
        </div>
      </div>

      <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-violet-500/20 blur-[120px]" />
    </motion.div>
  );
}

export default AnalysisIntro;
