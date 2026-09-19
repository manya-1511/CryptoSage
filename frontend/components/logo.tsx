"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

/**
 * Inline SVG shield/circuit mark used as CryptoSage's logo throughout
 * the app. Built as a component (rather than a /public image asset)
 * so the frontend has no dependency on image files that don't exist yet.
 */
export function LogoMark({
  className,
  animate = false,
}: {
  className?: string;
  animate?: boolean;
}) {
  const Wrapper = animate ? motion.svg : "svg";
  const animProps = animate
    ? {
        animate: { rotate: 360 },
        transition: { duration: 20, repeat: Infinity, ease: "linear" },
      }
    : {};

  return (
    <Wrapper
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("w-9 h-9", className)}
      {...animProps}
    >
      <defs>
        <linearGradient id="cs-grad" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#a78bfa" />
          <stop offset="100%" stopColor="#e879f9" />
        </linearGradient>
      </defs>
      <path
        d="M24 3 6 10v11c0 11.5 7.7 20.6 18 24 10.3-3.4 18-12.5 18-24V10L24 3Z"
        fill="url(#cs-grad)"
        opacity="0.15"
      />
      <path
        d="M24 3 6 10v11c0 11.5 7.7 20.6 18 24 10.3-3.4 18-12.5 18-24V10L24 3Z"
        stroke="url(#cs-grad)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M17 23.5 22 28.5 32 17.5"
        stroke="url(#cs-grad)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Wrapper>
  );
}

export function LogoWordmark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "font-bold bg-gradient-to-r from-violet-600 via-fuchsia-600 to-violet-700 dark:from-violet-400 dark:via-fuchsia-400 dark:to-violet-300 bg-clip-text text-transparent",
        className
      )}
    >
      CryptoSage
    </span>
  );
}
