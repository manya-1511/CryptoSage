"use client";

import { motion } from "framer-motion";
import { UploadCloudIcon, BrainCircuitIcon, BookOpenIcon } from "lucide-react";

const steps = [
  {
    n: 1,
    icon: UploadCloudIcon,
    title: "Upload & Extract",
    desc: "Drop in a .bin, .img, or .elf image. CryptoSage runs Binwalk extraction and disassembles every discovered binary with LIEF and Capstone.",
    pills: ["Binwalk", "SHA-256 Dedup"],
  },
  {
    n: 2,
    icon: BrainCircuitIcon,
    title: "Detect & Score",
    desc: "A hierarchical ML model classifies the crypto family and exact algorithm, then a weighted risk engine scores each binary from Safe to Critical.",
    pills: ["95%+ Accuracy", "SHAP Explainable"],
  },
  {
    n: 3,
    icon: BookOpenIcon,
    title: "Understand Why",
    desc: "A RAG pipeline generates a plain-language summary with cited standards and remediation recommendations for every finding.",
    pills: ["Cited Sources", "Remediation Steps"],
  },
];

function HowItWorks() {
  return (
    <section className="relative py-20 px-6 overflow-hidden bg-white dark:bg-black" id="how-it-works">
      <div className="absolute inset-0">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(139,92,246,0.15)_1px,transparent_1px),linear-gradient(to_bottom,rgba(139,92,246,0.15)_1px,transparent_1px)] dark:bg-[linear-gradient(to_right,rgba(139,92,246,0.1)_1px,transparent_1px),linear-gradient(to_bottom,rgba(139,92,246,0.1)_1px,transparent_1px)] bg-[size:48px_48px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_110%)]" />
      </div>

      <motion.div
        animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.5, 0.3] }}
        transition={{ duration: 8, repeat: Infinity }}
        className="absolute top-20 left-1/4 w-96 h-96 bg-gradient-to-r from-violet-400/20 to-fuchsia-400/10 rounded-full blur-3xl"
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
            <span className="text-sm font-bold text-violet-700 dark:text-violet-300">Simple Process</span>
          </motion.div>

          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6 tracking-tight"
          >
            <span className="text-gray-900 dark:text-white">Three steps to</span>
            <br />
            <span className="bg-gradient-to-r from-violet-600 via-fuchsia-600 to-violet-700 dark:from-violet-400 dark:via-fuchsia-400 dark:to-violet-300 bg-clip-text text-transparent">
              secure firmware
            </span>
          </motion.h2>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto leading-relaxed"
          >
            CryptoSage turns raw firmware binaries into detected algorithms,
            risk scores, and evidence-backed explanations you can act on.
          </motion.p>
        </div>

        <div className="grid lg:grid-cols-3 gap-8">
          {steps.map((step, i) => (
            <motion.div
              key={step.n}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.15 }}
              whileHover={{ y: -8 }}
              className="relative bg-white/80 dark:bg-black/80 backdrop-blur-xl rounded-3xl p-8 border border-violet-500/30 hover:border-violet-500/50 transition-all duration-300 shadow-[0_0_40px_rgba(139,92,246,0.15)] hover:shadow-[0_0_60px_rgba(139,92,246,0.25)]"
            >
              <div className="absolute -top-4 left-8 w-10 h-10 bg-gradient-to-r from-violet-600 to-fuchsia-600 dark:from-violet-400 dark:to-fuchsia-400 rounded-full flex items-center justify-center text-white dark:text-violet-950 text-sm font-bold shadow-[0_0_20px_rgba(139,92,246,0.5)]">
                {step.n}
              </div>

              <div className="w-20 h-20 bg-gradient-to-br from-violet-100 to-fuchsia-100 dark:from-violet-900/40 dark:to-fuchsia-900/40 rounded-2xl flex items-center justify-center mx-auto mb-6">
                <step.icon className="h-9 w-9 text-violet-600 dark:text-violet-300" strokeWidth={1.5} />
              </div>

              <h3 className="text-2xl font-bold mb-4 text-center text-gray-900 dark:text-white">
                {step.title}
              </h3>
              <p className="text-gray-600 dark:text-gray-300 text-center leading-relaxed mb-6">
                {step.desc}
              </p>

              <div className="flex flex-wrap gap-2 justify-center">
                {step.pills.map((pill) => (
                  <span
                    key={pill}
                    className="px-3 py-1 bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300 text-xs font-bold rounded-full border border-violet-200 dark:border-violet-500/30"
                  >
                    {pill}
                  </span>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default HowItWorks;
