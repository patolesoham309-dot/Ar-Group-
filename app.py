import os, sqlite3, uuid, shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "fleet.db"
UPLOAD_DIR = APP_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

SECRET_KEY = os.getenv("FLEET_SECRET_KEY", "CHANGE_THIS_SECRET_BEFORE_DEPLOYMENT")
ALGORITHM = "HS256"
TOKEN_MINUTES = 60 * 12
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

app = FastAPI(title="Diesel Fleet Management API", version="0.1.0")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT UNIQUE NOT NULL,
          full_name TEXT NOT NULL,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('super_admin','staff','driver')),
          fixed_bus_id INTEGER,
          active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS buses (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          bus_number TEXT UNIQUE NOT NULL,
          active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS routes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          route_name TEXT UNIQUE NOT NULL,
          active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS diesel_entries (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at TEXT NOT NULL,
          entry_date TEXT NOT NULL,
          driver_id INTEGER NOT NULL,
          bus_id INTEGER NOT NULL,
          route_id INTEGER NOT NULL,
          meter_km REAL NOT NULL,
          litres REAL NOT NULL,
          rate_per_litre REAL NOT NULL,
          full_tank INTEGER NOT NULL DEFAULT 1,
          meter_photo TEXT NOT NULL,
          pump_photo TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          reviewed_by INTEGER,
          review_note TEXT,
          FOREIGN KEY(driver_id) REFERENCES users(id),
          FOREIGN KEY(bus_id) REFERENCES buses(id),
          FOREIGN KEY(route_id) REFERENCES routes(id)
        );
        """)
        # Seed a first-run admin only when no users exist.
        count = c.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        if count == 0:
            username = os.getenv("FLEET_ADMIN_USER", "admin")
            password = os.getenv("FLEET_ADMIN_PASSWORD", "ChangeMe123!")
            c.execute(
                "INSERT INTO users(username,full_name,password_hash,role) VALUES(?,?,?,?)",
                (username, "System Administrator", pwd_context.hash(password), "super_admin")
            )
        # Seed demo buses/routes as editable examples.
        if c.execute("SELECT COUNT(*) FROM buses").fetchone()[0] == 0:
            c.executemany("INSERT INTO buses(bus_number) VALUES(?)",
                          [(f"BUS-{i:02d}",) for i in range(1, 31)])
        if c.execute("SELECT COUNT(*) FROM routes").fetchone()[0] == 0:
            c.executemany("INSERT INTO routes(route_name) VALUES(?)",
                          [(x,) for x in ["Pune-Goa", "Goa-Pune", "Hyderabad-Goa", "Pune-Nagpur", "Karad-Vijayawada"]])

init_db()

def current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired login")
    with db() as c:
        u = c.execute("SELECT * FROM users WHERE id=? AND active=1", (uid,)).fetchone()
    if not u:
        raise HTTPException(status_code=401, detail="User not active")
    return dict(u)

def require_admin(user=Depends(current_user)):
    if user["role"] not in ("super_admin", "staff"):
        raise HTTPException(status_code=403, detail="Admin/staff access required")
    return user

def save_image(upload: UploadFile) -> str:
    allowed = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    if upload.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPG, PNG or WEBP photos are accepted")
    name = f"{uuid.uuid4().hex}{allowed[upload.content_type]}"
    path = UPLOAD_DIR / name
    size = 0
    with path.open("wb") as out:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > 8 * 1024 * 1024:
                out.close()
                path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Each photo must be 8 MB or smaller")
            out.write(chunk)
    return name

@app.post("/api/login")
def login(username: str = Form(...), password: str = Form(...)):
    with db() as c:
        u = c.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
    if not u or not pwd_context.verify(password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="Username or password is incorrect")
    token = jwt.encode({"sub": str(u["id"]), "exp": datetime.utcnow() + timedelta(minutes=TOKEN_MINUTES)}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "role": u["role"], "full_name": u["full_name"]}

@app.get("/api/me")
def me(user=Depends(current_user)):
    return {"id": user["id"], "username": user["username"], "full_name": user["full_name"],
            "role": user["role"], "fixed_bus_id": user["fixed_bus_id"]}

@app.get("/api/buses")
def buses(user=Depends(current_user)):
    with db() as c:
        rows = c.execute("SELECT id,bus_number FROM buses WHERE active=1 ORDER BY bus_number").fetchall()
    return [dict(r) for r in rows]

@app.get("/api/routes")
def routes(user=Depends(current_user)):
    with db() as c:
        rows = c.execute("SELECT id,route_name FROM routes WHERE active=1 ORDER BY route_name").fetchall()
    return [dict(r) for r in rows]

@app.post("/api/admin/users")
def create_user(username: str = Form(...), full_name: str = Form(...), password: str = Form(...),
                role: str = Form(...), fixed_bus_id: Optional[str] = Form(None),
                admin=Depends(require_admin)):
    if role not in ("staff", "driver"):
        raise HTTPException(status_code=400, detail="Only staff or driver accounts can be created here")
    if len(password) < 10:
        raise HTTPException(status_code=400, detail="Password must be at least 10 characters")
    with db() as c:
        try:
            bus_value = int(fixed_bus_id) if fixed_bus_id and fixed_bus_id.strip() else None
            c.execute("INSERT INTO users(username,full_name,password_hash,role,fixed_bus_id) VALUES(?,?,?,?,?)",
                      (username, full_name, pwd_context.hash(password), role, bus_value))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Username already exists")
    return {"ok": True, "message": "Account created"}

@app.post("/api/admin/buses")
def create_bus(bus_number: str = Form(...), admin=Depends(require_admin)):
    with db() as c:
        try:
            c.execute("INSERT INTO buses(bus_number) VALUES(?)", (bus_number.strip(),))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Bus number already exists")
    return {"ok": True}

@app.post("/api/admin/routes")
def create_route(route_name: str = Form(...), admin=Depends(require_admin)):
    with db() as c:
        try:
            c.execute("INSERT INTO routes(route_name) VALUES(?)", (route_name.strip(),))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Route already exists")
    return {"ok": True}

@app.post("/api/diesel-entries")
def create_diesel_entry(
    entry_date: str = Form(...), bus_id: int = Form(...), route_id: int = Form(...),
    meter_km: float = Form(...), litres: float = Form(...), rate_per_litre: float = Form(...),
    full_tank: bool = Form(True),
    meter_photo: UploadFile = File(...), pump_photo: UploadFile = File(...),
    user=Depends(current_user)
):
    if user["role"] != "driver":
        raise HTTPException(status_code=403, detail="Only driver accounts can submit diesel entries")
    if min(meter_km, litres, rate_per_litre) <= 0:
        raise HTTPException(status_code=400, detail="KM, litres and diesel rate must be greater than zero")
    with db() as c:
        bus = c.execute("SELECT id FROM buses WHERE id=? AND active=1", (bus_id,)).fetchone()
        route = c.execute("SELECT id FROM routes WHERE id=? AND active=1", (route_id,)).fetchone()
        if not bus or not route:
            raise HTTPException(status_code=400, detail="Select a valid bus and route")
        if user["fixed_bus_id"] and user["fixed_bus_id"] != bus_id:
            raise HTTPException(status_code=403, detail="This driver is assigned to a different fixed bus")
    meter_name = save_image(meter_photo)
    try:
        pump_name = save_image(pump_photo)
    except Exception:
        (UPLOAD_DIR / meter_name).unlink(missing_ok=True)
        raise
    with db() as c:
        c.execute("""INSERT INTO diesel_entries
          (created_at,entry_date,driver_id,bus_id,route_id,meter_km,litres,rate_per_litre,full_tank,meter_photo,pump_photo)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
          (datetime.utcnow().isoformat(), entry_date, user["id"], bus_id, route_id, meter_km, litres,
           rate_per_litre, int(full_tank), meter_name, pump_name))
    return {"ok": True, "status": "pending", "message": "Entry submitted for office approval"}

