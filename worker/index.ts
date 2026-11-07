import { Hono } from "hono"

const app = new Hono()

app.get("/api/edge/health", (c) => c.json({ ok: true, edge: true }))
app.all("/api/*", (c) => c.json({ error: "not_implemented" }, 501))

export default app
