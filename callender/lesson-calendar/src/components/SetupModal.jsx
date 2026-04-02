import { useEffect, useMemo, useRef, useState } from "react";
import { Copy, Download, Save, Upload, X } from "lucide-react";

export default function SetupModal({
  open,
  values,
  onSave,
  onClose,
  dataSnapshot,
  onImportData,
}) {
  const [clientId, setClientId] = useState(values?.clientId || "");
  const [apiKey, setApiKey] = useState(values?.apiKey || "");
  const [error, setError] = useState("");
  const [importError, setImportError] = useState("");
  const [importSuccess, setImportSuccess] = useState("");
  const fileInputRef = useRef(null);
  const formattedSnapshot = useMemo(() => JSON.stringify(dataSnapshot ?? {}, null, 2), [dataSnapshot]);

  useEffect(() => {
    if (!open) return;
    setClientId(values?.clientId || "");
    setApiKey(values?.apiKey || "");
    setError("");
    setImportError("");
    setImportSuccess("");
  }, [open, values]);

  if (!open) return null;

  const handleSubmit = (event) => {
    event.preventDefault();

    if (!clientId.trim() || !apiKey.trim()) {
      setError("Both fields are required.");
      return;
    }

    onSave({ clientId: clientId.trim(), apiKey: apiKey.trim() });
  };

  const handleExport = () => {
    try {
      const payload = formattedSnapshot || "{}";
      const blob = new Blob([payload], { type: "application/json" });
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `lesson-calendar-data-${stamp}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.setTimeout(() => URL.revokeObjectURL(link.href), 0);
      setImportSuccess("Download started.");
      setImportError("");
    } catch (downloadError) {
      setImportError(downloadError.message || "Failed to start download.");
      setImportSuccess("");
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(formattedSnapshot || "{}");
      setImportSuccess("Copied.");
      setImportError("");
    } catch (copyError) {
      setImportError(copyError.message || "Failed to copy.");
      setImportSuccess("");
    }
  };

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0];
    setImportError("");
    setImportSuccess("");

    if (!file) return;

    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      if (typeof onImportData !== "function") {
        throw new Error("Import is not available.");
      }

      const result = onImportData(parsed);
      if (Array.isArray(result) && result.length) {
        setImportSuccess(`Imported ${result.join(", ")}.`);
      } else {
        setImportSuccess("Import completed.");
      }
    } catch (importErr) {
      setImportError(importErr.message || "Failed to import.");
    } finally {
      event.target.value = "";
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/80 px-4 py-6 backdrop-blur sm:items-center">
      <div className="app-modal overflow-y-auto">
        <div className="flex items-start justify-between gap-4">
          <h2 className="app-section-title">Setup</h2>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="app-button app-button-square"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        <div className="mt-6 grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="app-label" htmlFor="clientId">
                OAuth Client ID
              </label>
              <input
                id="clientId"
                type="text"
                value={clientId}
                onChange={(event) => setClientId(event.target.value)}
                className="app-field"
              />
            </div>

            <div className="space-y-2">
              <label className="app-label" htmlFor="apiKey">
                API Key
              </label>
              <input
                id="apiKey"
                type="text"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                className="app-field"
              />
            </div>

            {error && <div className="app-alert app-alert-error">{error}</div>}

            <button
              type="submit"
              className="app-button app-button-primary w-full"
            >
              <Save className="h-4 w-4" />
              Save credentials
            </button>
          </form>

          <section className="space-y-4">
            <textarea
              readOnly
              value={formattedSnapshot}
              className="app-code"
            />

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleExport}
                className="app-button"
              >
                <Download className="h-4 w-4" />
                Download
              </button>

              <button
                type="button"
                onClick={handleCopy}
                className="app-button"
              >
                <Copy className="h-4 w-4" />
                Copy
              </button>

              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="app-button app-button-primary"
              >
                <Upload className="h-4 w-4" />
                Import
              </button>

              <input
                ref={fileInputRef}
                type="file"
                accept="application/json,.json"
                onChange={handleFileChange}
                className="hidden"
              />
            </div>

            {importError && <div className="app-alert app-alert-error">{importError}</div>}
            {importSuccess && <div className="app-alert app-alert-success">{importSuccess}</div>}
          </section>
        </div>
      </div>
    </div>
  );
}
