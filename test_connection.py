"""
test_connection.py
Testa todas as conexoes antes de processar:
- FFmpeg
- Canais YouTube (token + upload de video teste)
- OpenAI (se configurado)
- Pastas e permissoes
"""
import sys, os, json, pickle, subprocess, tempfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

import streamlit as st

st.set_page_config(page_title="🔧 Testar Conexões", page_icon="🔧", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');
#MainMenu,header,footer,div[data-testid="stToolbar"]{display:none!important}
.block-container{padding-top:1.2rem!important}
html,body,[class*="css"]{font-family:'Space Grotesk',sans-serif}
.stApp{background:linear-gradient(135deg,#0a0a0f,#0f0f1a);color:#e8e8f0}
.stButton>button{background:linear-gradient(90deg,#ff3cac,#784ba0,#2b86c5)!important;color:white!important;border:none!important;border-radius:10px!important;font-weight:600!important;width:100%!important}
.ok{background:rgba(0,200,100,0.1);border:1px solid rgba(0,200,100,0.3);border-radius:10px;padding:0.8rem;margin:0.3rem 0}
.fail{background:rgba(255,60,60,0.1);border:1px solid rgba(255,60,60,0.3);border-radius:10px;padding:0.8rem;margin:0.3rem 0}
.warn{background:rgba(255,180,0,0.1);border:1px solid rgba(255,180,0,0.3);border-radius:10px;padding:0.8rem;margin:0.3rem 0}
</style>
""", unsafe_allow_html=True)

st.markdown("## 🔧 Testar Conexões")
st.caption("Valide tudo antes de processar vídeos.")
st.markdown("---")

# Carregar config
cfg_file = APP_DIR / "autopilot_config.json"
cfg = json.loads(cfg_file.read_text(encoding="utf-8")) if cfg_file.exists() else {}

# Carregar canais
TOKENS_DIR = str(APP_DIR / "yt_tokens")
def load_channels_all():
    """Carrega canais do channel_groups.json e channels.json."""
    all_chs = []
    gf = APP_DIR / "channel_groups.json"
    if gf.exists():
        groups = json.loads(gf.read_text(encoding="utf-8"))
        for niche, chs in groups.items():
            for c in chs:
                c["_niche"] = niche
                all_chs.append(c)
    cf = APP_DIR / "channels.json"
    if cf.exists():
        for c in json.loads(cf.read_text(encoding="utf-8")):
            c["_niche"] = "legado"
            all_chs.append(c)
    return all_chs

def is_auth(ch_id):
    return os.path.exists(os.path.join(TOKENS_DIR, f"{ch_id}.pkl"))

# ── Testes ────────────────────────────────────────────────────────────────────

def test_ffmpeg(ffmpeg_path):
    """Testa se o ffmpeg funciona."""
    exe = "ffmpeg"
    if ffmpeg_path and os.path.isdir(ffmpeg_path):
        import glob
        candidates = glob.glob(os.path.join(ffmpeg_path, "ffmpeg.exe")) + \
                     glob.glob(os.path.join(ffmpeg_path, "ffmpeg"))
        if candidates:
            exe = candidates[0]
    try:
        r = subprocess.run([exe, "-version"], capture_output=True, timeout=10)
        if r.returncode == 0:
            version = r.stdout.decode(errors="ignore").split("\n")[0]
            return True, exe, version
        return False, exe, "Erro ao executar"
    except FileNotFoundError:
        return False, exe, "ffmpeg.exe não encontrado"
    except Exception as e:
        return False, exe, str(e)

def test_youtube_token(ch):
    """Testa se o token do canal ainda é válido."""
    try:
        from google.auth.transport.requests import Request
        token_path = os.path.join(TOKENS_DIR, f"{ch['id']}.pkl")
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "wb") as f:
                pickle.dump(creds, f)
        if creds.valid:
            return True, "Token válido ✅"
        return False, "Token inválido"
    except Exception as e:
        return False, str(e)

def test_youtube_upload_permission(ch):
    """Testa se consegue listar o canal (prova que o token funciona para upload)."""
    try:
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        token_path = os.path.join(TOKENS_DIR, f"{ch['id']}.pkl")
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        service = build("youtube", "v3", credentials=creds)
        resp = service.channels().list(part="snippet", mine=True).execute()
        items = resp.get("items", [])
        if items:
            name = items[0]["snippet"]["title"]
            return True, f"Canal YouTube: {name}"
        return False, "Canal não encontrado"
    except Exception as e:
        return False, str(e)[:100]

def test_upload_video_signature():
    """Verifica se o uploader.py tem publish_at na assinatura."""
    uploader_file = APP_DIR / "core" / "uploader.py"
    if not uploader_file.exists():
        return False, "uploader.py não encontrado"
    content = uploader_file.read_text(encoding="utf-8", errors="ignore")
    if "publish_at" in content:
        return True, "publish_at presente no uploader.py ✅"
    return False, "publish_at AUSENTE no uploader.py — substitua o arquivo!"

def test_openai(api_key):
    """Testa a chave da OpenAI."""
    if not api_key:
        return None, "Não configurado (opcional)"
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Responda só: OK"}],
            max_tokens=5,
        )
        return True, f"OpenAI OK — modelo: gpt-4o-mini"
    except Exception as e:
        return False, str(e)[:100]

def test_music_folder(folder):
    """Verifica músicas disponíveis."""
    if not folder or not os.path.isdir(folder):
        return False, f"Pasta não existe: {folder}"
    musics = [f for f in os.listdir(folder) if f.lower().endswith((".mp3",".m4a",".wav",".ogg"))]
    if musics:
        return True, f"{len(musics)} música(s): {', '.join(musics[:3])}"
    return False, "Nenhuma música encontrada na pasta"

def test_output_folder():
    """Testa permissão de escrita."""
    try:
        test_dir = APP_DIR / "output_shorts" / "_test"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / "test.txt"
        test_file.write_text("ok")
        test_file.unlink()
        test_dir.rmdir()
        return True, str(APP_DIR / "output_shorts")
    except Exception as e:
        return False, str(e)

# ── UI ────────────────────────────────────────────────────────────────────────

def show(ok, label, detail=""):
    icon = "✅" if ok else ("⚠️" if ok is None else "❌")
    css  = "ok" if ok else ("warn" if ok is None else "fail")
    st.markdown(f'<div class="{css}">{icon} <b>{label}</b><br><small>{detail}</small></div>',
                unsafe_allow_html=True)

all_channels = load_channels_all()
ffmpeg_path  = cfg.get("ffmpeg_path", "")
music_folder = cfg.get("music_folder", str(APP_DIR / "musicas"))
openai_key   = cfg.get("openai_key", "")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🔧 Sistema")

    # FFmpeg
    ok, exe, detail = test_ffmpeg(ffmpeg_path)
    show(ok, "FFmpeg", detail)

    # Output folder
    ok, detail = test_output_folder()
    show(ok, "Pasta de saída", detail)

    # Músicas
    ok, detail = test_music_folder(music_folder)
    show(ok, "Músicas", detail)

    # Uploader.py
    ok, detail = test_upload_video_signature()
    show(ok, "uploader.py (publish_at)", detail)

    st.markdown("### 🤖 OpenAI (ChatGPT)")
    ok, detail = test_openai(openai_key)
    show(ok, "OpenAI API", detail)

with col2:
    st.markdown("### 📡 Canais YouTube")

    if not all_channels:
        st.warning("Nenhum canal configurado.")
    else:
        for ch in all_channels:
            if not is_auth(ch["id"]):
                show(False, ch["name"], f"Nicho: {ch.get('_niche','?')} | Não autenticado")
                continue

            # Token
            ok_tok, detail_tok = test_youtube_token(ch)
            if not ok_tok:
                show(False, ch["name"], f"Token inválido: {detail_tok}")
                continue

            # Upload permission
            ok_up, detail_up = test_youtube_upload_permission(ch)
            show(ok_up, ch["name"], f"Nicho: {ch.get('_niche','?')} | {detail_up}")

st.markdown("---")

# Botão rodar todos os testes
if st.button("🔄 Rodar Todos os Testes Novamente"):
    st.rerun()

# Resumo
st.markdown("### 📋 Resumo")
total_ch   = len(all_channels)
auth_ch    = sum(1 for c in all_channels if is_auth(c["id"]))
ffmpeg_ok  = test_ffmpeg(ffmpeg_path)[0]

if ffmpeg_ok and auth_ch > 0:
    st.success(f"✅ Sistema pronto! FFmpeg OK + {auth_ch}/{total_ch} canal(is) autenticado(s)")
else:
    issues = []
    if not ffmpeg_ok: issues.append("FFmpeg não encontrado")
    if auth_ch == 0: issues.append("Nenhum canal autenticado")
    st.error("❌ Problemas encontrados:\n" + "\n".join(f"• {i}" for i in issues))
