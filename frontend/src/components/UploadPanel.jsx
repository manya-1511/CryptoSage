
import React, { useRef, useState } from "react";

export function formatBytes(bytes) {
  if (bytes === undefined || bytes === null || Number.isNaN(bytes)) {
    return "--";
  }

  if (bytes === 0) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  const decimals = value < 10 && unitIndex > 0 ? 1 : 0;

  return `${value.toFixed(decimals)} ${units[unitIndex]}`;
}

export default function UploadPanel({
  onFileSelected,
  uploading = false,
  uploadProgress = 0,
}) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const handleFiles = (files) => {
    if (!files || files.length === 0) {
      return;
    }

    const file = files[0];

    const allowedExtensions = [".bin", ".img", ".elf"];
    const fileName = file.name.toLowerCase();

    const isValidFile = allowedExtensions.some((extension) =>
      fileName.endsWith(extension)
    );

    if (!isValidFile) {
      window.alert("Please select a .bin, .img, or .elf firmware file.");
      return;
    }

    if (onFileSelected) {
      onFileSelected(file);
    }
  };

  const handleBrowse = (event) => {
    event.stopPropagation();
    inputRef.current?.click();
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (!uploading) {
      setDragging(true);
    }
  };

  const handleDragLeave = (event) => {
    event.preventDefault();
    event.stopPropagation();

    setDragging(false);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    event.stopPropagation();

    setDragging(false);

    if (uploading) {
      return;
    }

    handleFiles(event.dataTransfer.files);
  };

  const handleInputChange = (event) => {
    handleFiles(event.target.files);

    // Allows selecting the same file again.
    event.target.value = "";
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();

      if (!uploading) {
        inputRef.current?.click();
      }
    }
  };

  const safeProgress = Math.min(
    100,
    Math.max(0, Number(uploadProgress) || 0)
  );

  return (
    <div
      className={`dropzone dropzone-compact ${
        dragging ? "dragging" : ""
      } ${uploading ? "uploading" : ""}`}
      onClick={() => {
        if (!uploading) {
          inputRef.current?.click();
        }
      }}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={uploading ? -1 : 0}
      aria-disabled={uploading}
      aria-label="Upload firmware"
    >
      <input
        ref={inputRef}
        type="file"
        accept=".bin,.img,.elf"
        onChange={handleInputChange}
        disabled={uploading}
        style={{ display: "none" }}
      />

      <div className="upload-icon" aria-hidden="true">
        {uploading ? "↑" : "＋"}
      </div>

      <div className="upload-content">
        {uploading ? (
          <>
            <div className="upload-status">
              Uploading… {safeProgress}%
            </div>

            <div
              className="progress-track"
              style={{ marginTop: "10px" }}
              aria-label={`Upload progress ${safeProgress}%`}
            >
              <div
                className="progress-fill"
                style={{
                  width: `${safeProgress}%`,
                  transition: "width 0.2s ease",
                }}
              />
            </div>
          </>
        ) : (
          <>
            <div className="upload-prompt">
              {dragging
                ? "Drop firmware here"
                : "Drop firmware or click to browse"}
            </div>

            <div className="file-types">
              .bin · .img · .elf
            </div>
          </>
        )}
      </div>
    </div>
  );
}