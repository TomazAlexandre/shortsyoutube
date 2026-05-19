import sys
import os
import glob
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import streamlit as st
import time as _time
from core.downloader import download_youtube_video, get_video_info, QUALITY_FORMATS
from core.analyzer import find_most_watched_segments
from core.editor import create_short
import pickle as _pickle

def _yt_upload(ch_id, secrets_path, video_path, title, description, tags, privacy, publish_at=""):
    """Chama a API do YouTube diretamente — sem depender do uploader.py em cache."""
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    token_path = os.path.join("yt_tokens", f"{ch_id}.pkl")
    with open(token_path, "rb") as f:
        creds = _pickle.load(f)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "wb") as f:
            _pickle.dump(creds, f)

    service = build("youtube", "v3", credentials=creds)

    status_body = {
        "privacyStatus": "private" if publish_at else privacy,
        "madeForKids": False,
        "selfDeclaredMadeForKids": False,
    }
    if publish_at:
        status_body["publishAt"] = publish_at

    body = {
        "snippet": {"title": title[:100], "description": description[:5000],
                    "tags": tags or [], "categoryId": "22"},
        "status": status_body,
    }
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True,
                            chunksize=5*1024*1024)
    request = service.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    vid_id = response.get("id")
    return {"id": vid_id, "url": f"https://youtube.com/shorts/{vid_id}"}

try:
    from core.uploader import load_channels, is_authenticated
    UPLOADER_OK = True
    upload_video = _yt_upload  # sempre usar a versao direta
except ImportError:
    UPLOADER_OK = False
    def load_channels(): return []
    def is_authenticated(x): return False

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="YouTube → Shorts AI",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

/* Esconder UI padrão do Streamlit */
#MainMenu, header[data-testid="stHeader"], footer,
div[data-testid="stToolbar"], div[data-testid="stDecoration"],
div[data-testid="stStatusWidget"] {
    display: none !important; visibility: hidden !important; height: 0 !important;
}
.block-container { padding-top: 1.5rem !important; }

