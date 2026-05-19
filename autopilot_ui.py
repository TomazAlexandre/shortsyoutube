"""
autopilot_ui.py v3
- Log via arquivo (resolve problema de thread + session_state)
- Opção de agendar para múltiplos dias
"""
import sys, os
from pathlib import Path
APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

import importlib.util, datetime, threading, time

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

autopilot = _load("autopilot", APP_DIR / "autopilot.py")

import streamlit as st
import json as _json

st.set_page_config(page_title="🤖 Autopiloto", page_icon="🤖", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400&display=swap');
#MainMenu,header,footer,div[data-testid="stToolbar"]{display:none!important}
.block-container{padding-top:1.2rem!important}
html,body,[class*="css"]{font-family:'Space Grotesk',sans-serif}
.stApp{background:linear-gradient(135deg,#0a0a0f,#0f0f1a);color:#e8e8f0}
.stButton>button{background:linear-gradient(90deg,#ff3cac,#784ba0,#2b86c5)!important;color:white!important;border:none!important;border-radius:10px!important;font-weight:600!important;width:100%!important}
.phase{background:rgba(120,75,160,0.15);border-left:3px solid #784ba0;padding:0.6rem 1rem;border-radius:0 8px 8px 0;margin:0.3rem 0;font-size:0.85rem}
.result-card{background:rgba(0,200,100,0.08);border:1px solid rgba(0,200,100,0.25);border-radius:12px;padding:1rem;margin:0.4rem 0}
.status-on{background:rgba(0,200,100,0.1);border:1px solid rgba(0,200,100,0.3);border-radius:10px;padding:0.8rem;text-align:center}
.status-off{background:rgba(255,60,60,0.08);border:1px solid rgba(255,60,60,0.2);border-radius:10px;padding:0.8rem;text-align:center}
</style>
""", unsafe_allow_html=True)

# ── Log via arquivo (thread-safe) ─────────────────────────────────────────────
LOG_FILE = str(APP_DIR / "autopilot_run.log")

def write_log(msg: str):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def read_log(last_n: int = 40) -> str:
    if not os.path.exists(LOG_FILE):
        return "Aguardando início..."
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return "".join(lines[-last_n:])

def clear_log():
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("")

# ── Estado ────────────────────────────────────────────────────────────────────
RUNNING_FILE = str(APP_DIR / "autopilot_running.flag")
RESULTS_FILE = str(APP_DIR / "autopilot_results.json")

def is_running() -> bool:
    return os.path.exists(RUNNING_FILE)

def set_running(val: bool):
    if val:
        with open(RUNNING_FILE, "w") as f: f.write("1")
    elif os.path.exists(RUNNING_FILE):
        os.remove(RUNNING_FILE)

def save_results(r: dict):
    import json
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)

def load_results() -> dict:
    import json
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

cfg = autopilot.load_config()

# ── Estado do agendador autônomo ──────────────────────────────────────────────
import json as _json
_sched_file  = str(APP_DIR / "scheduler_state.json")
_sched_state = {}
if os.path.exists(_sched_file):
    try:
        with open(_sched_file, "r", encoding="utf-8") as _f:
            _sched_state = _json.load(_f)
    except: pass
_auto_enabled = _sched_state.get("enabled", False)
_auto_time    = _sched_state.get("run_time", "08:00")
_last_runs    = _sched_state.get("last_runs", {})

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 🤖 Autopiloto — Geração e Publicação Automática")

col_s, col_b1, col_b2, col_b3 = st.columns([3, 1, 1, 1])
with col_s:
    if is_running():
        st.markdown('<div class="status-on">⚙️ <b>PROCESSANDO...</b> — Atualize o log para ver o progresso</div>', unsafe_allow_html=True)
    elif _auto_enabled:
        st.markdown(f'<div class="status-on">🤖 <b>AUTÔNOMO ATIVO</b> — Roda todos os nichos às <b>{_auto_time}</b></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-off">⏸️ <b>AGUARDANDO</b> — Clique em RODAR AGORA para iniciar</div>', unsafe_allow_html=True)
with col_b1:
    run_now = st.button("▶️ Rodar agora", key="btn_auto_1")
with col_b2:
    run_all = st.button("🌐 Todos nichos", key="btn_auto_2")
with col_b3:
    if st.button("🔄 Atualizar", key="btn_refresh_log"):
        st.rerun()

st.markdown("---")

# Pipeline visual
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown('<div class="phase"><b>FASE 1 — Busca</b><br>🔍 Podcasts em alta<br>📊 Análise Heatmap<br>🎯 Melhores momentos</div>', unsafe_allow_html=True)
with c2:
    st.markdown('<div class="phase"><b>FASE 2 — Processamento</b><br>📥 Download<br>✂️ Corte + legenda + efeitos<br>🤖 ChatGPT título/desc</div>', unsafe_allow_html=True)
with c3:
    st.markdown('<div class="phase"><b>FASE 3 — Agendamento</b><br>📤 Upload para canais<br>📅 Agenda por dias<br>🕐 Horários configurados</div>', unsafe_allow_html=True)

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs(["⚙️ Geral", "🎬 Vídeo", "📅 Publicação", "🤖 ChatGPT", "📡 Canais", "🧪 Teste Rápido", "📋 Log", "✅ Resultados", "📊 Acompanhamento", "⏳ Fila", "📈 Estatísticas"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🤖 Modo Autônomo**")
        _auto_toggle = st.toggle(
            "Ativar modo autônomo (roda todos os dias automaticamente)",
            value=_auto_enabled,
            key="auto_toggle"
        )
        _auto_time_input = st.time_input(
            "Horário de execução diária",
            value=datetime.time(*map(int, _auto_time.split(":"))),
            key="auto_time_input"
        )
        if _auto_toggle != _auto_enabled or _auto_time_input.strftime("%H:%M") != _auto_time:
            _new_state = dict(_sched_state)
            _new_state["enabled"]  = _auto_toggle
            _new_state["run_time"] = _auto_time_input.strftime("%H:%M")
            with open(_sched_file, "w", encoding="utf-8") as _f:
                _json.dump(_new_state, _f, ensure_ascii=False, indent=2)
            st.rerun()

        if _auto_toggle:
            # Mostrar nichos ativos
            try:
                _active = autopilot.get_active_niches()
                st.success(f"✅ {len(_active)} nicho(s) ativo(s): {', '.join(_active)}")
                st.caption("Executa um nicho por vez, respeitando o histórico do dia.")
            except:
                pass
        else:
            st.info("🖱️ Modo manual — clique em Rodar agora")

    st.markdown("**🎯 Nicho do Canal**")

    # Carregar nichos dinamicamente do channel_groups.json + fixos
    _ALL_NICHES = {
        "geral":           "🎙️ Geral",
        "politica":        "🏛️ Política",
        "policia_relatos": "🚔 Polícia & Relatos",
        "futebol":         "⚽ Futebol",
        "games":           "🎮 Games",
        "humor":           "😂 Humor",
        "financas":        "💰 Finanças",
        "saude":           "❤️ Saúde & Bem-estar",
        "tecnologia":      "💻 Tecnologia",
        "esportes":        "🏆 Esportes",
        "negocios":        "💼 Negócios",
        "educacao":        "📚 Educação",
        "outros":          "📦 Outros",
    }
    # Adicionar nichos do channel_groups.json que não estejam na lista
    _gf = APP_DIR / "channel_groups.json"
    if _gf.exists():
        import json as _j
        _groups = _j.loads(_gf.read_text(encoding="utf-8"))
        for _n in _groups:
            if _n not in _ALL_NICHES:
                _ALL_NICHES[_n] = f"📦 {_n.title()}"

    # Mostrar só nichos que têm canais configurados (+ geral sempre)
    _available = {k: v for k, v in _ALL_NICHES.items()
                  if k == "geral" or (_gf.exists() and k in _j.loads(_gf.read_text(encoding="utf-8")))}

    niche_key = st.selectbox(
        "Selecione o nicho",
        options=list(_available.keys()),
        format_func=lambda x: _available[x],
        index=list(_available.keys()).index(cfg.get("niche","geral"))
              if cfg.get("niche","geral") in _available else 0,
        label_visibility="collapsed",
    )
    cfg["niche"] = niche_key

    # Mostrar canais do nicho selecionado
    if _gf.exists():
        _chs = _j.loads(_gf.read_text(encoding="utf-8")).get(niche_key, [])
        _auth = [c for c in _chs if os.path.exists(str(APP_DIR / "yt_tokens" / f"{c['id']}.pkl"))]
        st.caption(f"✅ {len(_auth)}/{len(_chs)} canal(is) conectado(s) neste nicho")
    else:
        st.caption("Só busca podcasts brasileiros. Conteúdo estrangeiro é ignorado automaticamente.")
    cfg["max_podcasts_per_day"] = st.slider("Podcasts por execução", 1, 10, cfg.get("max_podcasts_per_day", 4))
    cfg["min_views"] = st.number_input(
        "👁️ Views mínimas do podcast",
        min_value=0, max_value=10_000_000,
        value=cfg.get("min_views", 500_000),
        step=100_000,
        help="Ignora podcasts com menos views que esse valor"
    )
    cfg["clips_per_podcast"]    = st.slider("Cortes por podcast", 1, 10, cfg.get("clips_per_podcast", 5),
        help="5 cortes = 1 para cada canal")
    with col2:
        cfg["ffmpeg_path"]  = st.text_input("Pasta do ffmpeg.exe", value=cfg.get("ffmpeg_path",""), placeholder=r"C:\ffmpeg\bin")
        cfg["music_folder"] = st.text_input("Pasta das músicas", value=cfg.get("music_folder", str(APP_DIR/"musicas")))
        musics = autopilot.get_music_files(cfg["music_folder"])
        if musics:
            st.success(f"🎵 {len(musics)} música(s)")
            for m in musics: st.caption(f"• {Path(m).name}")
        else:
            st.warning("Nenhuma música. Adicione MP3s na pasta.")
            if st.button("📁 Criar pasta /musicas", key="btn_auto_3"):
                os.makedirs(cfg["music_folder"], exist_ok=True)
                st.rerun()

with tab2:
    col1, col2 = st.columns(2)
    with col1:
        cfg["clip_duration"]  = st.slider("Duração do Short (seg)", 30, 60, cfg.get("clip_duration", 60))
        cfg["skip_intro"]     = st.slider("Ignorar início (seg)", 0, 1800, cfg.get("skip_intro", 720), step=60,
            help="720 = ignorar 12min (intro/patrocínio). Valor em segundos.")
        cfg["font_size"]      = st.slider("Tamanho da fonte", 20, 120, cfg.get("font_size", 69))
        cfg["words_per_line"] = st.slider("Palavras por linha", 1, 5, cfg.get("words_per_line", 2))
    with col2:
        cfg["enable_subtitles"] = st.toggle("Legendas automáticas", value=cfg.get("enable_subtitles", True))
        st.caption("Estilo sorteado aleatoriamente: Amarela / Branca / Rosa")
        cfg["whisper_model"] = st.selectbox("Modelo Whisper", ["tiny","base","small"],
                               index=["tiny","base","small"].index(cfg.get("whisper_model","tiny")))
        cfg["mirror"] = st.toggle("Espelhar vídeo (anti-reuso)", value=cfg.get("mirror", True))
        cfg["use_broll"] = st.toggle("🎬 B-Roll automático por palavra-chave", value=cfg.get("use_broll", False))
        if cfg["use_broll"]:
            default_broll = str(APP_DIR / "broll_images")
            cfg["broll_dir"] = st.text_input("Pasta B-Roll", value=cfg.get("broll_dir", default_broll), label_visibility="collapsed")
            if os.path.isdir(cfg["broll_dir"]):
                cats = [d for d in os.listdir(cfg["broll_dir"]) if os.path.isdir(os.path.join(cfg["broll_dir"], d))]
                st.caption(f"✅ {len(cats)} categoria(s) encontrada(s)")
            else:
                st.warning("⚠️ Pasta não encontrada — extraia o broll_images.zip")
        else:
            cfg["broll_dir"] = ""
        cfg["use_dynamic_zoom"] = st.toggle("🔍 Zoom dinâmico (simulação de speaker)", value=cfg.get("use_dynamic_zoom", False))

with tab3:
    st.markdown("### 📅 Agendamento de Publicação")

    cfg["publish_privacy"] = st.selectbox("Privacidade", ["public","unlisted","private"])

    st.markdown("**Selecione o período:**")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_date = st.date_input(
            "📅 Data inicial",
            value=datetime.date.today(),
            min_value=datetime.date.today(),
            key="start_date_picker"
        )
    with col_d2:
        end_date = st.date_input(
            "📅 Data final",
            value=datetime.date.today() + datetime.timedelta(days=2),
            min_value=datetime.date.today(),
            key="end_date_picker"
        )

    if end_date < start_date:
        st.error("Data final deve ser maior que a inicial!")
        end_date = start_date

    total_days = (end_date - start_date).days + 1
    days_ahead = (start_date - datetime.date.today()).days
    cfg["start_date"] = start_date.isoformat()
    cfg["end_date"]   = end_date.isoformat()
    cfg["total_days"] = total_days
    cfg["days_ahead"] = days_ahead

    st.success(f"📆 **{total_days} dia(s)** — {start_date.strftime('%d/%m/%Y')} até {end_date.strftime('%d/%m/%Y')}")

    st.markdown("**Horários por dia:**")
    schedules_saved = cfg.get("publish_schedules", ["12:00","15:00","18:00","21:30"])
    n_slots = st.slider("Qtd de horários por dia", 1, 8, len(schedules_saved))
    new_schedules = []
    slot_cols = st.columns(min(n_slots, 4))
    for i in range(n_slots):
        with slot_cols[i % 4]:
            default_t = schedules_saved[i] if i < len(schedules_saved) else "12:00"
            h, m = map(int, default_t.split(":"))
            t = st.time_input(f"Slot {i+1}", value=datetime.time(h, m), key=f"slot_{i}")
            new_schedules.append(t.strftime("%H:%M"))
    cfg["publish_schedules"] = new_schedules

    st.markdown("**📋 Calendário:**")
    for day_i in range(total_days):
        pub_date = start_date + datetime.timedelta(days=day_i)
        slots_str = " | ".join([f"🕐 {s} → 5 canais" for s in new_schedules])
        st.caption(f"📅 **{pub_date.strftime('%d/%m/%Y')}** — {slots_str}")

    st.markdown("---")
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Dias", total_days)
    col_m2.metric("Shorts/dia", n_slots * 5)
    col_m3.metric("Total de shorts", n_slots * 5 * total_days)
    st.warning("⚠️ Cota YouTube API: ~6 uploads/dia. Solicite aumento em console.cloud.google.com")

with tab4:
    cfg["openai_key"] = st.text_input("Chave API OpenAI", value=cfg.get("openai_key",""),
                                       type="password", placeholder="sk-...")
    cfg["description_template"] = st.text_area("Instruções extras para o ChatGPT",
        value=cfg.get("description_template",""),
        placeholder="Ex: Sempre mencione que é um corte do Flow Podcast. Use emojis de fogo.",
        height=80)

    if cfg["openai_key"]:
        col_t1, col_t2 = st.columns(2)
        with col_t1: tg = st.text_input("Convidado teste", value="GAULES")
        with col_t2: tp = st.text_input("Podcast teste",   value="Flow Podcast")
        if st.button("🧪 Testar", key="btn_auto_4"):
            with st.spinner("Gerando..."):
                r = autopilot.generate_content(f"{tg} - {tp}", tp, cfg["openai_key"], cfg.get("description_template",""))
            st.success(f"**Título:** {r['title']}")
            st.info(f"**Hook:** {r['hook']}")
            st.text_area("Descrição:", r["description"], height=80)
            st.text_area("Hashtags:",  r["hashtags"],    height=60)
    else:
        st.info("Sem chave OpenAI: usará título/descrição padrão.")

with tab5:
    st.markdown("### 📡 Gerenciar Canais por Nicho")
    st.caption("Conecte até 5 canais por nicho. Ao selecionar um nicho no Autopiloto, ele publica nesses canais.")

    NICHE_OPTIONS = {
        "geral": "🎙️ Geral", "politica": "🏛️ Política",
        "policia_relatos": "🚔 Polícia & Relatos", "futebol": "⚽ Futebol",
        "games": "🎮 Games", "humor": "😂 Humor", "financas": "💰 Finanças",
        "saude": "❤️ Saúde", "tecnologia": "💻 Tecnologia",
        "esportes": "🏆 Esportes", "negocios": "💼 Negócios",
        "educacao": "📚 Educação", "outros": "📦 Outros",
    }

    import json as _jch, pickle as _pkl

    GROUPS_FILE = str(APP_DIR / "channel_groups.json")
    TOKENS_DIR  = str(APP_DIR / "yt_tokens")
    LOGOS_DIR   = str(APP_DIR / "channel_logos")

    def _load_groups():
        if os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, "r", encoding="utf-8") as f:
                return _jch.load(f)
        return {}

    def _save_groups(g):
        with open(GROUPS_FILE, "w", encoding="utf-8") as f:
            _jch.dump(g, f, ensure_ascii=False, indent=2)

    def _is_auth(ch_id):
        return os.path.exists(os.path.join(TOKENS_DIR, f"{ch_id}.pkl"))

    def _connect(ch_id, secrets_path):
        _up_src = (APP_DIR / "core" / "uploader.py").read_text(encoding="utf-8")
        _up_ns  = {"__file__": str(APP_DIR / "core" / "uploader.py")}
        exec(compile(_up_src, str(APP_DIR / "core" / "uploader.py"), "exec"), _up_ns)
        return _up_ns["get_channel_info"](ch_id, secrets_path)

    _groups = _load_groups()
    secrets_default = str(APP_DIR / "client_secrets.json")

    col_sel, col_add = st.columns([3,1])
    with col_sel:
        _sel_niche = st.selectbox(
            "Selecionar grupo",
            options=list(NICHE_OPTIONS.keys()),
            format_func=lambda x: NICHE_OPTIONS[x],
            key="ch_niche_sel"
        )
    with col_add:
        st.markdown("<br>", unsafe_allow_html=True)
        if _sel_niche not in _groups:
            if st.button("➕ Criar grupo", key="btn_create_group"):
                _groups[_sel_niche] = []
                _save_groups(_groups)
                st.rerun()

    st.markdown("---")

    if _sel_niche not in _groups:
        st.info(f"Grupo **{NICHE_OPTIONS[_sel_niche]}** não existe. Clique em **➕ Criar grupo**.")
    else:
        _chs = _groups[_sel_niche]
        st.markdown(f"#### {NICHE_OPTIONS[_sel_niche]} — {len(_chs)}/5 canais")

        for _i, _ch in enumerate(_chs):
            _authed = _is_auth(_ch["id"])
            _badge  = "✅ Conectado" if _authed else "❌ Não conectado"
            with st.expander(f"{_ch['name']} — {_badge}", expanded=not _authed):
                c1, c2, c3 = st.columns([2,2,1])
                with c1:
                    _lu = st.file_uploader("Logo", type=["png","jpg","jpeg"], key=f"lu_{_sel_niche}_{_i}")
                    if _lu:
                        os.makedirs(LOGOS_DIR, exist_ok=True)
                        _lp = os.path.join(LOGOS_DIR, f"{_ch['id']}_{_lu.name}")
                        with open(_lp, "wb") as f: f.write(_lu.read())
                        _chs[_i]["logo_path"] = _lp
                        _save_groups(_groups)
                        st.success("Logo salva!")
                    if _ch.get("logo_path") and os.path.exists(_ch.get("logo_path","")):
                        st.image(_ch["logo_path"], width=70)
                with c2:
                    _sp = st.text_input("client_secrets.json",
                        value=_ch.get("secrets_path", secrets_default),
                        key=f"sp_{_sel_niche}_{_i}")
                    if _sp != _ch.get("secrets_path",""):
                        _chs[_i]["secrets_path"] = _sp
                        _save_groups(_groups)
                    if _ch.get("youtube_name"):
                        st.caption(f"YouTube: {_ch['youtube_name']}")
                    if not _authed:
                        if st.button("🔐 Conectar", key=f"conn_{_sel_niche}_{_i}"):
                            _sp_v = _chs[_i].get("secrets_path", _sp)
                            if not os.path.exists(_sp_v):
                                st.error("client_secrets.json não encontrado!")
                            else:
                                try:
                                    with st.spinner("Abrindo browser..."):
                                        _info = _connect(_ch["id"], _sp_v)
                                        _chs[_i].update({"authenticated": True, "secrets_path": _sp_v, **_info})
                                        _save_groups(_groups)
                                    st.success(f"✅ {_info.get('youtube_name','')}")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro: {e}")
                    else:
                        if st.button("🔄 Reconectar", key=f"rec_{_sel_niche}_{_i}"):
                            _tp = os.path.join(TOKENS_DIR, f"{_ch['id']}.pkl")
                            if os.path.exists(_tp): os.remove(_tp)
                            _chs[_i]["authenticated"] = False
                            _save_groups(_groups)
                            st.rerun()
                with c3:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if st.button("🗑️", key=f"del_{_sel_niche}_{_i}"):
                        _chs.pop(_i)
                        _save_groups(_groups)
                        st.rerun()

        if len(_chs) < 5:
            st.markdown("---")
            with st.form(f"add_ch_{_sel_niche}"):
                _new_name = st.text_input("Nome do canal", placeholder=f"Ex: {NICHE_OPTIONS[_sel_niche]} Cortes A")
                if st.form_submit_button("➕ Adicionar canal"):
                    if _new_name:
                        import time as _t
                        _new_id = f"{_sel_niche}_ch{len(_chs)+1}_{int(_t.time())%9999}"
                        _chs.append({
                            "id": _new_id, "name": _new_name.strip(),
                            "logo_path": "", "authenticated": False,
                            "secrets_path": secrets_default, "niche": _sel_niche,
                        })
                        _save_groups(_groups)
                        st.success(f"Canal '{_new_name}' adicionado!")
                        st.rerun()
        else:
            st.warning("Limite de 5 canais por grupo.")

        st.markdown("---")
        st.markdown("**Visão geral:**")
        _overview_cols = st.columns(min(len(_groups), 4))
        for _idx, (_n, _cs) in enumerate(_groups.items()):
            with _overview_cols[_idx % 4]:
                _auth_c = sum(1 for c in _cs if _is_auth(c["id"]))
                st.markdown(f"**{NICHE_OPTIONS.get(_n,_n)}**")
                st.caption(f"{_auth_c}/{len(_cs)} conectado(s)")


with tab6:
    st.markdown("### 🧪 Teste Rápido — 1 Vídeo")
    st.caption("Processa apenas 1 podcast com 1 clipe para testar configurações rapidamente.")
    st.markdown("---")

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        test_url = st.text_input("URL do YouTube", placeholder="https://www.youtube.com/watch?v=...")
        test_start = st.text_input("Início do clipe (HH:MM:SS)", value="00:01:00")
        test_duration = st.slider("Duração (seg)", 15, 60, 45)
    with col_t2:
        test_subtitle = st.toggle("Legenda", value=True)
        test_broll    = st.toggle("B-Roll", value=cfg.get("use_broll", False))
        test_zoom     = st.toggle("Zoom dinâmico", value=False)
        test_upload   = st.toggle("Fazer upload após gerar", value=False)
        if test_upload:
            test_channel = st.selectbox(
                "Canal para upload",
                options=[c["name"] for c in channels] if channels else ["Nenhum canal"],
            )

    test_log_file  = str(APP_DIR / "test_run.log")
    test_flag_file = str(APP_DIR / "test_run.flag")

    def is_test_running():
        return os.path.exists(test_flag_file)

    col_tb1, col_tb2 = st.columns([2,1])
    with col_tb1:
        run_test = st.button("▶️ Testar agora!", disabled=is_test_running() or not test_url)
    with col_tb2:
        if st.button("🔄 Atualizar", key="btn_auto_5"):
            st.rerun()

    # Log do teste
    if os.path.exists(test_log_file):
        with open(test_log_file, "r", encoding="utf-8") as f:
            test_log_content = f.read()
        st.code(test_log_content or "Aguardando...", language="bash")
    else:
        st.info("Clique em **▶️ Testar agora!** para começar.")

    if run_test and test_url and not is_test_running():
        autopilot.save_config(cfg)
        open(test_flag_file, "w").close()
        open(test_log_file, "w").close()

        import glob as _glob_t

        def _write_test(msg):
            with open(test_log_file, "a", encoding="utf-8") as f:
                f.write(msg + "\n")

        def _run_test():
            try:
                _write_test("🧪 TESTE RÁPIDO INICIADO")
                _write_test("=" * 40)

                # Resolver ffmpeg
                ffmpeg_exe = "ffmpeg"
                fp = cfg.get("ffmpeg_path", "")
                if fp and os.path.isdir(fp):
                    cands = _glob_t.glob(os.path.join(fp, "ffmpeg.exe")) + _glob_t.glob(os.path.join(fp, "ffmpeg"))
                    if cands: ffmpeg_exe = cands[0]
                if not os.path.isfile(ffmpeg_exe):
                    try:
                        import imageio_ffmpeg
                        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                    except: pass
                _write_test(f"🔧 FFmpeg: {os.path.basename(ffmpeg_exe)}")

                # Carregar módulos
                import importlib.util as _ilu
                def _lmod(name):
                    spec = _ilu.spec_from_file_location(name, APP_DIR / "core" / f"{name}.py")
                    mod  = _ilu.module_from_spec(spec); spec.loader.exec_module(mod)
                    return mod
                dl = _lmod("downloader")
                ed = _lmod("editor")

                # Download
                _write_test(f"\n📥 Baixando: {test_url}")
                out_dir = str(APP_DIR / "output_shorts" / "teste")
                os.makedirs(out_dir, exist_ok=True)
                video_path = dl.download_youtube_video(test_url, out_dir, cfg.get("ffmpeg_path",""))
                _write_test(f"✅ Baixado: {os.path.basename(video_path)}")

                # Converter horário para segundos
                from core.analyzer import time_str_to_seconds
                start_sec = time_str_to_seconds(test_start)
                end_sec   = start_sec + test_duration

                # Músicas
                music_files = autopilot.get_music_files(cfg.get("music_folder", str(APP_DIR / "musicas")))

                # Gerar clipe
                out_path = os.path.join(out_dir, "teste_short.mp4")
                _write_test(f"\n✂️ Gerando clipe: {test_start} ({test_duration}s)")
                ed.create_short(
                    video_path=video_path,
                    start=start_sec, end=end_sec,
                    output_path=out_path,
                    width=1080, height=1920,
                    effect=cfg.get("effect", "Nenhum"),
                    enable_subtitles=test_subtitle,
                    subtitle_style=cfg.get("subtitle_style", "Amarela + Borda Preta"),
                    subtitle_position="Baixo",
                    audio_boost=0,
                    ffmpeg_exe=ffmpeg_exe,
                    music_files=music_files or None,
                    music_volume=cfg.get("music_volume", 0.10),
                    original_volume=1.0,
                    url=test_url,
                    words_per_line=cfg.get("words_per_line", 2),
                    font_size=cfg.get("font_size", 69),
                    mirror=cfg.get("mirror", True),
                    whisper_model=cfg.get("whisper_model", "tiny"),
                    broll_dir=str(APP_DIR / "broll_images") if test_broll else "",
                    use_dynamic_zoom=test_zoom,
                )
                size_mb = os.path.getsize(out_path) / 1_048_576
                _write_test(f"✅ Clipe gerado: {size_mb:.1f} MB")
                _write_test(f"📁 Salvo em: {out_path}")

                # Upload opcional
                if test_upload and channels:
                    ch = next((c for c in channels if c["name"] == test_channel), None)
                    if ch:
                        _write_test(f"\n📤 Fazendo upload para: {ch['name']}")
                        import pickle
                        from google.auth.transport.requests import Request
                        from googleapiclient.discovery import build
                        from googleapiclient.http import MediaFileUpload
                        tk = str(APP_DIR / "yt_tokens" / f"{ch['id']}.pkl")
                        with open(tk, "rb") as f: creds = pickle.load(f)
                        if creds.expired: creds.refresh(Request())
                        svc = build("youtube", "v3", credentials=creds)
                        body = {
                            "snippet": {"title": "Teste Short 🧪", "description": "#shorts #teste", "tags": ["shorts"], "categoryId": "22"},
                            "status":  {"privacyStatus": "private", "madeForKids": False},
                        }
                        media = MediaFileUpload(out_path, mimetype="video/mp4", resumable=True)
                        req = svc.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
                        resp = None
                        while resp is None: _, resp = req.next_chunk()
                        _write_test(f"✅ Publicado (privado): https://youtube.com/shorts/{resp['id']}")

                _write_test("\n" + "=" * 40)
                _write_test("🎉 TESTE CONCLUÍDO!")
            except Exception as e:
                import traceback
                _write_test(f"\n❌ ERRO: {e}")
                _write_test(traceback.format_exc())
            finally:
                if os.path.exists(test_flag_file): os.remove(test_flag_file)

        import threading
        threading.Thread(target=_run_test, daemon=True).start()
        import time; time.sleep(1)
        st.rerun()

    if is_test_running():
        import time; time.sleep(3); st.rerun()

with tab7:
    st.markdown("### 📋 Log em Tempo Real")
    if is_running():
        st.warning("⚙️ Processando... Clique em **🔄 Atualizar log** para ver o progresso.")
    log_content = read_log(50)
    st.code(log_content or "Nenhum log ainda.", language="bash")
    if st.button("🗑️ Limpar log", key="btn_clear_log"):
        clear_log()
        st.rerun()

with tab8:
    r = load_results()
    if r:
        st.markdown("### ✅ Última execução")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Gerados",   r.get("processed", 0))
        col_b.metric("Agendados", r.get("uploaded",  0))
        col_c.metric("Erros",     len(r.get("errors", [])))
        if r.get("videos"):
            st.markdown("**Vídeos agendados:**")
            for v in r["videos"]:
                st.markdown(f"""<div class="result-card">
                    📅 <b>{v['slot']}</b> — {v['channel']}<br>
                    📌 {v['title']}<br>
                    🔗 <a href="{v['url']}" target="_blank">{v['url']}</a>
                </div>""", unsafe_allow_html=True)
        if r.get("errors"):
            st.error("Erros:\n" + "\n".join(r["errors"]))
    else:
        st.info("Nenhuma execução ainda.")

# Salvar
st.markdown("---")
col_save, col_hist = st.columns(2)
with col_save:
    if st.button("💾 Salvar Configurações", key="btn_auto_6"):
        autopilot.save_config(cfg)
        st.success("✅ Salvo!")
with col_hist:
    hist_file = APP_DIR / "autopilot_history.json"
    if hist_file.exists():
        import json as _jh
        hist = _jh.loads(hist_file.read_text(encoding="utf-8"))
        total = hist.get("total", len(hist.get("urls", [])))
        updated = hist.get("updated", "")
        st.markdown(f"**📚 Histórico:** {total} podcast(s) processado(s)")
        if updated:
            st.caption(f"Última atualização: {updated}")
        if st.button("🗑️ Limpar histórico", key="btn_auto_7"):
            autopilot.clear_history()
            st.success("Histórico limpo!")
            st.rerun()
    else:
        st.info("📚 Histórico vazio")

with tab9:
    st.markdown("### 📊 Acompanhamento de Publicações")
    st.caption("Dados reais do YouTube — vídeos agendados e publicados por canal.")

    import json as _jac, pickle as _pkl9

    def _yt_service(ch_id):
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        _tk = str(APP_DIR / "yt_tokens" / f"{ch_id}.pkl")
        if not os.path.exists(_tk): return None
        with open(_tk, "rb") as _f: _creds = _pkl9.load(_f)
        if _creds.expired and _creds.refresh_token:
            _creds.refresh(Request())
        return build("youtube", "v3", credentials=_creds)

    def _get_channel_videos(ch_id, max_results=20):
        """Busca videos recentes do canal via API."""
        try:
            _svc = _yt_service(ch_id)
            if not _svc: return []
            # Pegar uploads playlist
            _ch_resp = _svc.channels().list(part="contentDetails", mine=True).execute()
            _playlist_id = _ch_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            _pl_resp = _svc.playlistItems().list(
                part="snippet", playlistId=_playlist_id,
                maxResults=max_results
            ).execute()
            _video_ids = [i["snippet"]["resourceId"]["videoId"] for i in _pl_resp.get("items",[])]
            if not _video_ids: return []
            # Pegar stats
            _v_resp = _svc.videos().list(
                part="snippet,statistics,status",
                id=",".join(_video_ids)
            ).execute()
            _videos = []
            for _v in _v_resp.get("items", []):
                _snip  = _v.get("snippet", {})
                _stats = _v.get("statistics", {})
                _stat  = _v.get("status", {})
                _pub   = _snip.get("publishedAt","")[:10]
                _sched = _stat.get("publishAt","")
                _videos.append({
                    "id":        _v["id"],
                    "title":     _snip.get("title","")[:50],
                    "views":     int(_stats.get("viewCount",0)),
                    "likes":     int(_stats.get("likeCount",0)),
                    "comments":  int(_stats.get("commentCount",0)),
                    "privacy":   _stat.get("privacyStatus",""),
                    "published": _pub,
                    "scheduled": _sched[:16].replace("T"," ") if _sched else "",
                    "url":       f"https://youtube.com/shorts/{_v['id']}",
                })
            return _videos
        except Exception as _e:
            return []

    _gf9 = APP_DIR / "channel_groups.json"
    _all_chs9 = []
    if _gf9.exists():
        _g9 = _jac.loads(_gf9.read_text(encoding="utf-8"))
        for _n9, _cs9 in _g9.items():
            for _c9 in _cs9:
                _all_chs9.append({**_c9, "_niche": _n9.title()})

    if not _all_chs9:
        st.info("Nenhum canal configurado.")
    else:
        _col_sel9, _col_btn9 = st.columns([3,1])
        with _col_sel9:
            _sel_ch9 = st.selectbox(
                "Selecionar canal",
                options=[c["name"] for c in _all_chs9],
                key="acomp_ch_sel"
            )
        with _col_btn9:
            st.markdown("<br>", unsafe_allow_html=True)
            _fetch9 = st.button("🔄 Buscar do YouTube", key="fetch_yt")

        _sel_ch_obj9 = next((c for c in _all_chs9 if c["name"] == _sel_ch9), None)

        if _fetch9 and _sel_ch_obj9:
            with st.spinner("Buscando vídeos do YouTube..."):
                _vids9 = _get_channel_videos(_sel_ch_obj9["id"])
            if _vids9:
                st.session_state[f"yt_vids_{_sel_ch9}"] = _vids9
            else:
                st.error("Não foi possível buscar vídeos. Verifique a conexão do canal.")

        _vids_cached = st.session_state.get(f"yt_vids_{_sel_ch9}", [])
        if _vids_cached:
            st.markdown(f"**{len(_vids_cached)} vídeo(s) recentes — {_sel_ch9}**")

            # Métricas rápidas
            _total_views  = sum(v["views"] for v in _vids_cached)
            _total_likes  = sum(v["likes"] for v in _vids_cached)
            _agendados    = sum(1 for v in _vids_cached if v["privacy"] == "private" and v["scheduled"])
            _publicados   = sum(1 for v in _vids_cached if v["privacy"] == "public")
            _mc1,_mc2,_mc3,_mc4 = st.columns(4)
            _mc1.metric("👁️ Views totais", f"{_total_views:,}")
            _mc2.metric("👍 Likes totais", f"{_total_likes:,}")
            _mc3.metric("✅ Publicados", _publicados)
            _mc4.metric("📅 Agendados", _agendados)

            st.markdown("---")
            for _v9 in _vids_cached:
                _vc1, _vc2, _vc3 = st.columns([4,2,1])
                with _vc1:
                    _icon = "📅" if _v9["scheduled"] else ("✅" if _v9["privacy"]=="public" else "🔒")
                    st.markdown(f"{_icon} **{_v9['title']}**")
                    if _v9["scheduled"]:
                        st.caption(f"Agendado: {_v9['scheduled']} UTC")
                    else:
                        st.caption(f"Publicado: {_v9['published']}")
                with _vc2:
                    st.caption(f"👁️ {_v9['views']:,} views | 👍 {_v9['likes']:,}")
                with _vc3:
                    st.markdown(f"[🔗 Abrir]({_v9['url']})")
                st.divider()
        else:
            st.info("Selecione um canal e clique **🔄 Buscar do YouTube**")

        # Tabela geral (local)
        st.markdown("---")
        st.markdown("**📋 Calendário local (período configurado):**")
        _today9 = datetime.date.today()
        _dates9 = [_today9 + datetime.timedelta(days=i) for i in range(-1, 6)]
        import pandas as _pd9
        _rows9 = []
        for _ch9 in _all_chs9:
            _row9 = {"Categoria": _ch9.get("_niche",""), "Canal": _ch9.get("name","")}
            for _d9 in _dates9:
                _sd9 = cfg.get("start_date",""); _ed9 = cfg.get("end_date","")
                _lbl9 = ""
                if _sd9 and _ed9:
                    try:
                        if datetime.date.fromisoformat(_sd9) <= _d9 <= datetime.date.fromisoformat(_ed9):
                            _lbl9 = "📅"
                    except: pass
                _row9[_d9.strftime("%d/%m")] = _lbl9
            _rows9.append(_row9)
        _df9 = _pd9.DataFrame(_rows9)
        st.dataframe(_df9, use_container_width=True, height=300)
        _csv9 = _df9.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ CSV", _csv9, f"acomp_{_today9.isoformat()}.csv", "text/csv")

with tab11:
    st.markdown("### 📈 Estatísticas dos Canais")
    st.caption("Inscritos, views e dados reais puxados da API do YouTube.")

    import pickle as _pkl11, json as _jst

    def _get_stats(ch_id):
        try:
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            _tk = str(APP_DIR / "yt_tokens" / f"{ch_id}.pkl")
            if not os.path.exists(_tk): return None
            with open(_tk, "rb") as _f: _creds = _pkl11.load(_f)
            if _creds.expired and _creds.refresh_token: _creds.refresh(Request())
            _svc = build("youtube", "v3", credentials=_creds)
            _resp = _svc.channels().list(part="snippet,statistics", mine=True).execute()
            _item = _resp.get("items", [{}])[0]
            _snip = _item.get("snippet", {})
            _stat = _item.get("statistics", {})
            return {
                "name":        _snip.get("title",""),
                "subscribers": int(_stat.get("subscriberCount", 0)),
                "views":       int(_stat.get("viewCount", 0)),
                "videos":      int(_stat.get("videoCount", 0)),
                "thumbnail":   _snip.get("thumbnails",{}).get("default",{}).get("url",""),
            }
        except: return None

    _gfst = APP_DIR / "channel_groups.json"
    _all_st = []
    if _gfst.exists():
        _gst = _jst.loads(_gfst.read_text(encoding="utf-8"))
        for _nst, _cst in _gst.items():
            for _c in _cst:
                _all_st.append({**_c, "_niche": _nst.title()})

    if not _all_st:
        st.info("Nenhum canal configurado.")
    else:
        if st.button("🔄 Atualizar Estatísticas de Todos os Canais", key="btn_auto_8"):
            _stats_all = {}
            _prog = st.progress(0)
            for _i, _ch in enumerate(_all_st):
                with st.spinner(f"Buscando {_ch['name']}..."):
                    _s = _get_stats(_ch["id"])
                    if _s:
                        _stats_all[_ch["id"]] = _s
                _prog.progress((_i+1)/len(_all_st))
            st.session_state["ch_stats"] = _stats_all
            st.success("✅ Estatísticas atualizadas!")

        _stats = st.session_state.get("ch_stats", {})

        # Totais gerais
        if _stats:
            _tot_subs  = sum(s.get("subscribers",0) for s in _stats.values())
            _tot_views = sum(s.get("views",0) for s in _stats.values())
            _tot_vids  = sum(s.get("videos",0) for s in _stats.values())
            _sc1,_sc2,_sc3 = st.columns(3)
            _sc1.metric("👥 Total de Inscritos", f"{_tot_subs:,}")
            _sc2.metric("👁️ Total de Views", f"{_tot_views:,}")
            _sc3.metric("🎬 Total de Vídeos", f"{_tot_vids:,}")
            st.markdown("---")

        # Cards por nicho
        _cur_niche = ""
        for _ch in _all_st:
            if _ch["_niche"] != _cur_niche:
                _cur_niche = _ch["_niche"]
                st.markdown(f"#### {_cur_niche}")

            _s = _stats.get(_ch["id"])
            _c1, _c2, _c3, _c4, _c5 = st.columns([2,2,2,2,1])
            with _c1:
                if _ch.get("thumbnail"):
                    st.image(_ch["thumbnail"], width=40)
                st.markdown(f"**{_ch['name']}**")
            with _c2:
                _subs = _s["subscribers"] if _s else "—"
                st.metric("👥 Inscritos", f"{_subs:,}" if isinstance(_subs, int) else _subs)
            with _c3:
                _vws = _s["views"] if _s else "—"
                st.metric("👁️ Views", f"{_vws:,}" if isinstance(_vws, int) else _vws)
            with _c4:
                _vds = _s["videos"] if _s else "—"
                st.metric("🎬 Vídeos", _vds)
            with _c5:
                st.markdown("<br>", unsafe_allow_html=True)
                if not _s:
                    st.caption("❌ sem dados")

        if not _stats:
            st.info("Clique em **🔄 Atualizar Estatísticas** para buscar dados do YouTube.")


with tab10:
    st.markdown("### ⏳ Fila de Upload Pendente")
    st.caption("Vídeos salvos por quota excedida. Envie quando a cota renovar às **03:00 de Brasília**.")

    import json as _jq, pickle as _pq

    QUEUE_FILE = str(APP_DIR / "upload_queue.json")

    def _load_q():
        if not os.path.exists(QUEUE_FILE): return []
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            return _jq.load(f)

    def _save_q(q):
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            _jq.dump(q, f, ensure_ascii=False, indent=2)

    _queue = _load_q()

    if not _queue:
        st.success("✅ Fila vazia — nenhum upload pendente!")
    else:
        st.warning(f"⚠️ **{len(_queue)} vídeo(s)** aguardando na fila")
        st.markdown("---")
        for _i, _item in enumerate(_queue):
            _c1, _c2, _c3 = st.columns([3,2,1])
            with _c1:
                st.markdown(f"**{_item.get('channel_name','?')}**")
                st.caption(f"📌 {_item.get('title','')[:55]}")
                st.caption(f"📁 {os.path.basename(_item.get('path',''))}")
            with _c2:
                st.caption(f"📅 {_item.get('slot','')}")
                st.caption(f"🕐 Fila: {_item.get('queued_at','')}")
                _exists = os.path.exists(_item.get("path",""))
                _sz = os.path.getsize(_item["path"])/1_048_576 if _exists else 0
                st.caption(f"💾 {'%.1f MB ✅' % _sz if _exists else '❌ não encontrado'}")
            with _c3:
                if st.button("🗑️", key=f"dq_{_i}"):
                    _queue.pop(_i); _save_q(_queue); st.rerun()
            st.divider()

        st.markdown("---")
        _col1, _col2 = st.columns(2)
        with _col1:
            _send = st.button("📤 Enviar Fila Agora!", type="primary")
        with _col2:
            if st.button("🗑️ Limpar fila toda", key="btn_auto_9"):
                _save_q([]); st.rerun()

        if _send:
            _qlogs = []
            _qbox  = st.empty()
            def _qw(msg):
                _qlogs.append(msg)
                _qbox.code("\n".join(_qlogs[-20:]), language="bash")

            _qw(f"📤 Enviando {len(_queue)} vídeo(s)...")
            _ok = 0; _remaining = []

            for _item in _queue:
                if not os.path.exists(_item.get("path","")):
                    _qw(f"❌ Arquivo não encontrado: {os.path.basename(_item['path'])}")
                    _remaining.append(_item); continue

                _qw(f"\n📤 {_item['channel_name']} — {_item['title'][:50]}")
                _qw(f"   📅 {_item.get('slot','')}")
                try:
                    from google.auth.transport.requests import Request
                    from googleapiclient.discovery import build
                    from googleapiclient.http import MediaFileUpload
                    _tk = str(APP_DIR / "yt_tokens" / f"{_item['channel_id']}.pkl")
                    with open(_tk, "rb") as _f: _creds = _pq.load(_f)
                    if _creds.expired and _creds.refresh_token: _creds.refresh(Request())
                    _svc = build("youtube", "v3", credentials=_creds)
                    _sb = {"privacyStatus": "private" if _item.get("publish_at") else "public",
                           "madeForKids": False, "selfDeclaredMadeForKids": False}
                    if _item.get("publish_at"): _sb["publishAt"] = _item["publish_at"]
                    _body = {"snippet": {"title": _item["title"][:100],
                                         "description": _item.get("description","#shorts")[:5000],
                                         "tags": ["shorts","podcast","viral","brasil"],
                                         "categoryId": "22"},
                             "status": _sb}
                    _media = MediaFileUpload(_item["path"], mimetype="video/mp4",
                                            resumable=True, chunksize=5*1024*1024)
                    _req  = _svc.videos().insert(part=",".join(_body.keys()),
                                                  body=_body, media_body=_media)
                    _resp = None
                    while _resp is None: _, _resp = _req.next_chunk()
                    _url = f"https://youtube.com/shorts/{_resp['id']}"
                    _qw(f"   ✅ {_url}")
                    _ok += 1
                except Exception as _e:
                    _es = str(_e)
                    if "quotaExceeded" in _es:
                        _qw(f"   ⏳ Quota ainda excedida — mantendo na fila")
                    else:
                        _qw(f"   ❌ Erro: {_es[:80]}")
                    _remaining.append(_item)

            _save_q(_remaining)
            _qw(f"\n{'='*40}")
            _qw(f"✅ {_ok} enviado(s) | ⏳ {len(_remaining)} restante(s) na fila")
            if _ok > 0: st.success(f"✅ {_ok} vídeo(s) enviado(s)!")
            if _remaining: st.warning(f"⏳ {len(_remaining)} ainda na fila")

    st.markdown("---")
    st.info("💡 A cota do YouTube renova todo dia às **03:00 horário de Brasília**")

# ── Executar todos os nichos ──────────────────────────────────────────────────
run_all = run_all if "run_all" in dir() else False
if run_all and not is_running():
    autopilot.save_config(cfg)
    clear_log()
    set_running(True)
    write_log("🌐 INICIANDO TODOS OS NICHOS...")

    def _run_all():
        try:
            autopilot.run_all_niches(cfg, log_callback=write_log)
            write_log("🏁 TODOS OS NICHOS FINALIZADOS!")
        except Exception as e:
            import traceback
            write_log(f"❌ ERRO: {e}\n{traceback.format_exc()}")
        finally:
            set_running(False)

    import threading as _thr_all
    _thr_all.Thread(target=_run_all, daemon=True).start()
    time.sleep(1)
    st.rerun()

# ── Executar nicho atual ───────────────────────────────────────────────────────
if run_now:
    autopilot.save_config(cfg)
    clear_log()
    set_running(True)
    write_log("▶️ Iniciando autopiloto...")
    
    def _run():
        try:
            results = autopilot.run_autopilot(cfg, log_callback=write_log)
            save_results(results)
            write_log("🏁 FINALIZADO!")
        except Exception as e:
            import traceback
            write_log(f"❌ ERRO FATAL: {e}")
            write_log(traceback.format_exc())
        finally:
            set_running(False)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    time.sleep(2)
    st.rerun()
