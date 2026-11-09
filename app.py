import os
import json
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, Response, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
import zipfile
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx

from db import get_db, init_db, hash_pw

app = FastAPI(title="ShowMe", docs_url=None, redoc_url=None)

os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("static/audio", exist_ok=True)
os.makedirs("static/uploads", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
def on_startup():
    init_db()

def get_current_user(request: Request):
    token = request.cookies.get("showme_session")
    if not token:
        return None
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT u.* FROM users u
        JOIN sessions s ON u.id = s.user_id
        WHERE s.token = ?
    """, (token,))
    user = c.fetchone()
    conn.close()
    return dict(user) if user else None

def require_user(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user

def parse_profile(row):
    if not row:
        return None
    data = dict(row)
    try:
        data["socials"] = json.loads(data.get("socials_json") or "{}")
    except Exception:
        data["socials"] = {}
    try:
        data["badges"] = json.loads(data.get("badges_json") or "[]")
    except Exception:
        data["badges"] = []
    try:
        data["custom_links"] = json.loads(data.get("custom_links_json") or "[]")
    except Exception:
        data["custom_links"] = []
    return data

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = get_current_user(request)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM users")
    total_users = c.fetchone()["count"]
    c.execute("SELECT COUNT(*) as count FROM invites")
    total_invites = c.fetchone()["count"]
    c.execute("SELECT SUM(clicks) as clicks FROM invites")
    total_clicks = c.fetchone()["clicks"] or 0
    c.execute("""
        SELECT u.username, u.is_owner, u.badge_title, p.display_name, p.avatar_url, p.views
        FROM users u
        LEFT JOIN profiles p ON u.id = p.user_id
        ORDER BY p.views DESC LIMIT 6
    """)
    featured = [dict(r) for r in c.fetchall()]
    conn.close()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        "total_users": total_users,
        "total_invites": total_invites,
        "total_clicks": total_clicks,
        "featured": featured
    })

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if get_current_user(request):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("register.html", {"request": request, "error": None})

@app.post("/register", response_class=HTMLResponse)
async def register_action(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    username = username.strip().lower()
    email = email.strip().lower()
    if len(username) < 3 or not username.isalnum():
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username must be 3+ alphanumeric characters."})
    if len(password) < 6:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Password must be at least 6 characters."})
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
    if c.fetchone():
        conn.close()
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username or email is already taken."})
    
    hashed, salt = hash_pw(password)
    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO users (username, email, password_hash, salt, is_owner, is_verified, badge_title, created_at)
        VALUES (?, ?, ?, ?, 0, 0, 'Member', ?)
    """, (username, email, hashed, salt, now))
    user_id = c.lastrowid
    
    c.execute("""
        INSERT INTO profiles (
            user_id, display_name, bio, avatar_url, banner_url, background_url,
            bg_effect, theme, font_family, accent_color, card_opacity, card_blur,
            card_border_radius, audio_url, audio_title, audio_artist, audio_autoplay,
            socials_json, badges_json, custom_links_json
        ) VALUES (
            ?, ?, 'No signal detected yet.',
            'https://api.dicebear.com/7.x/bottts/svg?seed=' || ?,
            '', '', 'particles', 'cyberpunk', 'JetBrains Mono', '#8b5cf6', 0.85, 12, 16,
            '', '', '', 0, '{}', '["Initiate"]', '[]'
        )
    """, (user_id, username, username))
    
    token = secrets.token_hex(32)
    c.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, user_id, now))
    conn.commit()
    conn.close()
    
    resp = RedirectResponse("/dashboard", status_code=303)
    resp.set_cookie("showme_session", token, max_age=86400*30, httponly=True)
    return resp

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login", response_class=HTMLResponse)
async def login_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    username = username.strip().lower()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username))
    user = c.fetchone()
    if not user:
        conn.close()
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials provided."})
    
    calc_hash, _ = hash_pw(password, user["salt"])
    if calc_hash != user["password_hash"]:
        conn.close()
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials provided."})
    
    token = secrets.token_hex(32)
    now = datetime.utcnow().isoformat()
    c.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, user["id"], now))
    conn.commit()
    conn.close()
    
    resp = RedirectResponse("/dashboard", status_code=303)
    resp.set_cookie("showme_session", token, max_age=86400*30, httponly=True)
    return resp

@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("showme_session")
    if token:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("showme_session")
    return resp

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = require_user(request)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM profiles WHERE user_id = ?", (user["id"],))
    profile = parse_profile(c.fetchone())
    
    c.execute("SELECT * FROM invites WHERE user_id = ? ORDER BY id DESC", (user["id"],))
    invites = [dict(r) for r in c.fetchall()]
    
    c.execute("""
        SELECT l.*, i.slug FROM invite_logs l
        JOIN invites i ON l.invite_id = i.id
        WHERE i.user_id = ?
        ORDER BY l.id DESC LIMIT 15
    """, (user["id"],))
    recent_clicks = [dict(r) for r in c.fetchall()]

    all_users = []
    if user.get("is_owner"):
        c.execute("""
            SELECT u.id, u.username, u.email, u.is_owner, u.is_verified, u.badge_title, u.created_at, p.views
            FROM users u
            LEFT JOIN profiles p ON u.id = p.user_id
            ORDER BY u.id ASC
        """)
        all_users = [dict(r) for r in c.fetchall()]

    conn.close()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "profile": profile,
        "invites": invites,
        "recent_clicks": recent_clicks,
        "all_users": all_users,
        "msg": request.query_params.get("msg")
    })