html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
.stApp {
    background: linear-gradient(135deg, #0a0a0f 0%, #0f0f1a 50%, #0a0a0f 100%);
    color: #e8e8f0;
}
.main-title {
    font-size: 2.8rem; font-weight: 700;
    background: linear-gradient(90deg, #ff3cac, #784ba0, #2b86c5);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    text-align: center; margin-bottom: 0.2rem;
}
.sub-title {
    text-align: center; color: #888; font-size: 1rem; margin-bottom: 2rem;
    font-family: 'JetBrains Mono', monospace;
}
.card {
    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 1.5rem; margin-bottom: 1rem;
}
.step-badge {
    display: inline-block;
    background: linear-gradient(90deg, #ff3cac, #784ba0);
    color: white; font-size: 0.75rem; font-weight: 700;
    padding: 3px 12px; border-radius: 20px; margin-bottom: 0.5rem;
    font-family: 'JetBrains Mono', monospace;
}
.segment-card {
    background: rgba(120,75,160,0.15); border: 1px solid rgba(120,75,160,0.3);
    border-radius: 12px; padding: 1rem; margin: 0.5rem 0;
}
.download-card {
    background: rgba(0,200,100,0.08); border: 1px solid rgba(0,200,100,0.25);
    border-radius: 14px; padding: 1.2rem; margin: 0.5rem 0;
    display: flex; align-items: center; gap: 1rem;
}
.stButton > button {
    background: linear-gradient(90deg, #ff3cac, #784ba0, #2b86c5) !important;
    color: white !important; border: none !important; border-radius: 10px !important;
    font-weight: 600 !important; font-size: 1rem !important;
    padding: 0.6rem 2rem !important; width: 100% !important;
}
.stTextInput > div > div > input {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    color: #e8e8f0 !important; border-radius: 10px !important;
}
.stSelectbox > div > div {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.12) !important; border-radius: 10px !important;
}
[data-testid="stSidebar"] {
    background: rgba(0,0,0,0.4) !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}
.success-box {
    background: rgba(0,200,100,0.1); border: 1px solid rgba(0,200,100,0.3);
    border-radius: 12px; padding: 1rem; margin: 1rem 0;
}
.whisper-tip {
    background: rgba(255,180,0,0.08); border: 1px solid rgba(255,180,0,0.25);
    border-radius: 10px; padding: 0.8rem; margin-top: 0.5rem; font-size: 0.85rem;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">🎬 YouTube → Shorts AI</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">download · detectar picos · cortar · legendar · exportar</div>', unsafe_allow_html=True)
st.markdown("---")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configurações")

    # Qualidade
    st.markdown("**📥 Qualidade do Download**")
    quality = st.selectbox(
        "Qualidade",
        ["💎 Máxima (4K)", "🔥 1080p (Recomendado)", "⚡ 720p (Rápido)", "💨 480p (Leve)"],
        index=1,
        label_visibility="collapsed"
    )

    # Resolução
    st.markdown("**📐 Resolução: 1080×1920 (YouTube Shorts)**")
    st.caption("Proporção 9:16 Full HD — padrão oficial do YouTube Shorts")
    resolution = "1080x1920"

    # Corte
    st.markdown("**✂️ Corte**")
    clip_duration = st.slider("Duração do Short (seg)", 15, 60, 45)
    num_clips     = st.slider("Número de clipes", 1, 10, 5)
    skip_intro    = st.slider("⏩ Ignorar início (seg)", 0, 720, 60,
                               help="Evita pegar a intro que todo mundo assiste por obrigação")

    # Efeitos
    st.markdown("**🎨 Efeito Visual**")
    effect = st.selectbox("Efeito", [
        "Nenhum", "Vinheta", "Saturação +", "Contraste Cinematográfico",
        "Brilho + Contraste", "Filtro Vintage", "Filtro Frio", "Filtro Quente",
    ], label_visibility="collapsed")

    st.markdown("**🔀 Anti-Reuso**")
    mirror = st.toggle("Espelhar vídeo (hflip)", value=False,
                       help="Inverte o vídeo horizontalmente para evitar detecção de conteúdo reutilizado")

    st.markdown("**🏷️ Título no Vídeo**")
    show_title = st.toggle("Exibir título no topo", value=True)

    # Legenda
    st.markdown("**💬 Legenda**")
    enable_subtitles = st.toggle("Ativar Legendas", value=True)
    if enable_subtitles:
        subtitle_style    = st.selectbox("Estilo", [
            "Amarela + Borda Preta", "Branca + Borda Preta",
            "Gradiente Rosa/Roxo", "Caixa Transparente",
        ])
        subtitle_position = st.selectbox("Posição", ["Baixo", "Centro", "Cima"])
        words_per_line    = st.slider("Palavras por linha", 1, 5, 2, help="2 a 3 palavras é o ideal para legenda de Shorts")
        font_size         = st.slider("Tamanho da fonte", 20, 120, 69)
        # Diagnóstico Whisper
        try:
            import whisper
            st.success("✅ Whisper instalado")
            whisper_model = st.selectbox(
                "Modelo Whisper",
                ["tiny (mais rápido)", "base (balanceado)", "small (preciso)"],
                index=0,
                help="tiny=30s por clipe | base=1min | small=2min"
            )
        except ImportError:
            st.markdown("""<div class="whisper-tip">
            ⚠️ <b>Whisper não instalado.</b><br>
            No terminal rode:<br>
            <code>pip install openai-whisper</code><br>
            Sem Whisper, usa legenda do YouTube (só funciona se o vídeo tiver legenda ativada).
            </div>""", unsafe_allow_html=True)
            subtitle_style    = st.selectbox("Estilo", ["Branca + Borda Preta", "Amarela + Borda Preta"])
            subtitle_position = st.selectbox("Posição", ["Baixo", "Centro", "Cima"])
            words_per_line    = st.slider("Palavras por linha", 1, 5, 2, help="2 a 3 palavras é o ideal para legenda de Shorts")
            font_size         = st.slider("Tamanho da fonte", 20, 120, 69)
    else:
        subtitle_style, subtitle_position = "Branca + Borda Preta", "Baixo"
        words_per_line, font_size = 2, 69
        mirror = False
        show_title = False
        _video_title = ""
        whisper_model = "tiny (mais rápido)"

    # Áudio
    st.markdown("**🔊 Áudio**")
    audio_boost     = st.slider("Boost do áudio original (dB)", 0, 10, 0)
    original_volume = st.slider("Volume original (%)", 0, 100, 100) / 100.0

    # Música de fundo
    st.markdown("**🎵 Música de Fundo**")
    music_files_uploaded = st.file_uploader(
        "Upload músicas (MP3/WAV/M4A)",
        type=["mp3", "m4a", "wav", "ogg"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    music_volume = st.slider("Volume da música (%)", 0, 80, 15) / 100.0
    if music_files_uploaded:
        st.success(f"✅ {len(music_files_uploaded)} música(s) — sorteio a cada clipe")

    # Logo do canal
    st.markdown("**🖼️ Logo do Canal**")
    logo_file    = st.file_uploader("Upload da logo (PNG/JPG)", type=["png", "jpg", "jpeg"],
                                     label_visibility="collapsed")
    logo_position = st.selectbox("Posição da logo", [
        "Canto superior direito", "Canto superior esquerdo",
        "Canto inferior direito", "Canto inferior esquerdo",
    ])
    logo_size = st.slider("Tamanho da logo (%)", 5, 30, 12)
    if logo_file:
        st.image(logo_file, width=80)

    # Pasta e FFmpeg
    st.markdown("**📁 Pasta de Saída**")
    output_dir = st.text_input("output_dir", value="./output_shorts", label_visibility="collapsed")

    st.markdown("**🔧 Caminho do FFmpeg**")
    st.caption("Cole a pasta onde está o ffmpeg.exe")
    ffmpeg_path = st.text_input("ffmpeg_path", value="", label_visibility="collapsed",
                                 placeholder=r"Ex: C:\ffmpeg\bin")
    if ffmpeg_path:
        exes = glob.glob(os.path.join(ffmpeg_path, "ffmpeg*"))
        if exes:
            st.success("✅ FFmpeg encontrado!")
        else:
            st.error("❌ ffmpeg.exe não está nessa pasta")

# ── Estado de sessão ──────────────────────────────────────────────────────────
if "segments"      not in st.session_state: st.session_state.segments      = []
if "created_files" not in st.session_state: st.session_state.created_files = []
if "processing"    not in st.session_state: st.session_state.processing    = False

# ── Layout principal ──────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 2])

with col1:
    # PASSO 1
    st.markdown('<div class="step-badge">PASSO 1</div>', unsafe_allow_html=True)
    st.markdown("#### 🔗 Cole a URL do YouTube")
    url = st.text_input("url", placeholder="https://www.youtube.com/watch?v=...", label_visibility="collapsed")

    if url:
        with st.spinner("Buscando informações..."):
            info = get_video_info(url)
        if info:
            st.markdown(f"""
            <div class="card">
                <b>📺 {info.get('title','N/A')}</b><br>
                <small>👤 {info.get('uploader','N/A')} &nbsp;|&nbsp;
                ⏱ {info.get('duration_str','N/A')} &nbsp;|&nbsp;
                👁 {info.get('view_count_str','N/A')} views</small>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # PASSO 2
    st.markdown('<div class="step-badge">PASSO 2</div>', unsafe_allow_html=True)
    st.markdown("#### 📊 Detectar Segmentos Mais Assistidos")

    col_a, col_b = st.columns(2)
    with col_a:
        detect_btn = st.button("🔍 Analisar Vídeo", disabled=not url)
    with col_b:
        manual_time = st.text_input("Horário manual (HH:MM:SS)", placeholder="01:25:24", label_visibility="collapsed")

    if detect_btn and url:
        with st.spinner("Analisando heatmap..."):
            segs = find_most_watched_segments(url, num_clips, clip_duration, skip_intro_seconds=skip_intro)
            st.session_state.segments = segs
            st.session_state.selected_clips = list(range(len(segs)))

    if st.session_state.segments:
        st.markdown("**🔥 Segmentos detectados:**")
        if "selected_clips" not in st.session_state:
            st.session_state.selected_clips = list(range(len(st.session_state.segments)))

        # Botões de seleção rápida
        col_sa, col_sn = st.columns(2)
        with col_sa:
            if st.button("✅ Selecionar todos"):
                st.session_state.selected_clips = list(range(len(st.session_state.segments)))
                st.rerun()
        with col_sn:
            if st.button("⬜ Desmarcar todos"):
                st.session_state.selected_clips = []
                st.rerun()

        for i, seg in enumerate(st.session_state.segments):
            col_chk, col_card = st.columns([1, 10])
            with col_chk:
                checked = st.checkbox(
                    f"Clipe {i+1}",
                    value=(i in st.session_state.selected_clips),
                    key=f"clip_chk_{i}",
                    label_visibility="collapsed"
                )
                if checked and i not in st.session_state.selected_clips:
                    st.session_state.selected_clips.append(i)
                elif not checked and i in st.session_state.selected_clips:
                    st.session_state.selected_clips.remove(i)
            with col_card:
                selected_mark = "✅" if i in st.session_state.selected_clips else "⬜"
                st.markdown(f"""<div class="segment-card">
                    <b>Clipe {i+1}</b> &nbsp;|&nbsp;
                    ⏱ <code>{seg['start_str']}</code> → <code>{seg['end_str']}</code> &nbsp;|&nbsp;
                    🔥 Score: <b>{seg['score']:.1f}</b>
                </div>""", unsafe_allow_html=True)

        n_sel = len(st.session_state.selected_clips)
        st.caption(f"**{n_sel} clipe(s) selecionado(s)** de {len(st.session_state.segments)}")
    elif manual_time:
        st.info(f"⏱ Horário manual: **{manual_time}** ({clip_duration}s)")

    st.markdown("---")

    # PASSO 3
    st.markdown('<div class="step-badge">PASSO 3</div>', unsafe_allow_html=True)
    st.markdown("#### 🚀 Gerar Shorts")

    col_test, col_gen = st.columns([1, 2])
    with col_test:
        if st.button("🔧 Testar Conexões"):
            import subprocess as _sp
            _sp.Popen(["streamlit", "run", "test_connection.py", "--server.port", "8503"],
                      cwd=str(Path(__file__).parent))
            st.info("Abrindo em localhost:8503...")
    with col_gen:
        generate_btn = st.button("⚡ Baixar e Gerar Shorts!", disabled=not url)

    if generate_btn and url:
        os.makedirs(output_dir, exist_ok=True)
        st.session_state.created_files = []

        progress_bar = st.progress(0, text="Iniciando...")
        log_area     = st.empty()
        logs = []

        def log(msg):
            logs.append(f"› {msg}")
            log_area.code("\n".join(logs[-12:]), language="bash")

        try:
            _total_start = _time.time()

            def elapsed():
                s = int(_time.time() - _total_start)
                m, sec = s // 60, s % 60
                return f"{m:02d}:{sec:02d}"

            # ── Resolver ffmpeg_exe ──────────────────────────────────────────
            _ffmpeg_exe = None

            # 1. Procurar no caminho informado pelo usuário
            if ffmpeg_path:
                candidates = (
                    glob.glob(os.path.join(ffmpeg_path, "ffmpeg.exe")) +
                    glob.glob(os.path.join(ffmpeg_path, "ffmpeg")) +
                    glob.glob(os.path.join(ffmpeg_path, "**", "ffmpeg.exe"), recursive=True)
                )
                if candidates:
                    _ffmpeg_exe = candidates[0]

            # 2. Tentar imageio-ffmpeg (embutido no pacote)
            if not _ffmpeg_exe:
                try:
                    import imageio_ffmpeg
                    _ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                    log(f"🔧 FFmpeg (imageio): {_ffmpeg_exe}")
                except Exception:
                    pass

            # 3. Fallback: confiar no PATH do sistema
            if not _ffmpeg_exe:
                _ffmpeg_exe = "ffmpeg"
                log("⚠️ FFmpeg não encontrado — usando PATH do sistema")
            else:
                log(f"🔧 FFmpeg: {_ffmpeg_exe}")

            # ── Download ─────────────────────────────────────────────────────
            log("📥 Baixando vídeo do YouTube...")
            progress_bar.progress(10, text="Baixando vídeo...")
            video_path = download_youtube_video(url, output_dir, ffmpeg_dir=ffmpeg_path or "", quality=quality)
            log(f"✅ Vídeo baixado: {Path(video_path).name} [{elapsed()}]")

            # Pegar título do vídeo
            _video_title = ""
            if show_title:
                try:
                    _info = get_video_info(url)
                    raw_title = _info.get("title", "") if _info else ""
                    # Pegar só o nome do canal/programa (antes do primeiro " - " ou "#")
                    if " - " in raw_title:
                        _video_title = raw_title.split(" - ")[0].strip() + " - " + raw_title.split(" - ")[1].split("#")[0].strip()
                    else:
                        _video_title = raw_title.split("#")[0].strip()
                    _video_title = _video_title[:55]
                    log(f"🏷️ Título: {_video_title}")
                except:
                    pass

            # ── Salvar músicas ────────────────────────────────────────────────
            music_paths = []
            if music_files_uploaded:
                music_tmp = os.path.join(output_dir, "_music")
                os.makedirs(music_tmp, exist_ok=True)
                for mf in music_files_uploaded:
                    mp = os.path.join(music_tmp, mf.name)
                    with open(mp, "wb") as f:
                        f.write(mf.read())
                    music_paths.append(mp)
                log(f"🎵 {len(music_paths)} música(s) prontas")

            # ── Salvar logo ───────────────────────────────────────────────────
            logo_path = None
            if logo_file:
                logo_tmp = os.path.join(output_dir, "_logo")
                os.makedirs(logo_tmp, exist_ok=True)
                logo_path = os.path.join(logo_tmp, logo_file.name)
                with open(logo_path, "wb") as f:
                    f.write(logo_file.read())
                log(f"🖼️ Logo salva: {logo_file.name}")

            # ── Segmentos ─────────────────────────────────────────────────────
            # Usar apenas os clipes selecionados
            all_segs = st.session_state.segments
            selected_idxs = st.session_state.get("selected_clips", list(range(len(all_segs))))
            segments_to_process = [all_segs[i] for i in sorted(selected_idxs) if i < len(all_segs)]

            if not segments_to_process and all_segs:
                st.warning("Nenhum clipe selecionado! Usando todos.")
                segments_to_process = all_segs

            if not segments_to_process:
                if manual_time:
                    from core.analyzer import time_str_to_seconds, seconds_to_str
                    start_sec = time_str_to_seconds(manual_time)
                    segments_to_process = [{
                        "start": start_sec, "end": start_sec + clip_duration,
                        "start_str": manual_time, "end_str": seconds_to_str(start_sec + clip_duration),
                        "score": 100.0,
                    }]
                else:
                    segments_to_process = [{"start": 0, "end": clip_duration,
                                            "start_str": "00:00:00", "end_str": "", "score": 100.0}]

            # ── Resolução ────────────────────────────────────────────────────
            w, h = (1080, 1920) if "1080" in resolution else (720, 1280) if "720" in resolution else (540, 960)

            # ── Processar clipes ──────────────────────────────────────────────
            created = []
            for i, seg in enumerate(segments_to_process):
                pct = 20 + int(70 * (i / len(segments_to_process)))
                progress_bar.progress(pct, text=f"Processando clipe {i+1}/{len(segments_to_process)}...")
                log(f"✂️ Clipe {i+1}: {seg['start_str']} ... [{elapsed()}]")

                out_path = os.path.join(os.path.abspath(output_dir), f"short_{i+1:02d}.mp4")
                create_short(
                    video_path=video_path,
                    start=seg["start"],
                    end=seg["end"],
                    output_path=out_path,
                    width=w, height=h,
                    effect=effect,
                    enable_subtitles=enable_subtitles,
                    subtitle_style=subtitle_style,
                    subtitle_position=subtitle_position,
                    words_per_line=words_per_line,
                    font_size=font_size,
                    audio_boost=audio_boost,
                    ffmpeg_exe=_ffmpeg_exe,
                    whisper_model=whisper_model.split(" ")[0],
                    music_files=music_paths or None,
                    music_volume=music_volume,
                    original_volume=original_volume,
                    url=url,
                    logo_path=logo_path,
                    logo_position=logo_position,
                    logo_size_pct=logo_size,
                    video_title=_video_title,
                    mirror=mirror,
                )
                created.append(out_path)
                log(f"✅ Clipe {i+1} pronto! [{elapsed()}]")

            # Guardar na session_state para persistir após download
            st.session_state.created_files = created
            st.session_state.total_seconds = int(_time.time() - _total_start)
            progress_bar.progress(100, text="✅ Concluído!")
            log(f"🎉 {len(created)} short(s) em: {os.path.abspath(output_dir)}")
            log(f"⏱️ Tempo total: {elapsed()}")

        except Exception as e:
            st.error(f"❌ Erro: {str(e)}")
            log(f"ERRO: {str(e)}")

    # ── Área de downloads — FORA do bloco generate_btn para persistir ────────
    if st.session_state.created_files:
        _total_secs = st.session_state.get("total_seconds", 0)
        _mm, _ss = _total_secs // 60, _total_secs % 60
        st.markdown(f"""<div class="success-box">
            <b>🎉 {len(st.session_state.created_files)} Short(s) prontos!</b><br>
            Pasta: <code>{os.path.abspath(output_dir)}</code><br>
            ⏱️ Tempo total: <b>{_mm:02d}:{_ss:02d}</b>
        </div>""", unsafe_allow_html=True)

        st.markdown("#### ⬇️ Downloads")
        for fpath in st.session_state.created_files:
            if os.path.exists(fpath):
                size_mb = os.path.getsize(fpath) / 1_048_576
                col_d1, col_d2 = st.columns([3, 1])
                with col_d1:
                    st.markdown(f"**{Path(fpath).name}** — {size_mb:.1f} MB")
                with col_d2:
                    with open(fpath, "rb") as f:
                        st.download_button(
                            label="⬇️ Baixar",
                            data=f.read(),          # <-- read() completo evita refresh
                            file_name=Path(fpath).name,
                            mime="video/mp4",
                            key=f"dl_{Path(fpath).name}",   # key única evita conflito
                        )

        if st.button("🗑️ Limpar lista"):
            st.session_state.created_files = []
            st.rerun()

        # ── Upload automático para os canais ──────────────────────────────
        if UPLOADER_OK:
            channels = load_channels()
            authed_channels = [c for c in channels if is_authenticated(c["id"])]

            if authed_channels and st.session_state.created_files:
                st.markdown("---")
                st.markdown("#### 📡 Publicar nos Canais")

                col_up1, col_up2 = st.columns(2)
                with col_up1:
                    upload_title = st.text_input(
                        "Título do Short",
                        value=st.session_state.get("last_video_title", "Short Viral"),
                        key="upload_title"
                    )
                with col_up2:
                    privacy_opt = st.selectbox("Privacidade", ["public", "unlisted", "private"])

                upload_desc = st.text_area(
                    "Descrição",
                    value="#shorts #viral #podcast",
                    height=80,
                    key="upload_desc"
                )

                # Agendamento
                st.markdown("**📅 Agendamento**")
                schedule_enabled = st.toggle("Agendar publicação", value=False)
                publish_at_iso = ""
                if schedule_enabled:
                    import datetime, pytz
                    col_d, col_t, col_tz = st.columns(3)
                    with col_d:
                        sched_date = st.date_input(
                            "Data",
                            value=datetime.date.today() + datetime.timedelta(days=1)
                        )
                    with col_t:
                        sched_time = st.time_input(
                            "Horário",
                            value=datetime.time(9, 0)
                        )
                    with col_tz:
                        tz_name = st.selectbox("Fuso", [
                            "America/Sao_Paulo",
                            "America/New_York",
                            "Europe/London",
                            "UTC",
                        ])

                    tz = pytz.timezone(tz_name)
                    dt_local = datetime.datetime.combine(sched_date, sched_time)
                    dt_utc   = tz.localize(dt_local).astimezone(pytz.utc)
                    publish_at_iso = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                    st.info(f"📅 Será publicado em: **{dt_local.strftime('%d/%m/%Y às %H:%M')}** ({tz_name})")

                # Distribuição com intervalo entre canais
                if schedule_enabled and len(selected_channels) > 1:
                    same_time = st.toggle(
                        "Publicar todos no mesmo horário", value=False,
                        help="Todos os canais publicam exatamente no mesmo horário"
                    )
                    if same_time:
                        interval_h = 0
                        st.success("✅ Todos os canais publicarão simultaneamente")
                    else:
                        interval_h = st.slider(
                            "⏱️ Intervalo entre canais (horas)", 1, 24, 2,
                            help="Canal A às 09h, Canal B às 11h, Canal C às 13h..."
                        )
                else:
                    interval_h = 0
                    same_time = True

                st.markdown("**Selecione os canais para publicar:**")
                selected_channels = []
                ch_cols = st.columns(min(len(authed_channels), 5))
                for idx, ch in enumerate(authed_channels):
                    with ch_cols[idx]:
                        if st.checkbox(ch["name"], value=True, key=f"ch_sel_{ch['id']}"):
                            selected_channels.append(ch)

                # Distribuição: cada canal recebe um short diferente
                if selected_channels:
                    n_clips = len(st.session_state.created_files)
                    n_ch    = len(selected_channels)
                    st.caption(
                        f"📋 {n_clips} short(s) serão distribuídos entre {n_ch} canal(is) "
                        f"— cada canal recebe 1 short em sequência"
                    )

                if st.button("🚀 Publicar nos Canais Selecionados!", disabled=not selected_channels):
                    upload_log = st.empty()
                    upload_logs = []

                    def ulog(msg):
                        upload_logs.append(f"› {msg}")
                        upload_log.code("\n".join(upload_logs[-8:]), language="bash")

                    results = []
                    for i, ch in enumerate(selected_channels):
                        # Distribuir shorts: canal 0 → short 0, canal 1 → short 1...
                        video_idx = i % len(st.session_state.created_files)
                        fpath = st.session_state.created_files[video_idx]
                        secrets = ch.get("secrets_path", "")

                        if not secrets or not os.path.exists(secrets):
                            ulog(f"❌ {ch['name']}: client_secrets.json não encontrado")
                            continue

                        ulog(f"📤 Enviando Short {video_idx+1} → {ch['name']}...")
                        try:
                            # Calcular horário escalonado por canal
                            if schedule_enabled and publish_at_iso:
                                import datetime
                                base_dt  = datetime.datetime.strptime(publish_at_iso, "%Y-%m-%dT%H:%M:%SZ")
                                sched_dt = base_dt + datetime.timedelta(hours=i * interval_h)
                                ch_publish_at = sched_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                                ulog(f"📅 {ch['name']}: agendado para {sched_dt.strftime('%d/%m %H:%M')} UTC")
                            else:
                                ch_publish_at = ""

                            result = _yt_upload(
                                ch_id=ch["id"],
                                secrets_path=secrets,
                                video_path=fpath,
                                title=upload_title,
                                description=upload_desc,
                                tags=["shorts", "viral", "podcast"],
                                privacy=privacy_opt,
                                publish_at=ch_publish_at,
                            )
                            ulog(f"✅ {ch['name']}: {result['url']}")
                            results.append((ch["name"], result["url"]))
                        except Exception as e:
                            ulog(f"❌ {ch['name']}: {str(e)[:80]}")

                    if results:
                        st.markdown("**✅ Publicados com sucesso:**")
                        for name, url in results:
                            st.markdown(f"- **{name}**: [{url}]({url})")

with col2:
    st.markdown("### 📖 Como usar")
    st.markdown("""<div class="card">
    <b>1.</b> Cole a URL do YouTube<br><br>
    <b>2.</b> Clique em <i>Analisar</i> para detectar os melhores momentos<br><br>
    <b>3.</b> Configure na barra lateral:<br>
    &nbsp;&nbsp;• Qualidade do download<br>
    &nbsp;&nbsp;• Efeito visual<br>
    &nbsp;&nbsp;• Legenda (Whisper ou YouTube)<br>
    &nbsp;&nbsp;• Música de fundo (upload MP3)<br>
    &nbsp;&nbsp;• Logo do canal (PNG/JPG)<br><br>
    <b>4.</b> Clique em <i>Gerar Shorts!</i> 🚀
    </div>""", unsafe_allow_html=True)

    st.markdown("### 💬 Instalar Legendas (Whisper)")
    st.markdown("""<div class="card">
    No terminal (uma vez só):<br>
    <code>pip install openai-whisper</code><br><br>
    Depois reinicie o Streamlit.<br>
    O status aparece na sidebar em tempo real.
    </div>""", unsafe_allow_html=True)

    st.markdown("### 🛠️ Tecnologias")
    st.markdown("""<div class="card">
    <code>yt-dlp</code> — Download<br>
    <code>FFmpeg</code> — Corte e efeitos<br>
    <code>Whisper</code> — Legendas automáticas<br>
    <code>Streamlit</code> — Interface
    </div>""", unsafe_allow_html=True)
