import React from "react";
import AnimatedNumber from "./AnimatedNumber.jsx";

export default function PredictionResults({ items, failed, meta }) {
  if ((!items || items.length === 0) && (!failed || failed.length === 0)) return null;

  return (
    <div className="panel section-gap">
      <div className="panel-title">
        <span>Prediction Results</span>
        {meta?.model && (
          <span className="mono" style={{ fontWeight: 400, fontSize: 11 }}>
            {meta.model} · v{meta.model_version}
          </span>
        )}
      </div>

      <div className="binary-result-list">
        {items.map((p, i) => (
          <div className="binary-result-card" key={p.binary_name || i}>
            <div className="binary-result-header">
              <span className="binary-result-name mono">{p.binary_name}</span>
              {p.prediction_time_ms != null && (
                <span className="binary-result-time mono">{p.prediction_time_ms.toFixed(1)}ms</span>
              )}
            </div>
            <div className="binary-result-body">
              <div>
                <div className="context-item-label">Family</div>
                <div className="predicted-family">{p.algorithm_family}</div>
              </div>
              <div>
                <div className="context-item-label">Algorithm</div>
                <div className="predicted-algo-sm">{p.algorithm}</div>
              </div>
              <div>
                <div className="context-item-label">Confidence</div>
                <div className="confidence-row" style={{ marginTop: 4 }}>
                  <div className="confidence-bar">
                    <div className="confidence-fill" style={{ width: `${p.confidence}%` }} />
                  </div>
                  <div className="confidence-value">
                    <AnimatedNumber value={p.confidence} decimals={1} suffix="%" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {failed && failed.length > 0 && (
        <div className="error-banner section-gap">
          {failed.length} binary(ies) failed prediction:{" "}
          {failed.map((f) => f.binary_name || f.error).join(", ")}
        </div>
      )}
    </div>
  );
}
