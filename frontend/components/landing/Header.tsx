"use client";

import { SignInButton, SignUpButton } from "@clerk/nextjs";
import { motion } from "framer-motion";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ModeToggle } from "@/components/mode-toggle";
import { LogoMark, LogoWordmark } from "@/components/logo";

function Header() {
  return (
    <motion.nav
      initial={{ y: -100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.6 }}
      className="
        fixed top-0 inset-x-0 z-50
        md:top-4 md:left-1/2 md:-translate-x-1/2
        w-full md:w-[calc(100%-2rem)] max-w-7xl
        px-4 md:px-6 py-3
        border-b md:border border-violet-500/30
        bg-white/90 dark:bg-black/90
        backdrop-blur-xl
        md:rounded-3xl
        shadow-[0_8px_32px_rgba(139,92,246,0.12)]
        dark:shadow-[0_8px_32px_rgba(139,92,246,0.25)]
      "
    >
      <div className="absolute inset-0 md:rounded-3xl bg-gradient-to-r from-violet-400/5 via-fuchsia-400/5 to-violet-400/5 dark:from-violet-400/10 dark:via-fuchsia-400/10 dark:to-violet-400/10 pointer-events-none" />

      <div className="relative flex items-center justify-between">
        <Link href="/" className="flex items-center gap-3">
          <motion.div
            whileHover={{ scale: 1.1, rotate: 360 }}
            transition={{ type: "spring", stiffness: 200 }}
            className="relative"
          >
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-violet-400 to-fuchsia-500 opacity-20 blur-md" />
            <LogoMark className="relative z-10" />
          </motion.div>
          <LogoWordmark className="text-lg" />
        </Link>

        <div className="hidden md:flex items-center gap-8">
          <a href="#hero" className="text-sm font-medium text-foreground/80 hover:text-violet-600 dark:hover:text-violet-300 transition-colors">
            Home
          </a>
          <a href="#how-it-works" className="text-sm font-medium text-foreground/80 hover:text-violet-600 dark:hover:text-violet-300 transition-colors">
            How It Works
          </a>
          <a href="#what-you-get" className="text-sm font-medium text-foreground/80 hover:text-violet-600 dark:hover:text-violet-300 transition-colors">
            What You Get
          </a>
        </div>

        <div className="flex items-center gap-2">
          <ModeToggle />

          <SignInButton mode="modal">
            <Button variant="ghost" size="sm">
              Login
            </Button>
          </SignInButton>

          <SignUpButton mode="modal">
            <Button size="sm">Sign Up</Button>
          </SignUpButton>
        </div>
      </div>

      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-violet-400/50 to-transparent md:hidden" />
    </motion.nav>
  );
}

export default Header;