@app.get("/api/admin/entries")
def list_entries(status: Optional[str] = None, admin=Depends(require_admin)):
    q = """SELECT e.*, u.full_name AS driver_name, b.bus_number, r.route_name,
           reviewer.full_name AS reviewer_name
           FROM diesel_entries e JOIN users u ON u.id=e.driver_id
           JOIN buses b ON b.id=e.bus_id JOIN routes r ON r.id=e.route_id
           LEFT JOIN users reviewer ON reviewer.id=e.reviewed_by"""
    params = ()
    if status in ("pending", "approved", "rejected"):
        q += " WHERE e.status=?"
        params = (status,)
    q += " ORDER BY e.id DESC"
    with db() as c:
        rows = c.execute(q, params).fetchall()
    return [dict(r) for r in rows]

@app.post("/api/admin/entries/{entry_id}/review")
def review_entry(entry_id: int, decision: str = Form(...), note: str = Form(""),
                 admin=Depends(require_admin)):
    if decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Decision must be approved or rejected")
    with db() as c:
        cur = c.execute("UPDATE diesel_entries SET status=?, reviewed_by=?, review_note=? WHERE id=? AND status='pending'",
                        (decision, admin["id"], note, entry_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Pending entry not found")
    return {"ok": True, "status": decision}

@app.get("/uploads/{filename}")
def get_upload(filename: str, token: Optional[str] = None):
    # Prototype supports a short-lived JWT query token for opening a photo in a new tab.
    # Production should use authenticated photo proxying or short-lived signed object-storage URLs.
    if not token:
        raise HTTPException(status_code=401, detail="Login token required")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired login")
    with db() as c:
        u = c.execute("SELECT id FROM users WHERE id=? AND active=1", (uid,)).fetchone()
    if not u:
        raise HTTPException(status_code=401, detail="User not active")
    path = UPLOAD_DIR / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(path)

@app.get("/api/admin/summary")
def summary(admin=Depends(require_admin)):
    with db() as c:
        counts = c.execute("""SELECT status, COUNT(*) n, SUM(litres) litres,
             SUM(litres*rate_per_litre) cost FROM diesel_entries GROUP BY status""").fetchall()
        bus_rows = c.execute("""SELECT b.bus_number, COUNT(e.id) entries, SUM(e.litres) litres,
             SUM(e.litres*e.rate_per_litre) cost
             FROM buses b LEFT JOIN diesel_entries e ON e.bus_id=b.id AND e.status='approved'
             GROUP BY b.id ORDER BY b.bus_number""").fetchall()
        route_rows = c.execute("""SELECT r.route_name, COUNT(e.id) entries, SUM(e.litres) litres,
             SUM(e.litres*e.rate_per_litre) cost
             FROM routes r LEFT JOIN diesel_entries e ON e.route_id=r.id AND e.status='approved'
             GROUP BY r.id ORDER BY r.route_name""").fetchall()
    return {"status_totals": [dict(x) for x in counts],
            "bus_totals": [dict(x) for x in bus_rows],
            "route_totals": [dict(x) for x in route_rows],
            "note": "KM/L average is intentionally not calculated from isolated refill records. Use verified full-to-full readings or trip-wise fuel consumed data."}

@app.get("/")
def home():
    return FileResponse(APP_DIR / "index.html")



