import axios from "axios";
import type {
  Firmware,
  FirmwareListResponse,
  UploadResponse,
  ExtractionResult,
} from "@/types/firmware";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

export const firmwareApi = {
  upload: async (file: File): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append("file", file);
    const { data } = await api.post<UploadResponse>(
      "/firmware/upload",
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
      },
    );
    return data;
  },

  list: async (page = 1, pageSize = 20): Promise<FirmwareListResponse> => {
    const { data } = await api.get<FirmwareListResponse>("/firmware", {
      params: { page, page_size: pageSize },
    });
    return data;
  },

  getById: async (id: string): Promise<Firmware> => {
    const { data } = await api.get<Firmware>(`/firmware/${id}`);
    return data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/firmware/${id}`);
  },

  extract: async (
    id: string,
  ): Promise<{ extraction_id: string; message: string }> => {
    const { data } = await api.post(`/firmware/${id}/extract`);
    return data;
  },

  listExtractions: async (firmwareId: string): Promise<ExtractionResult[]> => {
    const { data } = await api.get<ExtractionResult[]>(
      `/firmware/${firmwareId}/extractions`,
    );
    return data;
  },

  getExtraction: async (
    firmwareId: string,
    extractionId: string,
  ): Promise<ExtractionResult> => {
    const { data } = await api.get<ExtractionResult>(
      `/firmware/${firmwareId}/extractions/${extractionId}`,
    );
    return data;
  },
};

export default api;
