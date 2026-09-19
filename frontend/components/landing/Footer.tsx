"use client";

import { motion } from "framer-motion";
import { LogoMark, LogoWordmark } from "@/components/logo";

function Footer() {
  return (
    <footer className="relative px-6 py-10 border-t border-violet-500/20 bg-white dark:bg-black overflow-hidden">
      <div className="absolute inset-0">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(139,92,246,0.05)_1px,transparent_1px),linear-gradient(to_bottom,rgba(139,92,246,0.05)_1px,transparent_1px)] dark:bg-[linear-gradient(to_right,rgba(139,92,246,0.03)_1px,transparent_1px),linear-gradient(to_bottom,rgba(139,92,246,0.03)_1px,transparent_1px)] bg-[size:48px_48px]" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto flex flex-col items-center gap-4 text-center">
        <div className="flex items-center gap-2">
          <LogoMark className="w-6 h-6" />
          <LogoWordmark className="text-base" />
        </div>
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="text-sm text-gray-600 dark:text-gray-400"
        >
          &copy; {new Date().getFullYear()} CryptoSage. Built to help engineers
          detect and understand cryptographic risk in firmware.
        </motion.p>
      </div>
    </footer>
  );
}

export default Footer;
