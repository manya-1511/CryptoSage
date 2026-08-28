import React, { useCallback, useEffect, useState } from "react";
import {
  checkHealth,
  uploadFirmware,
  listFirmware,
  getFirmware,
  predictFirmware,
  assessRisk,
  explainFirmware,
  normalizePredictions,
  normalizeRiskAssessments,
  normalizeExplanations,
  isDuplicateUpload,
  ApiError,
} from "./api";
import { useToast } from "./components/Toast.jsx";

import FirmwareSidebar from "./components/FirmwareSidebar.jsx";
import FirmwareHeader from "./components/FirmwareHeader.jsx";
import ActionBar from "./components/ActionBar.jsx";
import PredictionResults from "./components/PredictionResults.jsx";
import RiskResults from "./components/RiskResults.jsx";
import ExplanationResults from "./components/ExplanationResults.jsx";

export default function App() {
  const toast = useToast();
  const [backendOnline, setBackendOnline] = useState(null);

  const [firmwareList, setFirmwareList] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedFirmware, setSelectedFirmware] = useState(null);

  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const [actionLoading, setActionLoading] = useState(null); // "predict" | "risk" | "explain" | null
  const [predictionResult, setPredictionResult] = useState(null);
  const [riskResult, setRiskResult] = useState(null);
  const [explanationResult, setExplanationResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    checkHealth()
      .then(() => setBackendOnline(true))
      .catch(() => setBackendOnline(false));
    refreshList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refreshList = useCallback(async () => {
    setLoadingList(true);
    try {
      const list = await listFirmware();
      setFirmwareList(list);
    } catch (e) {
      toast.push(describeError(e, "Could not load firmware list"), "error");
    } finally {
      setLoadingList(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectFirmware = useCallback(
    async (id) => {
      setSelectedId(id);
      setPredictionResult(null);
      setRiskResult(null);
      setExplanationResult(null);
      setError(null);
      try {
        const fw = await getFirmware(id);
        setSelectedFirmware(fw);
      } catch (e) {
        toast.push(describeError(e, "Could not load firmware details"), "error");
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const handleFileSelected = async (file) => {
    setUploading(true);
    setUploadProgress(0);
    try {
      const info = await uploadFirmware(file, setUploadProgress);
      if (isDuplicateUpload(info)) {
        toast.push(`Already uploaded as firmware #${info.firmware_id}`, "info");
      } else {
        toast.push(`Uploaded — firmware #${info.firmware_id}`, "success");
      }
      await refreshList();
      selectFirmware(info.firmware_id);
    } catch (e) {
      toast.push(describeError(e, "Upload failed"), "error");
    } finally {
      setUploading(false);
    }
  };

  const runPredict = async () => {
    if (!selectedId) return;
    setActionLoading("predict");
    setError(null);
    try {
      const resp = await predictFirmware(selectedId);
      setPredictionResult(normalizePredictions(resp));
      toast.push("Prediction complete", "success");
    } catch (e) {
      setError(describeError(e, "Prediction failed"));
    } finally {
      setActionLoading(null);
    }
  };

  const runRisk = async () => {
    if (!selectedId) return;
    setActionLoading("risk");
    setError(null);
    try {
      const resp = await assessRisk(selectedId);
      setRiskResult(normalizeRiskAssessments(resp));
      toast.push("Risk assessment complete", "success");
    } catch (e) {
      setError(describeError(e, "Risk assessment failed"));
    } finally {
      setActionLoading(null);
    }
  };

  const runExplain = async () => {
    if (!selectedId) return;
    setActionLoading("explain");
    setError(null);
    try {
      const resp = await explainFirmware(selectedId);
      setExplanationResult(normalizeExplanations(resp));
      toast.push("Explanation generated", "success");
    } catch (e) {
      setError(describeError(e, "Explanation failed"));
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="shell shell-with-sidebar">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">CS</div>
          <div>
            <div className="brand-name">CryptoSage Console</div>
            <div className="brand-sub">Firmware crypto-risk analysis</div>
          </div>
        </div>
        <span className="status-pill">
          <span
            className={`status-dot ${backendOnline === null ? "" : backendOnline ? "online" : "offline"}`}
          />
          {backendOnline === null ? "checking backend…" : backendOnline ? "backend online" : "backend unreachable"}
        </span>
      </header>

      <div className="layout-grid">
        <FirmwareSidebar
          firmwareList={firmwareList}
          loadingList={loadingList}
          selectedId={selectedId}
          onSelect={selectFirmware}
          onFileSelected={handleFileSelected}
          uploading={uploading}
          uploadProgress={uploadProgress}
          onRefresh={refreshList}
        />

        <main className="main-column">
          {error && <div className="error-banner">{error}</div>}

          {!selectedFirmware && (
            <div className="panel">
              <div className="empty-state">
                Upload a firmware file or select one from the list to begin.
              </div>
            </div>
          )}

          {selectedFirmware && (
            <>
              <FirmwareHeader firmware={selectedFirmware} />
              <ActionBar onPredict={runPredict} onRisk={runRisk} onExplain={runExplain} loading={actionLoading} />

              {predictionResult && (
                <PredictionResults items={predictionResult.items} failed={predictionResult.failed} />
              )}
              {riskResult && <RiskResults items={riskResult.items} failed={riskResult.failed} />}
              {explanationResult && (
                <ExplanationResults items={explanationResult.items} failed={explanationResult.failed} />
              )}
            </>
          )}
        </main>
      </div>

      <footer className="footer-note">
        CryptoSage Console · /firmware/upload · /predict · /risk · /explain
      </footer>
    </div>
  );
}

function describeError(e, fallback) {
  if (e instanceof ApiError) {
    return `${fallback}: ${e.detail || e.message}`;
  }
  if (e && e.message) {
    return `${fallback}: ${e.message} (is the backend running and reachable at the configured VITE_API_BASE_URL?)`;
  }
  return fallback;
}
