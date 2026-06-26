export type FirmwareStatus =
  | "pending"
  | "validating"
  | "valid"
  | "invalid"
  | "extracting"
  | "extracted"
  | "failed";

export type ExtractionStatus = "pending" | "running" | "completed" | "failed";

export interface Firmware {
  id: string;
  filename: string;
  original_filename: string;
  file_size: number;
  file_extension: string;
  mime_type?: string;
  sha256_hash?: string;
  md5_hash?: string;
  architecture?: string;
  endianness?: string;
  description?: string;
  vendor?: string;
  version?: string;
  status: FirmwareStatus;
  validation_error?: string;
  created_at: string;
  updated_at: string;
}

export interface BinwalkSignature {
  offset: number;
  hex_offset: string;
  description: string;
}

export interface FileTreeNode {
  name: string;
  path: string;
  type: "file" | "directory";
  size?: number;
  children?: FileTreeNode[];
}

export interface ComponentSummary {
  filesystems: string[];
  compression: string[];
  executables: string[];
  certificates: string[];
  archives: string[];
  kernels: string[];
  bootloaders: string[];
  total_signatures: number;
}

export interface ExtractionResult {
  id: string;
  firmware_id: string;
  extraction_path?: string;
  tool_used: string;
  status: ExtractionStatus;
  error_message?: string;
  scan_results?: BinwalkSignature[];
  file_tree?: FileTreeNode;
  entropy_data?: Array<{ offset: number; entropy: number }>;
  component_summary?: ComponentSummary;
  total_files_extracted: number;
  total_size_extracted: number;
  duration_seconds?: number;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface FirmwareListResponse {
  items: Firmware[];
  total: number;
  page: number;
  page_size: number;
}

export interface UploadResponse {
  firmware: Firmware;
  message: string;
  validation_passed: boolean;
}
