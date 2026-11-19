// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { UploadLecturePage } from "./LectureUpload";

class FakeXHR {
  static instances: FakeXHR[] = [];
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null };
  status = 201;
  responseText = JSON.stringify({ id: 9, title: "Lecture 8", status: "pending" });
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  open = vi.fn();
  setRequestHeader = vi.fn();
  send = vi.fn();

  constructor() {
    FakeXHR.instances.push(this);
  }
}

function progress(loaded: number, total = 100): ProgressEvent {
  return { lengthComputable: true, loaded, total } as ProgressEvent;
}

async function chooseFile() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/lecture title/i), "Lecture 8");
  const input = document.querySelector('input[type="file"]');
  if (!(input instanceof HTMLInputElement)) throw new Error("missing file input");
  const file = new File(["audio"], "lecture.mp4", { type: "video/mp4" });
  await user.upload(input, file);
  await user.click(screen.getByRole("button", { name: /upload lecture/i }));
  return FakeXHR.instances.at(-1);
}

describe("UploadLecturePage progress", () => {
  afterEach(() => {
    cleanup();
    FakeXHR.instances = [];
    vi.unstubAllGlobals();
  });

  it("shows the browser upload percent and then opens the status page", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    render(
      <MemoryRouter initialEntries={["/professor/class/12"]}>
        <Routes>
          <Route path="/professor/class/:classId" element={<UploadLecturePage />} />
          <Route
            path="/professor/class/:classId/lectures/:lectureId/status"
            element={<p>Status for lecture</p>}
          />
        </Routes>
      </MemoryRouter>
    );

    const xhr = await chooseFile();
    if (!xhr) throw new Error("upload did not start");
    expect(String(xhr.open.mock.calls[0][1])).toMatch(/\/classes\/12\/lectures\/$/);

    await act(async () => {
      xhr.upload.onprogress?.(progress(40));
    });
    expect(screen.getByRole("progressbar", { name: "Uploading" }).getAttribute("aria-valuenow")).toBe(
      "40"
    );
    expect(screen.getByText("40%")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Uploading \(40%\)/ })).toBeTruthy();

    await act(async () => {
      xhr.onload?.();
    });
    expect(await screen.findByText("Status for lecture")).toBeTruthy();
  });

  it("hands the new lecture to the class page instead of leaving it", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const onSuccess = vi.fn();
    render(
      <MemoryRouter>
        <UploadLecturePage overrideClassId={12} onSuccess={onSuccess} />
      </MemoryRouter>
    );

    const xhr = await chooseFile();
    await act(async () => {
      xhr?.upload.onprogress?.(progress(25, 50));
    });
    expect(screen.getByText("50%")).toBeTruthy();

    await act(async () => {
      xhr?.onload?.();
    });
    expect(onSuccess).toHaveBeenCalledWith({ id: 9, title: "Lecture 8" });
    expect(screen.queryByText("Status for lecture")).toBeNull();
  });
});
