"use client";

import { SignUpButton } from "@clerk/nextjs";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { UploadCloudIcon, ShieldCheckIcon } from "lucide-react";

function Hero() {
  return (
    <section
      id="hero"
      className="relative flex items-center overflow-hidden pt-32 pb-16 md:pt-40"
    >
      <div className="absolute inset-0 bg-white dark:bg-black">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(139,92,246,0.15)_1px,transparent_1px),linear-gradient(to_bottom,rgba(139,92,246,0.15)_1px,transparent_1px)] dark:bg-[linear-gradient(to_right,rgba(139,92,246,0.1)_1px,transparent_1px),linear-gradient(to_bottom,rgba(139,92,246,0.1)_1px,transparent_1px)] bg-[size:48px_48px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_110%)]" />
      </div>

      <motion.div
        animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.5, 0.3] }}
        transition={{ duration: 8, repeat: Infinity }}
        className="absolute top-20 left-1/4 w-72 h-72 bg-gradient-to-r from-violet-400/20 to-fuchsia-400/10 rounded-full blur-3xl"
      />
      <motion.div
        animate={{ scale: [1, 1.3, 1], opacity: [0.2, 0.4, 0.2] }}
        transition={{ duration: 10, repeat: Infinity }}
        className="absolute bottom-20 right-1/4 w-96 h-96 bg-gradient-to-r from-fuchsia-400/15 to-violet-400/5 rounded-full blur-3xl"
      />

      <div className="relative z-10 w-full px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div className="space-y-10">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
                className="space-y-6"
              >
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.2 }}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-100 to-fuchsia-100 dark:from-violet-900/40 dark:to-fuchsia-900/40 rounded-full border border-violet-200 dark:border-violet-500/30 backdrop-blur-sm shadow-[0_0_20px_rgba(139,92,246,0.2)]"
                >
                  <motion.div
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ duration: 2, repeat: Infinity }}
                    className="w-2 h-2 bg-violet-500 rounded-full shadow-[0_0_10px_rgba(139,92,246,0.8)]"
                  />
                  <span className="text-sm font-bold text-violet-700 dark:text-violet-300">
                    AI-Powered Firmware Security
                  </span>
                </motion.div>

                <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight">
                  <span className="text-gray-900 dark:text-white">
                    Know what&apos;s
                  </span>
                  <br />
                  <span className="bg-gradient-to-r from-violet-600 via-fuchsia-600 to-violet-700 dark:from-violet-400 dark:via-fuchsia-400 dark:to-violet-300 bg-clip-text text-transparent drop-shadow-[0_0_30px_rgba(139,92,246,0.4)]">
                    inside your
                  </span>
                  <br />
                  <span className="text-gray-900 dark:text-white">
                    firmware&apos;s crypto
                  </span>
                </h1>

                <p className="text-lg text-gray-600 dark:text-gray-300 leading-relaxed max-w-xl font-medium">
                  Upload a firmware image and CryptoSage extracts it, identifies
                  every cryptographic algorithm inside, scores the security
                  risk, and explains the findings with evidence-backed
                  citations.
                </p>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="flex flex-col sm:flex-row gap-4"
              >
                <SignUpButton mode="modal">
                  <motion.div
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <Button size="lg">
                      <UploadCloudIcon className="mr-2 size-5" />
                      Upload Firmware
                    </Button>
                  </motion.div>
                </SignUpButton>

                <SignUpButton mode="modal">
                  <motion.div
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <Button size="lg" variant="outline">
                      <ShieldCheckIcon className="mr-2 size-5" />
                      See a Risk Report
                    </Button>
                  </motion.div>
                </SignUpButton>
              </motion.div>
            </div>

            <motion.div
              initial={{ opacity: 0, x: 50 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.8, delay: 0.3 }}
              className="relative lg:pl-8 hidden lg:flex items-center justify-center"
            >
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 24, repeat: Infinity, ease: "linear" }}
                className="absolute -top-4 -left-4 w-24 h-24 bg-gradient-to-br from-violet-400/20 to-fuchsia-400/10 rounded-2xl blur-xl"
              />
              <motion.div
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 4, repeat: Infinity }}
                className="absolute -bottom-6 -right-6 w-32 h-32 bg-gradient-to-br from-fuchsia-400/15 to-violet-400/5 rounded-full blur-2xl"
              />
              <div className="relative w-full max-w-sm aspect-square rounded-3xl border border-violet-500/30 bg-white/70 dark:bg-black/60 backdrop-blur-xl shadow-[0_0_60px_rgba(139,92,246,0.25)] flex items-center justify-center overflow-hidden">
                <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(139,92,246,0.08)_1px,transparent_1px),linear-gradient(to_bottom,rgba(139,92,246,0.08)_1px,transparent_1px)] bg-[size:24px_24px]" />
                <motion.div
                  animate={{ y: ["-100%", "200%"] }}
                  transition={{
                    duration: 2.5,
                    repeat: Infinity,
                    ease: "linear",
                  }}
                  className="absolute left-0 right-0 h-1/3 bg-gradient-to-b from-transparent via-violet-400/30 to-transparent"
                />
                <ShieldCheckIcon
                  className="h-24 w-24 text-violet-500/70 dark:text-violet-400/70 relative z-10"
                  strokeWidth={1}
                />
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default Hero;