@app.post("/dashboard/profile")
async def update_profile(
    request: Request,
    display_name: str = Form(""),
    bio: str = Form(""),
    avatar_url: str = Form(""),
    banner_url: str = Form(""),
    background_url: str = Form(""),
    bg_effect: str = Form("particles"),
    theme: str = Form("cyberpunk"),
    font_family: str = Form("JetBrains Mono"),
    accent_color: str = Form("#8b5cf6"),
    text_color: str = Form("#f8fafc"),
    card_opacity: float = Form(0.85),
    card_blur: int = Form(12),
    card_border_radius: int = Form(16),
    audio_url: str = Form(""),
    audio_title: str = Form(""),
    audio_artist: str = Form(""),
    audio_autoplay: Optional[int] = Form(0),
    audio_loop: Optional[int] = Form(1),
    layout_style: str = Form("glass_card"),
    custom_css: str = Form(""),
    social_discord: str = Form(""),
    social_twitter: str = Form(""),
    social_github: str = Form(""),
    social_spotify: str = Form(""),
    social_telegram: str = Form(""),
    social_youtube: str = Form(""),
    social_twitch: str = Form(""),
    social_instagram: str = Form(""),
    custom_links_json_str: str = Form("[]")
):
    user = require_user(request)
    socials = {
        "discord": social_discord.strip(),
        "twitter": social_twitter.strip(),
        "github": social_github.strip(),
        "spotify": social_spotify.strip(),
        "telegram": social_telegram.strip(),
        "youtube": social_youtube.strip(),
        "twitch": social_twitch.strip(),
        "instagram": social_instagram.strip()
    }
    socials = {k: v for k, v in socials.items() if v}
    
    try:
        json.loads(custom_links_json_str)
        valid_custom_links = custom_links_json_str
    except Exception:
        valid_custom_links = "[]"
        
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        UPDATE profiles SET
            display_name = ?,
            bio = ?,
            avatar_url = ?,
            banner_url = ?,
            background_url = ?,
            bg_effect = ?,
            theme = ?,
            font_family = ?,
            accent_color = ?,
            text_color = ?,
            card_opacity = ?,
            card_blur = ?,
            card_border_radius = ?,
            audio_url = ?,
            audio_title = ?,
            audio_artist = ?,
            audio_autoplay = ?,
            audio_loop = ?,
            layout_style = ?,
            custom_css = ?,
            socials_json = ?,
            custom_links_json = ?
        WHERE user_id = ?
    """, (
        display_name, bio, avatar_url, banner_url, background_url,
        bg_effect, theme, font_family, accent_color, text_color,
        card_opacity, card_blur, card_border_radius,
        audio_url, audio_title, audio_artist, audio_autoplay, audio_loop,
        layout_style, custom_css, json.dumps(socials), valid_custom_links,
        user["id"]
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/dashboard?msg=Profile+Updated", status_code=303)

@app.post("/dashboard/invite/create")
async def create_invite(
    request: Request,
    slug: str = Form(...),
    discord_code: str = Form(...),
    custom_title: str = Form(""),
    custom_desc: str = Form(""),
    accent_color: str = Form("#5865F2"),
    expires_in_days: int = Form(0)
):
    user = require_user(request)
    slug = slug.strip().lower()
    raw_code = discord_code.strip()
    clean_code = raw_code.replace("https://discord.gg/", "").replace("discord.gg/", "").split("?")[0].strip()
    
    destination_url = f"https://discord.gg/{clean_code}"
    expires_at = None
    if expires_in_days > 0:
        expires_at = (datetime.utcnow() + timedelta(days=expires_in_days)).isoformat()
        
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM invites WHERE slug = ?", (slug,))
    if c.fetchone():
        conn.close()
        return RedirectResponse("/dashboard?msg=Error:+Slug+already+in+use", status_code=303)
        
    c.execute("""
        INSERT INTO invites (
            user_id, slug, discord_code, destination_url, custom_title, custom_desc,
            accent_color, expires_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user["id"], slug, clean_code, destination_url, custom_title, custom_desc,
        accent_color, expires_at, datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()
    return RedirectResponse("/dashboard?msg=Invite+Slug+Constructed", status_code=303)

@app.post("/dashboard/invite/{invite_id}/delete")
async def delete_invite(request: Request, invite_id: int):
    user = require_user(request)
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM invite_logs WHERE invite_id = ?", (invite_id,))
    c.execute("DELETE FROM invites WHERE id = ? AND user_id = ?", (invite_id, user["id"]))
    conn.commit()
    conn.close()
    return RedirectResponse("/dashboard?msg=Invite+Deleted", status_code=303)

@app.get("/api/discord/check/{code}")
async def check_discord_invite(code: str):
    clean = code.replace("https://discord.gg/", "").replace("discord.gg/", "").split("?")[0].strip()
    api_url = f"https://discord.com/api/v10/invites/{clean}?with_counts=true"
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(api_url)
            if resp.status_code == 200:
                data = resp.json()
                guild = data.get("guild", {})
                return {
                    "valid": True,
                    "guild_name": guild.get("name"),
                    "guild_id": guild.get("id"),
                    "icon": guild.get("icon"),
                    "approximate_member_count": data.get("approximate_member_count", 0),
                    "approximate_presence_count": data.get("approximate_presence_count", 0),
                    "expires_at": data.get("expires_at")
                }
            return {"valid": False, "status": resp.status_code}
    except Exception as e:
        return {"valid": False, "error": str(e)}

@app.get("/inv/{slug}", response_class=HTMLResponse)
async def vanity_invite(request: Request, slug: str):
    slug = slug.strip().lower()
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT i.*, u.username, u.is_owner, u.badge_title
        FROM invites i
        JOIN users u ON i.user_id = u.id
        WHERE i.slug = ?
    """, (slug,))
    invite = c.fetchone()
    if not invite:
        conn.close()
        raise HTTPException(status_code=404, detail="Vanity invite not found")
    
    invite_dict = dict(invite)
    
    is_expired = False
    if invite_dict.get("expires_at"):
        try:
            exp_time = datetime.fromisoformat(invite_dict["expires_at"])
            if datetime.utcnow() > exp_time:
                is_expired = True
        except Exception:
            pass
            
    client_ip = request.client.host if request.client else "unknown"
    ip_hash = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:16]
    user_agent = request.headers.get("user-agent", "")[:200]
    referrer = request.headers.get("referer", "")[:200]
    
    c.execute("UPDATE invites SET clicks = clicks + 1 WHERE id = ?", (invite_dict["id"],))
    c.execute("""
        INSERT INTO invite_logs (invite_id, ip_hash, user_agent, referrer, visited_at)
        VALUES (?, ?, ?, ?, ?)
    """, (invite_dict["id"], ip_hash, user_agent, referrer, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    
    return templates.TemplateResponse("invite.html", {
        "request": request,
        "invite": invite_dict,
        "is_expired": is_expired
    })

@app.post("/dashboard/admin/grant-owner")
async def grant_owner(request: Request, target_user_id: int = Form(...)):
    user = require_user(request)
    if not user.get("is_owner"):
        raise HTTPException(status_code=403, detail="Forbidden: Root Owner access required")
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_owner = 1, is_verified = 1, badge_title = 'Co-Owner' WHERE id = ?", (target_user_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/dashboard?msg=Owner+Privileges+Granted", status_code=303)

@app.post("/dashboard/admin/verify-user")
async def verify_user(request: Request, target_user_id: int = Form(...)):
    user = require_user(request)
    if not user.get("is_owner"):
        raise HTTPException(status_code=403, detail="Forbidden")
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_verified = 1 WHERE id = ?", (target_user_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/dashboard?msg=User+Verified", status_code=303)

@app.get("/download-source")
async def download_source():
    zip_path = "showme_release.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk("."):
            if ".git" in root or "__pycache__" in root:
                continue
            for f in files:
                if f.endswith(".zip") or f.endswith(".db"):
                    continue
                file_path = os.path.join(root, f)
                arcname = os.path.relpath(file_path, ".")
                zf.write(file_path, arcname)
    return FileResponse(zip_path, media_type="application/zip", filename="showme.zip")

@app.get("/usr/{username}", response_class=HTMLResponse)
async def public_profile(request: Request, username: str):
    username = username.strip().lower()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Operative profile not found")
        
    user_dict = dict(user)
    c.execute("SELECT * FROM profiles WHERE user_id = ?", (user_dict["id"],))
    profile = parse_profile(c.fetchone())
    
    c.execute("SELECT * FROM invites WHERE user_id = ? AND is_active = 1", (user_dict["id"],))
    user_invites = [dict(r) for r in c.fetchall()]
    
    client_ip = request.client.host if request.client else "unknown"
    ip_hash = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:16]
    user_agent = request.headers.get("user-agent", "")[:200]
    
    c.execute("UPDATE profiles SET views = views + 1 WHERE user_id = ?", (user_dict["id"],))
    c.execute("""
        INSERT INTO profile_views (user_id, ip_hash, user_agent, viewed_at)
        VALUES (?, ?, ?, ?)
    """, (user_dict["id"], ip_hash, user_agent, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "target_user": user_dict,
        "profile": profile,
        "invites": user_invites
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
