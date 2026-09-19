import axios, { AxiosError } from "axios";

/* ---------- Config ---------- */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
});

/* ---------- Types (mirrors backend/routes.py + schemas) ---------- */

export interface Firmware {
  id: number;
  filename: string;
  file_hash: string;
  file_size?: number;
  upload_time: string;
}

export interface FirmwareUploadResponse extends Firmware {
  duplicate?: false;
}

export interface FirmwareDuplicateResponse {
  duplicate: true;
  id: number;
  filename: string;
  file_hash: string;
  upload_time: string;
  message?: string;
}

export interface FirmwareAnalysisResponse {
  firmware_id: number;
  binaries_found?: number;
  [key: string]: unknown;
}

export interface BinaryPrediction {
  binary_name: string;
  algorithm_family: string;
  algorithm: string;
  confidence: number;
  prediction_time_ms?: number;
}

export interface SinglePrediction extends BinaryPrediction {
  firmware_id: number;
  model: string;
  model_version: string;
  feature_count_used?: number;
}

export interface MultiplePredictions {
  firmware_id: number;
  model: string;
  model_version: string;
  predictions: BinaryPrediction[];
  failed: { binary_name: string; error: string }[];
}

export interface RiskAssessmentResponse {
  firmware_id: number;
  binary_name: string;
  algorithm_family: string;
  algorithm: string;
  confidence: number;
  risk_score: number;
  risk_level: "Safe" | "Low" | "Medium" | "High" | "Critical";
  risk_factors: string[];
  recommendations: string[];
}

export interface MultipleRiskAssessments {
  firmware_id: number;
  assessments: RiskAssessmentResponse[];
  failed: { binary_name: string; error: string }[];
}

export interface ExplanationResponse {
  firmware_id: number;
  binary_name: string;
  algorithm_family: string;
  algorithm: string;
  confidence: number;
  risk_score: number;
  risk_level: "Safe" | "Low" | "Medium" | "High" | "Critical";
  summary: string;
  sections: Record<string, string> | string[];
  recommendations: string[];
  references: string[];
  generated_by: string;
  generation_time_ms?: number;
}

export interface MultipleExplanations {
  firmware_id: number;
  explanations: ExplanationResponse[];
  failed: { binary_name: string; error: string }[];
}

/* ---------- Helpers ---------- */

export function isDuplicateResponse(
  data: FirmwareUploadResponse | FirmwareDuplicateResponse
): data is FirmwareDuplicateResponse {
  return (data as FirmwareDuplicateResponse).duplicate === true;
}

export function isMultipleExplanations(
  data: ExplanationResponse | MultipleExplanations
): data is MultipleExplanations {
  return Array.isArray((data as MultipleExplanations).explanations);
}

/* ---------- API Calls ---------- */

/** POST /firmware/upload */
export const uploadFirmware = async (
  file: File
): Promise<FirmwareUploadResponse | FirmwareDuplicateResponse> => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post("/firmware/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};

/** GET /firmware */
export const listFirmware = async (): Promise<Firmware[]> => {
  const response = await api.get("/firmware");
  return response.data;
};

/** GET /firmware/{id} */
export const getFirmware = async (firmwareId: number): Promise<Firmware> => {
  const response = await api.get(`/firmware/${firmwareId}`);
  return response.data;
};

/** POST /firmware/{id}/analyze */
export const analyzeFirmware = async (
  firmwareId: number
): Promise<FirmwareAnalysisResponse> => {
  const response = await api.post(`/firmware/${firmwareId}/analyze`);
  return response.data;
};

/** POST /predict/{id} */
export const predictFirmware = async (
  firmwareId: number
): Promise<SinglePrediction | MultiplePredictions> => {
  const response = await api.post(`/predict/${firmwareId}`);
  return response.data;
};

/** POST /risk/{id} */
export const assessFirmwareRisk = async (
  firmwareId: number
): Promise<RiskAssessmentResponse | MultipleRiskAssessments> => {
  const response = await api.post(`/risk/${firmwareId}`);
  return response.data;
};

/** POST /explain/{id} */
export const explainFirmware = async (
  firmwareId: number
): Promise<ExplanationResponse | MultipleExplanations> => {
  const response = await api.post(`/explain/${firmwareId}`);
  return response.data;
};

/** GET /health */
export const checkHealth = async (): Promise<{
  status: string;
  database: string;
}> => {
  const response = await api.get("/health");
  return response.data;
};

export type { AxiosError };
export default api;
