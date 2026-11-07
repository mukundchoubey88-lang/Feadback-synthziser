import { useState, type FormEvent } from "react";
import { client, formatWhen } from "../../lib/api";
import type { UploadJob, UploadResult } from "../../lib/types";
import { Notice, Panel } from "./ui";

function sampleFile(): File {
  const stamp = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const csv = [
    "source,customer_id,feedback_text,product,feature,timestamp,app_version",
    `in_app,cust-demo,"Search results load slowly on mobile web.",Analytics Portal,Search,${stamp},2.4.0`,
    `zendesk,cust-demo-2,"Export to CSV fails when the table has over 500 rows.",Analytics Portal,Export,${stamp},2.4.0`,
  ].join("\n");
  return new File([csv], "sample-feedback.csv", { type: "text/csv" });
}

export function IngestionPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [job, setJob] = useState<UploadJob | null>(null);
  const [jobId, setJobId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function upload(target: File) {
    setBusy(true);
    setError(null);
    setJob(null);
    try {
      const uploaded = await client.upload(target);
      setResult(uploaded);
      setJobId(uploaded.job_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function loadJob(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setJob(await client.job(jobId.trim()));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Job lookup failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid max-w-3xl gap-6">
      <div>
        <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Ingestion</p>
        <h1 className="mt-2 text-[36px] leading-none tracking-[-0.045em]">Upload CSV or JSON.</h1>
        <p className="mt-3 text-[15px] leading-relaxed text-ink-soft">
          Files go to <span className="text-ink">POST /api/feedback/upload</span>. The API validates timestamps, skips
          duplicates, and returns the job counts. Limit: 10 MB, 10,000 records, 10,000 characters per note.
        </p>
      </div>
      {error && <Notice tone="bad">{error}</Notice>}
      <Panel title="File">
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="file"
            accept=".csv,.json,text/csv,application/json"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="text-[13px]"
          />
          <button
            type="button"
            disabled={!file || busy}
            onClick={() => file && void upload(file)}
            className="bg-ink px-3 py-2 text-[13px] text-paper disabled:opacity-40"
          >
            {busy ? "Working…" : "Upload"}
          </button>
          <button type="button" disabled={busy} onClick={() => void upload(sampleFile())} className="border border-line px-3 py-2 text-[13px]">
            Upload a fresh sample
          </button>
        </div>
      </Panel>
      {result && (
        <Panel title="Upload result">
          <p className="text-[14px]">{result.message}</p>
          <dl className="mt-3 grid grid-cols-2 gap-2 text-[13px] sm:grid-cols-4">
            <div>
              <dt className="text-mute">Status</dt>
              <dd>{result.status}</dd>
            </div>
            <div>
              <dt className="text-mute">Inserted</dt>
              <dd>{result.inserted_records}</dd>
            </div>
            <div>
              <dt className="text-mute">Duplicates</dt>
              <dd>{result.duplicate_records}</dd>
            </div>
            <div>
              <dt className="text-mute">Rejected</dt>
              <dd>{result.rejected_records}</dd>
            </div>
          </dl>
          {result.errors && result.errors.length > 0 && (
            <pre className="mt-3 overflow-auto text-[12px] text-ink-soft">{JSON.stringify(result.errors, null, 2)}</pre>
          )}
        </Panel>
      )}
      <Panel title="Look up a job">
        <form className="flex flex-wrap gap-3" onSubmit={(event) => void loadJob(event)}>
          <input
            value={jobId}
            onChange={(event) => setJobId(event.target.value)}
            placeholder="Job UUID"
            className="min-w-[260px] flex-1 border border-line bg-paper px-3 py-2 text-[14px]"
          />
          <button type="submit" disabled={busy || !jobId.trim()} className="bg-ink px-3 py-2 text-[13px] text-paper disabled:opacity-40">
            Fetch job
          </button>
        </form>
        {job && (
          <p className="mt-3 text-[13px] text-ink-soft">
            {job.filename} · {job.format} · {job.status} · inserted {job.inserted_records} of {job.total_records} ·{" "}
            {formatWhen(job.completed_at ?? job.created_at)}
          </p>
        )}
      </Panel>
    </div>
  );
}
