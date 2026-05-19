"""
upload_only.py v2
Faz upload dos videos ja gerados.
Chama a API do YouTube diretamente, sem importar uploader.py.
"""
import sys, os, json, datetime, time, threading, pickle
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

import streamlit as st

st.set_page_config(page_title="📤 Upload Vídeos", page_icon="📤", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');
#MainMenu,header,footer,div[data-testid="stToolbar"]{display:none!important}
.block-container{padding-top:1.2rem!important}
html,body,[class*="css"]{font-family:'Space Grotesk',sans-serif}
.stApp{background:linear-gradient(135deg,#0a0a0f,#0f0f1a);color:#e8e8f0}
.stButton>button{background:linear-gradient(90deg,#ff3cac,#784ba0,#2b86c5)!important;color:white!important;border:none!important;border-radius:10px!important;font-weight:600!important;width:100%!important}
</style>
""", unsafe_allow_html=True)

st.markdown("## 📤 Upload dos Vídeos Gerados")
st.markdown("---")

# ── Log ───────────────────────────────────────────────────────────────────────
LOG_FILE     = str(APP_DIR / "upload_only.log")
RUNNING_FILE = str(APP_DIR / "upload_only.flag")

def wlog(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def rlog(n=60):
    if not os.path.exists(LOG_FILE): return "Aguardando..."
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return "".join(f.readlines()[-n:])

def is_running():
    return os.path.exists(RUNNING_FILE)

def set_running(v):
    if v: open(RUNNING_FILE,"w").close()
    elif os.path.exists(RUNNING_FILE): os.remove(RUNNING_FILE)

# ── Funções de canal (lê direto do JSON, sem importar uploader) ───────────────
CHANNELS_FILE = str(APP_DIR / "channels.json")
TOKENS_DIR    = str(APP_DIR / "yt_tokens")

def load_channels():
    if not os.path.exists(CHANNELS_FILE): return []
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def is_authenticated(ch_id):
    return os.path.exists(os.path.join(TOKENS_DIR, f"{ch_id}.pkl"))

def get_service(ch_id, secrets_path):
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    token_path = os.path.join(TOKENS_DIR, f"{ch_id}.pkl")
    with open(token_path, "rb") as f:
        creds = pickle.load(f)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)

def do_upload(ch_id, secrets_path, video_path, title, description, tags, privacy, publish_at=""):
    """Upload direto via API — sem depender do uploader.py."""
    from googleapiclient.http import MediaFileUpload

    service = get_service(ch_id, secrets_path)

    status_body = {
        "privacyStatus": "private" if publish_at else privacy,
        "madeForKids": False,
        "selfDeclaredMadeForKids": False,
    }
    if publish_at:
        status_body["publishAt"] = publish_at

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags or [],
            "categoryId": "22",
        },
        "status": status_body,
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True,
                            chunksize=5*1024*1024)

    request = service.videos().insert(
        part=",".join(body.keys()), body=body, media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            wlog(f"   ⏳ {int(status.progress()*100)}%")

    vid_id = response.get("id")
    return f"https://youtube.com/shorts/{vid_id}"

# ── UI ────────────────────────────────────────────────────────────────────────
channels = [c for c in load_channels() if is_authenticated(c["id"])]

if not channels:
    st.error("❌ Nenhum canal conectado. Configure em channels.py primeiro.")
    st.stop()

st.success(f"✅ {len(channels)} canal(is) conectado(s): {', '.join(c['name'] for c in channels)}")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📁 Selecionar Vídeos")
    base_dir = APP_DIR / "output_shorts"
    folders  = sorted([f for f in base_dir.glob("*") if f.is_dir()], reverse=True) if base_dir.exists() else []

    if not folders:
        st.error("Nenhuma pasta output_shorts encontrada.")
        st.stop()

    selected_folder = st.selectbox("Pasta", [f.name for f in folders])
    video_dir = base_dir / selected_folder

    all_videos = sorted([f for f in video_dir.glob("*.mp4") if not f.name.startswith("_")])
    st.markdown(f"**{len(all_videos)} vídeo(s) encontrado(s):**")

    selected_videos = []
    for i, v in enumerate(all_videos):
        size_mb = v.stat().st_size / 1_048_576
        if st.checkbox(f"{v.name} ({size_mb:.1f} MB)", value=True, key=f"v_{i}"):
            selected_videos.append(v)

    st.caption(f"{len(selected_videos)} selecionado(s)")

with col2:
    st.markdown("### ⚙️ Configurações")

    titulo_modo = st.radio("Título", ["Usar nome do arquivo", "Título personalizado"])
    titulo_custom = ""
    if titulo_modo == "Título personalizado":
        titulo_custom = st.text_input("Título", value="Short Viral 🔥 #shorts")

    privacy = st.selectbox("Privacidade", ["public", "unlisted", "private"])

    agendar = st.toggle("📅 Agendar publicação", value=True)
    pub_iso_list = []

    if agendar:
        cfg_file = APP_DIR / "autopilot_config.json"
        cfg = json.loads(cfg_file.read_text(encoding="utf-8")) if cfg_file.exists() else {}
        schedules_ = cfg.get("publish_schedules", ["12:00","15:00","18:00","21:30"])
        clips_per  = cfg.get("clips_per_podcast", 5)
        days_ahead = cfg.get("days_ahead", 1)

        import pytz
        today = datetime.date.today()
        tz    = pytz.timezone("America/Sao_Paulo")

        st.markdown("**Preview de publicação:**")
        for i, v in enumerate(selected_videos):
            pod_idx  = i // clips_per
            slot     = schedules_[pod_idx % len(schedules_)]
            h, m     = map(int, slot.split(":"))
            day_off  = days_ahead + (pod_idx // len(schedules_))
            pub_date = today + datetime.timedelta(days=day_off)
            dt_loc   = datetime.datetime(pub_date.year, pub_date.month, pub_date.day, h, m)
            dt_utc   = tz.localize(dt_loc).astimezone(pytz.utc)
            pub_iso  = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            pub_iso_list.append(pub_iso)
            ch = channels[i % len(channels)]
            st.caption(f"📹 {v.name} → {ch['name']} → {pub_date.strftime('%d/%m')} {slot}")
    else:
        pub_iso_list = [""] * len(selected_videos)

st.markdown("---")

col_b1, col_b2, col_b3 = st.columns([2,1,1])
with col_b1:
    start = st.button(f"📤 Fazer Upload de {len(selected_videos)} vídeo(s)",
                      disabled=is_running() or not selected_videos)
with col_b2:
    if st.button("🔄 Atualizar"): st.rerun()
with col_b3:
    if st.button("🗑️ Limpar log"):
        open(LOG_FILE,"w").close()
        st.rerun()

st.markdown("### 📋 Log")
if is_running():
    st.warning("⚙️ Uploading... Clique **Atualizar** para ver o progresso.")
st.code(rlog(), language="bash")

# ── Thread de upload ──────────────────────────────────────────────────────────
if start and selected_videos and not is_running():
    open(LOG_FILE,"w").close()
    set_running(True)

    _vids      = list(selected_videos)
    _chs       = list(channels)
    _pub_isos  = list(pub_iso_list) + [""] * 50   # padding
    _privacy   = privacy
    _t_modo    = titulo_modo
    _t_custom  = titulo_custom

    def _run():
        try:
            wlog(f"📤 Iniciando upload de {len(_vids)} vídeo(s)...")
            wlog("=" * 50)
            ok = 0
            for idx, vp in enumerate(_vids):
                ch      = _chs[idx % len(_chs)]
                secrets = ch.get("secrets_path","")
                if not secrets or not os.path.exists(secrets):
                    wlog(f"⚠️ {ch['name']}: secrets não encontrado")
                    continue

                title = vp.stem.replace("_"," ").title() if _t_modo == "Usar nome do arquivo" else _t_custom
                pub   = _pub_isos[idx]
                slot_str = pub[11:16] + " UTC" if pub else "agora"

                wlog(f"\n[{idx+1}/{len(_vids)}] {vp.name}")
                wlog(f"   Canal: {ch['name']} | Horário: {slot_str}")
                wlog(f"   Título: {title[:60]}")

                try:
                    url = do_upload(
                        ch_id=ch["id"],
                        secrets_path=secrets,
                        video_path=str(vp),
                        title=title,
                        description="#shorts #podcast #viral #brasil",
                        tags=["shorts","podcast","viral","brasil"],
                        privacy=_privacy,
                        publish_at=pub,
                    )
                    wlog(f"   ✅ Publicado: {url}")
                    ok += 1
                except Exception as e:
                    wlog(f"   ❌ ERRO: {e}")

            wlog("\n" + "=" * 50)
            wlog(f"🎉 CONCLUÍDO: {ok}/{len(_vids)} enviado(s)")
        except Exception as e:
            import traceback
            wlog(f"❌ ERRO FATAL: {e}\n{traceback.format_exc()}")
        finally:
            set_running(False)

    threading.Thread(target=_run, daemon=True).start()
    time.sleep(1)
    st.rerun()

if is_running():
    time.sleep(3)
    st.rerun()
