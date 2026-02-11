import os
import psycopg2
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL 환경변수가 필요합니다.")
    return psycopg2.connect(DATABASE_URL)

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory_state (
              tank TEXT PRIMARY KEY,
              grain TEXT NOT NULL,
              qty TEXT NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """)
        conn.commit()

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/state")
def get_state():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tank, grain, qty FROM inventory_state;")
            rows = cur.fetchall()
    data = {tank: {"grain": grain, "qty": qty} for tank, grain, qty in rows}
    return JSONResponse(data)

@app.post("/api/state")
async def set_state(payload: dict):
    with get_conn() as conn:
        with conn.cursor() as cur:
            for tank, v in payload.items():
                grain = (v.get("grain") or "").strip()
                qty = (v.get("qty") or "").strip()
                if not tank:
                    continue
                if grain == "" and qty == "":
                    continue
                cur.execute("""
                INSERT INTO inventory_state(tank, grain, qty)
                VALUES (%s, %s, %s)
                ON CONFLICT (tank) DO UPDATE SET
                  grain = EXCLUDED.grain,
                  qty   = EXCLUDED.qty,
                  updated_at = now();
                """, (tank.upper(), grain, qty))
        conn.commit()
    return {"ok": True}
