import { WorkflowEntrypoint, type WorkflowEvent, type WorkflowStep } from "cloudflare:workers";
import type { Env, PublishParams } from "../env";

export class PublishWorkflow extends WorkflowEntrypoint<Env, PublishParams> {
  async run(event: WorkflowEvent<PublishParams>, step: WorkflowStep) {
    const { post_id, publish_at } = event.payload;
    if (publish_at) await step.sleepUntil("scheduled slot", new Date(publish_at));

    await step.do("publish", { retries: { limit: 5, delay: "1 minute", backoff: "exponential" }, timeout: "5 minutes" }, async () => {
      const res = await this.env.AGENT_RUNTIME.getByName(this.env.WORKSPACE_ID).fetch("http://container/jobs/publish", {
        method: "POST",
        headers: { "content-type": "application/json", "Idempotency-Key": post_id },
        body: JSON.stringify({ post_id }),
      });
      // non-2xx throws so the step retries; the job is idempotent on the key
      if (!res.ok) throw new Error(`publish job failed: ${res.status} ${(await res.text()).slice(0, 200)}`);
    });

    await step.do("audit", async () => {
      await this.env.DB.prepare(
        "INSERT INTO audit (id, ts, thread_id, actor, agent, action, tool, status, mode, detail) VALUES (?, ?, NULL, 'system', NULL, 'publish.workflow', NULL, 'ok', 'live', ?)",
      )
        .bind(crypto.randomUUID(), new Date().toISOString(), JSON.stringify({ post_id }))
        .run();
    });
  }
}
