"use client";

import { useUser } from "@clerk/nextjs";
import { motion } from "framer-motion";
import { LogoMark } from "@/components/logo";

export default function WelcomeSection() {
  const { user } = useUser();
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "morning" : hour < 18 ? "afternoon" : "evening";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative z-10 flex items-center justify-between rounded-2xl sm:rounded-3xl p-5 sm:p-6 md:p-8 mb-6 md:mb-12 overflow-hidden border border-violet-500/30 bg-white/90 dark:bg-black/80 backdrop-blur-xl shadow-[0_0_40px_rgba(139,92,246,0.2)]"
    >
      <div className="absolute inset-0 bg-gradient-to-br from-violet-400/5 via-fuchsia-400/5 to-violet-500/5 dark:from-violet-400/10 dark:via-fuchsia-400/10 dark:to-violet-500/10" />

      <div className="relative space-y-3 sm:space-y-4 flex-1 min-w-0">
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="inline-flex items-center gap-2 px-3 py-1.5 sm:px-4 sm:py-2 rounded-full bg-gradient-to-r from-violet-100 to-fuchsia-100 dark:from-violet-900/40 dark:to-fuchsia-900/40 border border-violet-200 dark:border-violet-500/30 backdrop-blur-sm shadow-[0_0_15px_rgba(139,92,246,0.3)]"
        >
          <motion.div
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="size-2 bg-violet-500 rounded-full shadow-[0_0_10px_rgba(139,92,246,0.8)] shrink-0"
          />
          <span className="text-xs sm:text-sm font-bold text-violet-700 dark:text-violet-300 leading-tight">
            AI-Powered Firmware Security Analysis
          </span>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold mb-1 sm:mb-2 text-gray-900 dark:text-white">
            Good {greeting}, {user?.firstName ?? "there"}!
          </h1>
          <p className="text-sm sm:text-base text-gray-600 dark:text-gray-300 leading-relaxed">
            Upload firmware to detect cryptographic algorithms, assess
            security risk, and get evidence-backed explanations powered by AI.
          </p>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0, scale: 0.8, rotate: -180 }}
        animate={{ opacity: 1, scale: 1, rotate: 0 }}
        transition={{ delay: 0.4, type: "spring", stiffness: 200 }}
        whileHover={{ scale: 1.1, rotate: 360 }}
        className="hidden lg:flex ml-6 shrink-0 items-center justify-center size-32 rounded-full bg-gradient-to-br from-violet-100 to-fuchsia-100 dark:from-violet-900/40 dark:to-fuchsia-900/40 shadow-[0_0_30px_rgba(139,92,246,0.4)] relative cursor-pointer"
      >
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          className="absolute inset-0 rounded-full bg-gradient-to-r from-violet-400/20 to-fuchsia-400/20 blur-xl"
        />
        <LogoMark className="w-16 h-16 relative z-10" />
      </motion.div>
    </motion.div>
  );
}
