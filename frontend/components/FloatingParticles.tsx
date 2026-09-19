"use client";

import { motion } from "framer-motion";
import { useMemo } from "react";

export default function FloatingParticles({ count = 18 }: { count?: number }) {
  const particles = useMemo(
    () =>
      Array.from({ length: count }).map((_, i) => ({
        id: i,
        x1: Math.random() * 100,
        y1: Math.random() * 100,
        x2: Math.random() * 100,
        y2: Math.random() * 100,
        duration: Math.random() * 10 + 10,
      })),
    [count]
  );

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none -z-10">
      {particles.map((p) => (
        <motion.div
          key={p.id}
          className="absolute w-1 h-1 bg-violet-400/30 rounded-full shadow-[0_0_8px_rgba(167,139,250,0.6)]"
          animate={{
            x: [`${p.x1}%`, `${p.x2}%`],
            y: [`${p.y1}%`, `${p.y2}%`],
            scale: [1, 1.5, 1],
            opacity: [0.2, 0.5, 0.2],
          }}
          transition={{
            duration: p.duration,
            repeat: Infinity,
            ease: "linear",
          }}
        />
      ))}
    </div>
  );
}
