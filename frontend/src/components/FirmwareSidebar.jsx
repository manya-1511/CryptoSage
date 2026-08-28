import React from "react";
import UploadPanel from "./UploadPanel.jsx";
import { formatBytes } from "./UploadPanel.jsx";

const STATUS_COLOR = {
  Uploaded: "var(--text-muted)",
  Extracting: "var(--source-cwe)",
  Extracted: "var(--source-cwe)",
  Analyzing: "var(--source-cwe)",
  Completed: "var(--accent)",
  Failed: "var(--risk-high)",
};

export default function FirmwareSidebar({
  firmwareList,
  loadingList,
  selectedId,
  onSelect,
  onFileSelected,
  uploading,
  uploadProgress,
  onRefresh,
}) {
  return (
    <div className="sidebar-panel">
      <div className="panel-title">
        <span>Upload Firmware</span>
      </div>
      <UploadPanel onFileSelected={onFileSelected} uploading={uploading} uploadProgress={uploadProgress} />

      <div className="panel-title" style={{ marginTop: 20 }}>
        <span>Firmware Records</span>
        <button className="btn-ghost-sm" onClick={onRefresh} type="button" title="Refresh list">
          ⟳
        </button>
      </div>

      <div className="firmware-list">
        {loadingList && <div className="empty-state-sm">loading…</div>}
        {!loadingList && firmwareList.length === 0 && (
          <div className="empty-state-sm">No firmware uploaded yet.</div>
        )}
        {firmwareList.map((fw) => (
          <button
            key={fw.id}
            className={`firmware-list-item${fw.id === selectedId ? " active" : ""}`}
            onClick={() => onSelect(fw.id)}
            type="button"
          >
            <div className="firmware-list-item-top">
              <span className="firmware-list-item-name">{fw.filename}</span>
              <span className="firmware-status-dot" style={{ background: STATUS_COLOR[fw.status] || "var(--text-muted)" }} />
            </div>
            <div className="firmware-list-item-meta">
              #{fw.id} · {formatBytes(fw.file_size)} · {fw.status}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
