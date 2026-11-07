from fastapi import FastAPI

app = FastAPI(title="ugecy-agent")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "service": "ugecy-agent"}
