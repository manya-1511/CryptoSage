import React from "react";
import RiskGauge from "./RiskGauge.jsx";

export default function RiskResults({ items, failed }) {
  if ((!items || items.length === 0) && (!failed || failed.length === 0)) return null;

  return (
    <div className="panel section-gap">
      <div className="panel-title">Risk Assessment</div>

      <div className="risk-result-list">
        {items.map((r, i) => (
          <div className="risk-result-card" key={r.binary_name || i}>
            <div className="risk-result-top">
              <div>
                <div className="binary-result-name mono">{r.binary_name}</div>
                <div className="predicted-algo-sm" style={{ marginTop: 6 }}>
                  {r.algorithm} <span className="context-item-label" style={{ display: "inline" }}>· {r.algorithm_family}</span>
                </div>
              </div>
              <RiskGauge score={r.risk_score} level={r.risk_level} />
            </div>

            {r.risk_factors && r.risk_factors.length > 0 && (
              <div className="factor-chips">
                {r.risk_factors.map((f) => (
                  <span className="factor-chip" key={f}>
                    {f}
                  </span>
                ))}
              </div>
            )}

            {r.recommendations && r.recommendations.length > 0 && (
              <div className="rec-list" style={{ marginTop: 14 }}>
                {r.recommendations.map((rec, j) => (
                  <div className="rec-card" key={j}>
                    <div className="rec-score">{j + 1}</div>
                    <div className="rec-body">{rec}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {failed && failed.length > 0 && (
        <div className="error-banner section-gap">
          {failed.length} binary(ies) failed risk assessment:{" "}
          {failed.map((f) => f.binary_name || f.error).join(", ")}
        </div>
      )}
    </div>
  );
}
