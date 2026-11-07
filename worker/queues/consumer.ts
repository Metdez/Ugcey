import type { Env, JobMessage } from "../env";

// STREAM is not in the frozen Env; the binding exists in wrangler config only if added (see SUMMARY change requests).
type StreamVideo = { id: string; thumbnail?: string; hlsPlaybackUrl?: string };
type StreamBinding = { upload(url: string, p?: { creator?: string; meta?: Record<string, string> }): Promise<StreamVideo> };
const streamOf = (env: Env) => (env as unknown as { STREAM?: StreamBinding }).STREAM;

async function ingest(env: Env, m: Extract<JobMessage, { kind: "media.ingest" }>): Promise<void> {
  // shortcut: images/audio keep their original URL; copy to R2 once R2 is enabled
  if (m.media_kind !== "video") return;
  const stream = streamOf(env);
  if (!stream) return; // no Stream binding: documented no-op, original URL stays
  const v = await stream.upload(m.url, { creator: m.asset_id, meta: { asset_id: m.asset_id } });
  await env.DB.prepare("UPDATE assets SET url = COALESCE(?, url), thumbnail_url = COALESCE(?, thumbnail_url) WHERE id = ?")
    .bind(v.hlsPlaybackUrl ?? null, v.thumbnail ?? null, m.asset_id)
    .run();
}

export async function handleQueue(batch: MessageBatch<JobMessage>, env: Env): Promise<void> {
  for (const msg of batch.messages) {
    try {
      const m = msg.body;
      if (m.kind === "media.ingest") await ingest(env, m);
      else if (m.kind === "metric") env.METRICS.writeDataPoint({ blobs: [m.event, ...m.blobs], doubles: m.doubles, indexes: [m.event.slice(0, 96)] });
      msg.ack();
    } catch (e) {
      console.error("queue job failed", msg.id, e instanceof Error ? e.message : e);
      // after max_retries (wrangler config) the queue moves the message to ugecy-jobs-dlq
      msg.retry({ delaySeconds: 60 });
    }
  }
}
