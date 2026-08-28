// Thin fetch wrapper around the CryptoSage FastAPI backend.
// Override the backend origin via VITE_API_BASE_URL in a .env file if it's
// not running on the default http://localhost:8000.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function handle(res) {
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail =
        typeof body.detail === "string"
          ? body.detail
          : body.detail?.message
          ? `${body.detail.message}${body.detail.failures ? ` (${body.detail.failures.length} failure(s))` : ""}`
          : JSON.stringify(body.detail || body);
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(`Request failed (${res.status})`, res.status, detail);
  }
  return res.json();
}

export async function checkHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  return handle(res);
}

export async function uploadFirmware(file, onProgress) {
  // XHR (not fetch) so we can report upload progress for large firmware images.
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE_URL}/firmware/upload`);

    xhr.upload.onprogress = (evt) => {
      if (evt.lengthComputable && onProgress) {
        onProgress(Math.round((evt.loaded / evt.total) * 100));
      }
    };

    xhr.onload = () => {
      let body;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        body = null;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body);
      } else {
        reject(new ApiError("Upload failed", xhr.status, body?.detail || xhr.statusText));
      }
    };

    xhr.onerror = () => reject(new ApiError("Network error during upload", 0, "Could not reach backend"));

    xhr.send(form);
  });
}

export async function listFirmware() {
  const res = await fetch(`${BASE_URL}/firmware`);
  return handle(res);
}

export async function getFirmware(firmwareId) {
  const res = await fetch(`${BASE_URL}/firmware/${firmwareId}`);
  return handle(res);
}

export async function predictFirmware(firmwareId) {
  const res = await fetch(`${BASE_URL}/predict/${firmwareId}`, { method: "POST" });
  return handle(res);
}

export async function assessRisk(firmwareId) {
  const res = await fetch(`${BASE_URL}/risk/${firmwareId}`, { method: "POST" });
  return handle(res);
}

export async function explainFirmware(firmwareId) {
  const res = await fetch(`${BASE_URL}/explain/${firmwareId}`, { method: "POST" });
  return handle(res);
}

// ---------------------------------------------------------------------
// Response normalizers -- /predict, /risk, and /explain each return either
// a "Single*" shape (exactly one analyzed executable, no failures) or a
// "Multiple*" shape ({..., predictions/assessments/explanations: [...],
// failed: [...]}). These flatten either into one consistent array so
// components never need to branch on which shape came back.
// ---------------------------------------------------------------------

export function normalizePredictions(resp) {
  if (!resp) return { items: [], failed: [] };
  if (Array.isArray(resp.predictions)) {
    return { items: resp.predictions, failed: resp.failed || [] };
  }
  // Single prediction shape
  const { firmware_id, model, model_version, ...rest } = resp;
  return { items: [rest], failed: [] };
}

export function normalizeRiskAssessments(resp) {
  if (!resp) return { items: [], failed: [] };
  if (Array.isArray(resp.assessments)) {
    return { items: resp.assessments, failed: resp.failed || [] };
  }
  const { firmware_id, ...rest } = resp;
  return { items: [rest], failed: [] };
}

export function normalizeExplanations(resp) {
  if (!resp) return { items: [], failed: [] };
  if (Array.isArray(resp.explanations)) {
    return { items: resp.explanations, failed: resp.failed || [] };
  }
  const { firmware_id, ...rest } = resp;
  return { items: [rest], failed: [] };
}

export function isDuplicateUpload(resp) {
  return !!resp && typeof resp.message === "string" && resp.status === "Already Uploaded";
}

export { ApiError, BASE_URL };
