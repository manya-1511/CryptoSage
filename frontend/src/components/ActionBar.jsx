import React from "react";

export default function ActionBar({ onPredict, onRisk, onExplain, loading }) {
  return (
    <div className="panel section-gap">
      <div className="panel-title">Run Analysis</div>
      <div className="warn-banner" style={{ marginBottom: 16 }}>
        These endpoints expect the Firmware Analysis Engine (Phase 4 — Binwalk
        extraction, ELF parsing, feature extraction) to have already run for
        this firmware, producing <code className="mono">feature_vector.json</code>{" "}
        file(s) server-side. That step isn't exposed over the API yet, so if a
        run below 404s with "no analysis results found," that's what's
        missing — not a frontend bug.
      </div>
      <div className="action-row">
        <button className="btn btn-primary" onClick={onPredict} disabled={!!loading} type="button">
          {loading === "predict" ? "Predicting…" : "Run Prediction"}
        </button>
        <button className="btn btn-primary" onClick={onRisk} disabled={!!loading} type="button">
          {loading === "risk" ? "Assessing…" : "Assess Risk"}
        </button>
        <button className="btn btn-primary" onClick={onExplain} disabled={!!loading} type="button">
          {loading === "explain" ? "Explaining… (can take several seconds)" : "Generate Explanation"}
        </button>
      </div>
      <div className="action-hint">
        Risk assessment re-runs prediction internally; explanation re-runs
        both. You don't need to run them in order — each is a complete,
        independent call.
      </div>
    </div>
  );
}
