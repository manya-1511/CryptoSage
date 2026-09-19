"use client";

import { motion } from "framer-motion";
import { ShieldAlertIcon, FileSearchIcon, MessageSquareIcon } from "lucide-react";

const findings = [
  {
    icon: FileSearchIcon,
    question: "What algorithm is this binary using?",
    answer:
      "CryptoSage classifies the exact cryptographic algorithm and family with a confidence score, backed by SHAP explainability.",
    tags: ["Algorithm Detection", "24 Algorithms"],
  },
  {
    icon: ShieldAlertIcon,
    question: "How risky is this firmware?",
    answer:
      "Every binary gets a 0-100 risk score, a Safe-to-Critical risk level, and the specific factors driving that score.",
    tags: ["Risk Scoring", "Weighted Factors"],
  },
  {
    icon: MessageSquareIcon,
    question: "Why was this flagged, and what do I fix first?",
    answer:
      "A RAG-generated explanation cites the relevant standards and gives prioritized, actionable security recommendations.",
    tags: ["RAG Explanation", "Recommendations"],
  },
];

function WhatToAsk() {
  return (
    <section className="relative py-20 px-6 overflow-hidden bg-white dark:bg-black" id="what-you-get">
      <div className="absolute inset-0">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(139,92,246,0.15)_1px,transparent_1px),linear-gradient(to_bottom,rgba(139,92,246,0.15)_1px,transparent_1px)] dark:bg-[linear-gradient(to_right,rgba(139,92,246,0.1)_1px,transparent_1px),linear-gradient(to_bottom,rgba(139,92,246,0.1)_1px,transparent_1px)] bg-[size:48px_48px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_110%)]" />
      </div>

      <motion.div
        animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.5, 0.3] }}
        transition={{ duration: 8, repeat: Infinity }}
        className="absolute top-20 right-1/4 w-96 h-96 bg-gradient-to-r from-violet-400/20 to-fuchsia-400/10 rounded-full blur-3xl"
      />

      <div className="relative z-10 max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-100 to-fuchsia-100 dark:from-violet-900/40 dark:to-fuchsia-900/40 rounded-full border border-violet-200 dark:border-violet-500/30 mb-6"
          >
            <span className="w-2 h-2 bg-violet-500 rounded-full" />
            <span className="text-sm font-bold text-violet-700 dark:text-violet-300">What You&apos;ll See</span>
          </motion.div>

          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6 tracking-tight"
          >
            <span className="text-gray-900 dark:text-white">Every finding,</span>
            <br />
            <span className="bg-gradient-to-r from-violet-600 via-fuchsia-600 to-violet-700 dark:from-violet-400 dark:via-fuchsia-400 dark:to-violet-300 bg-clip-text text-transparent">
              fully explained
            </span>
          </motion.h2>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto leading-relaxed"
          >
            From algorithm detection to risk scoring to remediation guidance,
            CryptoSage never gives you a black-box verdict.
          </motion.p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {findings.map((item, i) => (
            <motion.div
              key={item.question}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.15 }}
              whileHover={{ y: -5 }}
              className="bg-white/80 dark:bg-black/80 backdrop-blur-xl rounded-3xl p-6 border border-violet-500/30 hover:border-violet-500/50 transition-all duration-300 shadow-[0_0_40px_rgba(139,92,246,0.15)] hover:shadow-[0_0_60px_rgba(139,92,246,0.25)]"
            >
              <div className="w-12 h-12 bg-gradient-to-br from-violet-100 to-fuchsia-100 dark:from-violet-900/40 dark:to-fuchsia-900/40 rounded-2xl flex items-center justify-center mb-4">
                <item.icon className="h-6 w-6 text-violet-600 dark:text-violet-300" />
              </div>
              <div className="space-y-3">
                <div className="bg-violet-50 dark:bg-violet-900/20 rounded-2xl p-4 border border-violet-200 dark:border-violet-500/30">
                  <p className="font-bold text-violet-700 dark:text-violet-300">
                    &quot;{item.question}&quot;
                  </p>
                </div>
                <div className="bg-gray-50 dark:bg-gray-900/30 rounded-2xl p-4 border border-gray-200 dark:border-gray-700/30">
                  <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
                    {item.answer}
                  </p>
                  <div className="flex gap-2 mt-3 flex-wrap">
                    {item.tags.map((tag) => (
                      <span
                        key={tag}
                        className="px-2 py-1 bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300 text-xs font-bold rounded-full border border-violet-200 dark:border-violet-500/30"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default WhatToAsk;
