"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { UploadCloudIcon, ShieldIcon, FileSearchIcon, BrainIcon } from "lucide-react";
import { motion } from "framer-motion";

function Step({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-2 h-2 w-2 rounded-full bg-violet-500 shadow-[0_0_8px_rgba(139,92,246,0.6)]" />
      <span className="text-sm text-gray-700 dark:text-gray-300">{text}</span>
    </div>
  );
}

function Feature({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center rounded-xl bg-violet-50 dark:bg-violet-900/20 p-3 border border-violet-200 dark:border-violet-500/30">
      <div className="mr-3 flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-100 to-fuchsia-100 dark:from-violet-900/40 dark:to-fuchsia-900/40">
        {icon}
      </div>
      <span className="text-sm font-medium text-gray-800 dark:text-gray-200">{text}</span>
    </div>
  );
}

function FeatureCards() {
  return (
    <div className="grid md:grid-cols-2 gap-6 mb-8">
      <motion.div initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}>
        <Card className="group relative overflow-hidden border border-violet-500/30 bg-white/80 dark:bg-black/80 backdrop-blur-xl transition-all duration-300 hover:shadow-[0_0_40px_rgba(139,92,246,0.3)]">
          <div className="absolute inset-0 bg-gradient-to-br from-violet-400/5 via-fuchsia-400/5 to-violet-500/5 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
          <CardHeader className="relative">
            <CardTitle className="flex items-center gap-3 text-gray-900 dark:text-white">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-fuchsia-100 dark:from-violet-900/40 dark:to-fuchsia-900/40 shadow-[0_0_15px_rgba(139,92,246,0.3)]">
                <UploadCloudIcon className="h-5 w-5 text-violet-600 dark:text-violet-300" />
              </div>
              How to Run an Analysis
            </CardTitle>
            <CardDescription>Five steps from raw firmware to a cited security report</CardDescription>
          </CardHeader>
          <CardContent className="relative space-y-4">
            <Step text="Upload a .bin, .img, or .elf firmware image" />
            <Step text="CryptoSage extracts it with Binwalk and discovers ELF binaries" />
            <Step text="Each binary is disassembled and static features are extracted" />
            <Step text="A hierarchical ML model predicts the crypto family and algorithm" />
            <Step text="Review the risk score, risk factors, and cited RAG explanation" />
          </CardContent>
        </Card>
      </motion.div>

      <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}>
        <Card className="group relative overflow-hidden border border-violet-500/30 bg-white/80 dark:bg-black/80 backdrop-blur-xl transition-all duration-300 hover:shadow-[0_0_40px_rgba(139,92,246,0.3)]">
          <div className="absolute inset-0 bg-gradient-to-br from-violet-400/5 via-fuchsia-400/5 to-violet-500/5 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
          <CardHeader className="relative">
            <CardTitle className="flex items-center gap-3 text-gray-900 dark:text-white">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-fuchsia-100 dark:from-violet-900/40 dark:to-fuchsia-900/40 shadow-[0_0_15px_rgba(139,92,246,0.3)]">
                <ShieldIcon className="h-5 w-5 text-violet-600 dark:text-violet-300" />
              </div>
              Analysis Capabilities
            </CardTitle>
            <CardDescription>Built for trustworthy, explainable firmware security review</CardDescription>
          </CardHeader>
          <CardContent className="relative space-y-4">
            <Feature icon={<BrainIcon className="h-4 w-4 text-violet-600 dark:text-violet-300" />} text="95%+ algorithm accuracy across 24 algorithms in 6 crypto families" />
            <Feature icon={<ShieldIcon className="h-4 w-4 text-violet-600 dark:text-violet-300" />} text="Deterministic, weighted risk scoring with explicit risk factors" />
            <Feature icon={<FileSearchIcon className="h-4 w-4 text-violet-600 dark:text-violet-300" />} text="RAG explanations cite the specific standards behind every finding" />
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}

export default FeatureCards;
