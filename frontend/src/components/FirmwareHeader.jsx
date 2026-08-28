import React from "react";
import CopyButton from "./CopyButton.jsx";
import { formatBytes } from "./UploadPanel.jsx";

export default function FirmwareHeader({ firmware }) {
  if (!firmware) return null;
  return (
    <div className="panel">
      <div className="panel-title">
        <span>Firmware #{firmware.id}</span>
        <span className="firmware-status-badge">{firmware.status}</span>
      </div>
      <div className="context-list">
        <div className="context-item">
          <div className="context-item-label">Filename</div>
          <div className="context-item-value mono">{firmware.filename}</div>
        </div>
        <div className="context-item">
          <div className="context-item-label">Size</div>
          <div className="context-item-value mono">{formatBytes(firmware.file_size)}</div>
        </div>
        <div className="context-item">
          <div className="context-item-label">Architecture</div>
          <div className="context-item-value mono">{firmware.architecture || "unknown"}</div>
        </div>
        <div className="context-item">
          <div className="context-item-label">Uploaded</div>
          <div className="context-item-value mono">
            {firmware.upload_time ? new Date(firmware.upload_time).toLocaleString() : "--"}
          </div>
        </div>
        <div className="context-item" style={{ gridColumn: "1 / -1" }}>
          <div className="context-item-label">SHA-256</div>
          <div className="context-item-value hash-text" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {firmware.file_hash}
            <CopyButton value={firmware.file_hash} />
          </div>
        </div>
      </div>
    </div>
  );
}
