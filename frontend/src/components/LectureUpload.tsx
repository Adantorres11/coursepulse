import { useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { API_BASE_URL, getStoredToken } from "../lib/apiClient";

const MAX_FILE_SIZE_MB = 500;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const ALLOWED_EXTENSIONS = [".mp3", ".mp4", ".wav", ".m4a", ".mov", ".webm", ".ogg", ".aac"];

interface UploadLecturePageProps {
  overrideClassId?: string | number;
}

export function UploadLecturePage({ overrideClassId }: UploadLecturePageProps) {
  const { classId: paramClassId } = useParams<{ classId: string }>();
  const classId = overrideClassId ?? paramClassId ?? "";
  const navigate = useNavigate();

  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<number>(0);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  function isAudioOrVideo(selected: File): boolean {
    if (selected.type.startsWith("audio/") || selected.type.startsWith("video/")) {
      return true;
    }
    const lowerName = selected.name.toLowerCase();
    return ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setValidationError(null);
    setUploadError(null);

    const selected = e.target.files?.[0];
    if (!selected) {
      setFile(null);
      return;
    }

    if (!isAudioOrVideo(selected)) {
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setValidationError(
        `"${selected.name}" is not a supported file type. Please choose an audio or video recording (MP4, MOV, WebM, MP3, WAV, or M4A).`
      );
      return;
    }

    if (selected.size > MAX_FILE_SIZE_BYTES) {
      const sizeMb = (selected.size / (1024 * 1024)).toFixed(1);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setValidationError(
        `File is too large (${sizeMb} MB). Recordings must be ${MAX_FILE_SIZE_MB} MB or smaller.`
      );
      return;
    }

    setFile(selected);
  }

  function startUpload() {
    if (!title.trim()) {
      setValidationError("Please enter a title for this lecture.");
      return;
    }
    if (!file) {
      setValidationError("Please select an audio or video file to upload.");
      return;
    }

    setValidationError(null);
    setUploadError(null);
    setUploading(true);
    setProgress(0);

    const formData = new FormData();
    formData.append("title", title.trim());
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open(
      "POST",
      `${API_BASE_URL}/classes/${encodeURIComponent(String(classId))}/lectures/`
    );

    const token = getStoredToken();
    if (token) {
      xhr.setRequestHeader("Authorization", `Token ${token}`);
    }

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        setProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      setUploading(false);
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText);
          const lectureId = data.id ?? data.lecture_id;
          if (lectureId != null) {
            navigate(`/professor/class/${classId}/lectures/${lectureId}/status`);
          } else {
            setUploadError("Upload completed, but no lecture ID was returned by the server.");
          }
        } catch {
          setUploadError("Upload completed, but the server response was invalid.");
        }
      } else {
        let message = `Upload failed (HTTP ${xhr.status}). Please try again.`;
        try {
          const errJson = JSON.parse(xhr.responseText);
          if (typeof errJson.detail === "string") message = errJson.detail;
          else if (typeof errJson.error === "string") message = errJson.error;
          else if (Array.isArray(errJson.file) && errJson.file[0]) message = errJson.file[0];
          else if (Array.isArray(errJson.title) && errJson.title[0]) message = errJson.title[0];
        } catch {
          // Keep fallback HTTP message
        }
        setUploadError(message);
      }
    };

    xhr.onerror = () => {
      setUploading(false);
      setUploadError("Network error while uploading. Check your connection and click Retry.");
    };

    xhr.send(formData);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!uploading) {
      startUpload();
    }
  }

  return (
    <div className="w-full text-white">
      <div className="mb-5">
        <h2 className="text-lg sm:text-xl font-bold tracking-tight text-white">
          Upload Lecture Recording
        </h2>
        <p className="text-slate-400 text-xs sm:text-sm mt-1">
          Select an audio or video recording (max {MAX_FILE_SIZE_MB} MB) to generate quiz questions.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {/* Title Field */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="lecture-title" className="text-xs font-semibold text-slate-300">
            Lecture Title
          </label>
          <input
            id="lecture-title"
            type="text"
            value={title}
            disabled={uploading}
            onChange={(e) => {
              setTitle(e.target.value);
              if (validationError) setValidationError(null);
            }}
            placeholder="e.g., Lecture 8: Pipelining and Data Hazards"
            className="rounded-xl border border-slate-800 bg-[#0A101F] px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:border-[#38BDF8] focus:outline-none focus:ring-1 focus:ring-[#38BDF8] disabled:opacity-50"
          />
        </div>

        {/* File Picker */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-300">
            Recording File (Audio or Video)
          </label>
          <div
            onClick={() => !uploading && fileInputRef.current?.click()}
            className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
              uploading
                ? "border-slate-800 bg-[#0A101F]/40 cursor-not-allowed opacity-60"
                : "border-slate-700/80 bg-[#0A101F] hover:border-[#38BDF8] cursor-pointer"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*,video/*"
              disabled={uploading}
              onChange={handleFileChange}
              className="hidden"
            />
            {file ? (
              <div className="flex flex-col items-center gap-1">
                <span className="font-semibold text-sm text-[#38BDF8] break-all">{file.name}</span>
                <span className="text-xs text-slate-400">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB • Click to replace file
                </span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-1">
                <span className="font-medium text-sm text-slate-200">
                  Click to select an audio or video file
                </span>
                <span className="text-xs text-slate-400">
                  MP4, MOV, WebM, MP3, WAV, or M4A up to {MAX_FILE_SIZE_MB} MB
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Validation Message */}
        {validationError && (
          <div className="rounded-xl border border-amber-500/40 bg-amber-950/50 px-4 py-3 text-xs sm:text-sm text-amber-300">
            {validationError}
          </div>
        )}

        {/* Upload Progress */}
        {uploading && (
          <div className="flex flex-col gap-2 rounded-xl border border-slate-800 bg-[#0A101F] p-4">
            <div className="flex items-center justify-between text-xs sm:text-sm">
              <span className="font-medium text-slate-200">Uploading recording…</span>
              <span className="font-bold text-[#38BDF8]">{progress}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
              <div
                className="h-full bg-[#38BDF8] transition-all duration-150"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Upload Error + Retry */}
        {uploadError && (
          <div className="flex items-center justify-between gap-4 rounded-xl border border-rose-500/40 bg-rose-950/50 px-4 py-3">
            <span className="text-xs sm:text-sm font-medium text-rose-300">{uploadError}</span>
            <button
              type="button"
              onClick={startUpload}
              className="shrink-0 rounded-lg bg-rose-400 px-3.5 py-1.5 text-xs font-bold text-slate-950 hover:bg-rose-300 cursor-pointer"
            >
              Retry
            </button>
          </div>
        )}

        {/* Submit Button */}
        <div className="flex items-center justify-end pt-1">
          <button
            type="submit"
            disabled={uploading || !file || !title.trim()}
            className="rounded-xl bg-[#38BDF8] hover:bg-[#0EA5E9] px-5 py-2.5 text-xs sm:text-sm font-bold text-[#0A101D] disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer transition-colors shadow-md shadow-sky-500/20"
          >
            {uploading ? `Uploading (${progress}%)…` : "Upload lecture →"}
          </button>
        </div>
      </form>
    </div>
  );

}
