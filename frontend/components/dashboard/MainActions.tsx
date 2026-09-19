"use client";

import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import {
  UploadCloudIcon,
  HistoryIcon,
  MessageSquareIcon,
  CheckCircle2,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

const actions = [
  {
    href: "/analyze",
    icon: UploadCloudIcon,
    title: "Run Firmware Analysis",
    desc: "Upload firmware to detect cryptographic algorithms and assess risk",
    features: [
      "Algorithm detection across 24 crypto algorithms",
      "Weighted risk scoring with clear risk factors",
      "Evidence-backed RAG explanation with citations",
    ],
    cta: "Upload Firmware",
  },
  {
    href: "/firmware",
    icon: HistoryIcon,
    title: "Firmware History",
    desc: "Review every firmware you've uploaded and its past results",
    features: [
      "Full upload history with SHA-256 dedup",
      "Past predictions, risk scores & reports",
      "Re-run analysis on any prior firmware",
    ],
    cta: "View History",
  },
  {
    href: "/assistant",
    icon: MessageSquareIcon,
    title: "Report Assistant",
    desc: "Ask questions about any completed analysis, grounded in its own report",
    features: [
      "Pick any past firmware report",
      "Ask about its algorithm, risk, or recommendations",
      "Answers stay grounded in that report only",
    ],
    cta: "Open Assistant",
  },
];

export default function MainActions() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5 sm:gap-8 mb-6 md:mb-12">
      {actions.map((action, index) => (
        <motion.div
          key={action.href}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: index * 0.15 }}
          whileHover={{ y: -8 }}
        >
          <Card className="relative overflow-hidden group transition-all duration-300 border-2 border-violet-500/30 hover:border-violet-500 bg-white/90 dark:bg-black/80 backdrop-blur-xl shadow-[0_0_30px_rgba(139,92,246,0.15)] hover:shadow-[0_0_50px_rgba(139,92,246,0.3)] h-full">
            <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-gradient-to-br from-violet-400/5 via-fuchsia-400/5 to-violet-500/5" />

            <CardContent className="relative p-5 sm:p-6 md:p-8 flex flex-col h-full">
              <div className="flex items-start sm:items-center gap-3 sm:gap-4 mb-5 sm:mb-6">
                <motion.div
                  whileHover={{ scale: 1.1, rotate: 5 }}
                  className="w-12 h-12 sm:w-14 sm:h-14 shrink-0 rounded-2xl flex items-center justify-center bg-gradient-to-br from-violet-100 to-fuchsia-100 dark:from-violet-900/40 dark:to-fuchsia-900/40 shadow-[0_0_20px_rgba(139,92,246,0.3)]"
                >
                  <action.icon className="h-6 w-6 sm:h-7 sm:w-7 text-violet-600 dark:text-violet-300" />
                </motion.div>

                <div className="min-w-0">
                  <h3 className="text-lg sm:text-xl font-bold text-gray-900 dark:text-white leading-tight">
                    {action.title}
                  </h3>
                  <p className="text-xs sm:text-sm text-gray-600 dark:text-gray-400 mt-0.5">
                    {action.desc}
                  </p>
                </div>
              </div>

              <div className="space-y-2.5 sm:space-y-3 text-sm text-gray-700 dark:text-gray-300 mb-5 sm:mb-6 flex-1">
                {action.features.map((feature) => (
                  <div key={feature} className="flex items-center gap-2.5 sm:gap-3">
                    <CheckCircle2 className="w-4 h-4 sm:w-5 sm:h-5 shrink-0 text-violet-600 dark:text-violet-400" />
                    <span className="text-xs sm:text-sm">{feature}</span>
                  </div>
                ))}
              </div>

              <Link
                href={action.href}
                className={cn(
                  buttonVariants({}),
                  "w-full py-4 sm:py-6 rounded-xl font-extrabold text-sm sm:text-base"
                )}
              >
                <action.icon className="mr-2 h-4 w-4 sm:h-5 sm:w-5" />
                {action.cta}
              </Link>
            </CardContent>
          </Card>
        </motion.div>
      ))}
    </div>
  );
}
