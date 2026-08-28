import React, { useState } from "react";

export default function CopyButton({ value, label = "copy" }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      // clipboard API unavailable -- fail silently, value is still visible/selectable
    }
  };

  return (
    <button className="copy-btn" onClick={handleCopy} type="button" title="Copy to clipboard">
      {copied ? "copied" : label}
    </button>
  );
}
