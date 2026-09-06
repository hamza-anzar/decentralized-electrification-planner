import { useRef, useState } from "react";
import { Download, Upload, FileSpreadsheet } from "lucide-react";
import Button from "./Button";
import Alert from "./Alert";
import { api } from "../api/client";

// Reusable "download a template, fill it in, upload it back" control — used by Demand Profile
// (hourly upload), Solar Design (irradiance upload), and Financials (BOQ upload).
export default function FileUpload({ downloadPath, downloadFilename, uploadPath, onUploaded, uploadLabel = "Upload" }) {
  const [file, setFile] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [errors, setErrors] = useState([]);
  const inputRef = useRef(null);

  async function handleDownload() {
    setDownloading(true);
    try {
      await api.download(downloadPath, downloadFilename);
    } catch (e) {
      setErrors([e.message || String(e)]);
    } finally {
      setDownloading(false);
    }
  }

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setErrors([]);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const result = await api.postForm(uploadPath, formData);
      if (result.errors?.length) {
        setErrors(result.errors);
      } else {
        setFile(null);
        if (inputRef.current) inputRef.current.value = "";
        onUploaded?.(result);
      }
    } catch (e) {
      setErrors([e.detail?.errors?.join(" ") || e.message || String(e)]);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="secondary" icon={Download} onClick={handleDownload} loading={downloading}>
        Download Template
      </Button>
      <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-ink-200 bg-ink-50/50 px-3 py-2 text-sm text-ink-500 transition hover:border-brand-300 hover:text-ink-700">
        <FileSpreadsheet size={16} />
        {file ? file.name : "Choose file…"}
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx"
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </label>
      <Button variant="primary" icon={Upload} onClick={handleUpload} loading={uploading} disabled={!file}>
        {uploadLabel}
      </Button>
      {errors.length > 0 && (
        <Alert type="error" className="w-full" onDismiss={() => setErrors([])}>
          <ul className="list-disc space-y-0.5 pl-4">
            {errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </Alert>
      )}
    </div>
  );
}
