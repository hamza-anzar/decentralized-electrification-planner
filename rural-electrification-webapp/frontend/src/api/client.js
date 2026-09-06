const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, { method = "GET", body } = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = typeof data === "object" ? data.detail : data;
    throw new ApiError(
      typeof detail === "object" ? JSON.stringify(detail) : detail || `Request failed (${res.status})`,
      res.status,
      detail
    );
  }
  return data;
}

async function postForm(path, formData) {
  const res = await fetch(`${BASE_URL}${path}`, { method: "POST", body: formData });
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = typeof data === "object" ? data.detail : data;
    throw new ApiError(
      typeof detail === "object" ? JSON.stringify(detail) : detail || `Request failed (${res.status})`,
      res.status,
      detail
    );
  }
  return data;
}

// Downloads a GET endpoint's response as a file, using the filename the server sent (falls back to `fallbackName`).
async function download(path, fallbackName = "download.xlsx") {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    throw new ApiError(`Download failed (${res.status})`, res.status);
  }
  const disposition = res.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : fallbackName;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", body }),
  postForm: (path, formData) => postForm(path, formData),
  download: (path, fallbackName) => download(path, fallbackName),
};

export { ApiError, BASE_URL };
