import React from "react";
import AnimatedNumber from "./AnimatedNumber.jsx";

const LEVEL_COLOR = {
  Safe: "var(--risk-low)",
  Low: "var(--risk-low)",
  Medium: "var(--risk-medium)",
  High: "var(--risk-high)",
  Critical: "var(--risk-critical)",
};

const LEVEL_BG = {
  Safe: "var(--risk-low-bg)",
  Low: "var(--risk-low-bg)",
  Medium: "var(--risk-medium-bg)",
  High: "var(--risk-high-bg)",
  Critical: "var(--risk-critical-bg)",
};

// Renders a 0-100 risk score as a radial arc gauge. Signature element of
// the risk results view.
export default function RiskGauge({ score = 0, level = "Low" }) {
  const clamped = Math.max(0, Math.min(100, score ?? 0));
  const fraction = clamped / 100;
  const radius = 70;
  const circumference = Math.PI * radius;
  const offset = circumference * (1 - fraction);
  const color = LEVEL_COLOR[level] || LEVEL_COLOR.Low;
  const bg = LEVEL_BG[level] || LEVEL_BG.Low;

  return (
    <div className="gauge-wrap">
      <svg width="180" height="104" viewBox="0 0 180 104">
        <path d="M 20 94 A 70 70 0 0 1 160 94" fill="none" strokeWidth="10" className="gauge-arc-bg" />
        <path
          d="M 20 94 A 70 70 0 0 1 160 94"
          fill="none"
          stroke={color}
          strokeWidth="10"
          className="gauge-arc-fill"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="gauge-value" style={{ color, marginTop: -36 }}>
        <AnimatedNumber value={clamped} decimals={1} />
      </div>
      <div className="gauge-label" style={{ color: "var(--text-muted)" }}>
        Risk Score / 100
      </div>
      <span className="risk-badge" style={{ color, background: bg }}>
        {level}
      </span>
    </div>
  );
}
