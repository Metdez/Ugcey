// llm.internal: OpenAI-compatible chat/embeddings over the Workers AI binding.
import type { Env } from "../env";

export const CHAT_MODELS = new Set([
  "@cf/zai-org/glm-5.3",
  "@cf/zai-org/glm-4.7-flash",
  "@cf/deepseek-ai/deepseek-v4.1-flash-1017",
  "@cf/qwen/qwen3.8-27b",
  "@cf/openai/gpt-oss-120b",
]);
/** OpenAI models on Workers AI (unified billing) use the Responses API shape. */
export const RESPONSES_MODELS = new Set(["openai/gpt-6-luna"]);
export const EMBED_MODELS = new Set(["@cf/qwen/qwen3-embedding-0.6b", "@cf/baai/bge-m3"]);

export function errorResponse(status: number, code: string, message: string): Response {
  return Response.json({ error: { code, message } }, { status });
}

/** Keep `[DONE]`, drop `data:` JSON lines lacking `choices` (Workers AI trailing usage chunk), pass the rest. */
export function filterSseLine(line: string): string | null {
  if (!line.startsWith("data:")) return line;
  const payload = line.slice(5).trim();
  if (payload === "[DONE]") return line;
  try {
    const j = JSON.parse(payload);
    return j && typeof j === "object" && "choices" in j ? line : null;
  } catch {
    return null; // truncated or non-JSON data line would break the OpenAI SDK parser
  }
}

export function sseFilterStream(): TransformStream<string, string> {
  let buf = "";
  const emit = (line: string, c: TransformStreamDefaultController<string>) => {
    const out = filterSseLine(line);
    if (out !== null) c.enqueue(out + "\n");
  };
  return new TransformStream({
    transform(chunk, c) {
      buf += chunk;
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const l of lines) emit(l.replace(/\r$/, ""), c);
    },
    flush(c) {
      if (buf) emit(buf, c);
    },
  });
}

function upstreamError(e: unknown): Response {
  const msg = e instanceof Error ? e.message : String(e);
  const st = (e as { status?: number })?.status;
  const status = st && st >= 400 && st < 600 ? st : /\b429\b|rate.?limit|too many/i.test(msg) ? 429 : 502;
  return errorResponse(status, status === 429 ? "rate_limited" : "upstream_error", msg.slice(0, 500));
}

function aiOpts(env: Env): { gateway?: { id: string } } {
  return env.AI_GATEWAY_ID ? { gateway: { id: env.AI_GATEWAY_ID } } : {};
}

export async function handleLlm(req: Request, env: Env): Promise<Response> {
  const path = new URL(req.url).pathname;
  if (req.method !== "POST") return errorResponse(405, "method_not_allowed", "POST only");
  let body: Record<string, any>;
  try {
    body = await req.json();
  } catch {
    return errorResponse(400, "bad_json", "invalid JSON body");
  }
  const { model, ...rest } = body;
  if (path === "/v1/chat/completions") {
    if (typeof model !== "string" || !CHAT_MODELS.has(model))
      return errorResponse(400, "model_not_allowed", `model not allowed: ${model}`);
    try {
      const out = await (env.AI as any).run(model, rest, aiOpts(env));
      if (rest.stream === true && out instanceof ReadableStream) {
        const stream = out
          .pipeThrough(new TextDecoderStream())
          .pipeThrough(sseFilterStream())
          .pipeThrough(new TextEncoderStream());
        return new Response(stream, {
          headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
        });
      }
      return Response.json(out);
    } catch (e) {
      return upstreamError(e);
    }
  }
  if (path === "/v1/responses") {
    if (typeof model !== "string" || !RESPONSES_MODELS.has(model))
      return errorResponse(400, "model_not_allowed", `model not allowed: ${model}`);
    try {
      return Response.json(await (env.AI as any).run(model, rest, aiOpts(env)));
    } catch (e) {
      return upstreamError(e);
    }
  }
  if (path === "/v1/embeddings") {
    if (typeof model !== "string" || !EMBED_MODELS.has(model))
      return errorResponse(400, "model_not_allowed", `model not allowed: ${model}`);
    const input: string[] = Array.isArray(body.input) ? body.input : [body.input];
    if (!input.length || input.some((s) => typeof s !== "string"))
      return errorResponse(400, "bad_input", "input must be a string or string[]");
    try {
      const out = (await (env.AI as any).run(model, { text: input }, aiOpts(env))) as { data?: number[][] };
      if (!out?.data) return errorResponse(502, "upstream_error", "embedding response had no data");
      return Response.json({
        object: "list",
        model,
        data: out.data.map((embedding, index) => ({ object: "embedding", embedding, index })),
      });
    } catch (e) {
      return upstreamError(e);
    }
  }
  return errorResponse(404, "not_found", `unknown path ${path}`);
}
