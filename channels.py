"""
channels.py v2
Gerencia grupos de canais por nicho.
Cada grupo tem até 5 canais com logo e token OAuth proprios.
"""
import sys, os, json, pickle
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

import importlib.util, streamlit as st

# Carregar uploader direto
_up_src = (APP_DIR / "core" / "uploader.py").read_text(encoding="utf-8")
_up_ns  = {"__file__": str(APP_DIR / "core" / "uploader.py")}
exec(compile(_up_src, str(APP_DIR / "core" / "uploader.py"), "exec"), _up_ns)

GROUPS_FILE  = str(APP_DIR / "channel_groups.json")
TOKENS_DIR   = str(APP_DIR / "yt_tokens")
LOGOS_DIR    = str(APP_DIR / "channel_logos")

NICHE_OPTIONS = {
    "geral":           "🎙️ Geral",
    "politica":        "🏛️ Política",
    "policia_relatos": "🚔 Polícia & Relatos",
    "futebol":         "⚽ Futebol",
    "games":           "🎮 Games",
    "humor":           "😂 Humor",
    "financas":        "💰 Finanças",
    "saude":           "❤️ Saúde & Bem-estar",
    "tecnologia":      "💻 Tecnologia",
    "outros":          "📦 Outros",
}

def load_groups() -> dict:
    """Retorna dict: {niche: [canal1, canal2, ...]}"""
    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_groups(groups: dict):
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)

def is_auth(ch_id: str) -> bool:
    return os.path.exists(os.path.join(TOKENS_DIR, f"{ch_id}.pkl"))

def connect_channel(ch_id: str, secrets_path: str) -> dict:
    """Autentica canal e retorna info do YouTube."""
    info = _up_ns["get_channel_info"](ch_id, secrets_path)
    return info

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="📡 Gerenciar Canais", page_icon="📡", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');
#MainMenu,header,footer,div[data-testid="stToolbar"]{display:none!important}
.block-container{padding-top:1.2rem!important}
html,body,[class*="css"]{font-family:'Space Grotesk',sans-serif}
.stApp{background:linear-gradient(135deg,#0a0a0f,#0f0f1a);color:#e8e8f0}
.stButton>button{background:linear-gradient(90deg,#ff3cac,#784ba0,#2b86c5)!important;color:white!important;border:none!important;border-radius:10px!important;font-weight:600!important;width:100%!important}
.group-card{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:1.2rem;margin-bottom:1rem}
.ch-row{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:0.8rem;margin:0.4rem 0;display:flex;align-items:center;gap:1rem}
.badge-ok{background:#00c864;color:#000;padding:2px 10px;border-radius:20px;font-size:.75rem;font-weight:700}
.badge-no{background:#ff4444;color:#fff;padding:2px 10px;border-radius:20px;font-size:.75rem;font-weight:700}
</style>
""", unsafe_allow_html=True)

st.markdown("## 📡 Grupos de Canais por Nicho")
st.caption("Cada nicho tem até 5 canais. Ao selecionar um nicho no Autopiloto, ele publica nesses canais.")
st.markdown("---")

groups = load_groups()
secrets_default = str(APP_DIR / "client_secrets.json")

# ── Selecionar nicho para editar ──────────────────────────────────────────────
col_sel, col_add = st.columns([3, 1])
with col_sel:
    selected_niche = st.selectbox(
        "Selecionar grupo para editar",
        options=list(NICHE_OPTIONS.keys()),
        format_func=lambda x: NICHE_OPTIONS[x],
    )
with col_add:
    st.markdown("<br>", unsafe_allow_html=True)
    if selected_niche not in groups:
        if st.button("➕ Criar grupo"):
            groups[selected_niche] = []
            save_groups(groups)
            st.success(f"Grupo '{NICHE_OPTIONS[selected_niche]}' criado!")
            st.rerun()

st.markdown("---")

# ── Editar grupo selecionado ──────────────────────────────────────────────────
if selected_niche not in groups:
    st.info(f"Grupo **{NICHE_OPTIONS[selected_niche]}** não existe ainda. Clique em **➕ Criar grupo**.")
else:
    channels = groups[selected_niche]
    niche_label = NICHE_OPTIONS[selected_niche]

    st.markdown(f"### {niche_label} — {len(channels)}/5 canais")

    # Listar canais existentes
    for i, ch in enumerate(channels):
        authed = is_auth(ch["id"])
        badge  = f'<span class="badge-ok">✅ Conectado</span>' if authed else f'<span class="badge-no">❌ Não conectado</span>'

        with st.expander(f"{ch['name']} {' ✅' if authed else ' ❌'}", expanded=not authed):
            col1, col2, col3 = st.columns([2, 2, 1])

            with col1:
                # Logo
                logo_up = st.file_uploader("Logo (PNG/JPG)", type=["png","jpg","jpeg"],
                                            key=f"logo_{selected_niche}_{i}")
                if logo_up:
                    os.makedirs(LOGOS_DIR, exist_ok=True)
                    lp = os.path.join(LOGOS_DIR, f"{ch['id']}_{logo_up.name}")
                    with open(lp, "wb") as f: f.write(logo_up.read())
                    channels[i]["logo_path"] = lp
                    save_groups(groups)
                    st.success("Logo salva!")

                if ch.get("logo_path") and os.path.exists(ch.get("logo_path","")):
                    st.image(ch["logo_path"], width=70)

            with col2:
                sp = st.text_input("client_secrets.json",
                                   value=ch.get("secrets_path", secrets_default),
                                   key=f"sp_{selected_niche}_{i}")
                if sp != ch.get("secrets_path",""):
                    channels[i]["secrets_path"] = sp
                    save_groups(groups)

                st.markdown(badge, unsafe_allow_html=True)
                if ch.get("youtube_name"):
                    st.caption(f"Canal: {ch['youtube_name']}")

                if not authed:
                    if st.button("🔐 Conectar", key=f"conn_{selected_niche}_{i}"):
                        sp_val = channels[i].get("secrets_path", sp)
                        if not os.path.exists(sp_val):
                            st.error("client_secrets.json não encontrado!")
                        else:
                            try:
                                with st.spinner("Abrindo browser..."):
                                    info = connect_channel(ch["id"], sp_val)
                                    channels[i].update({"authenticated": True,
                                                        "secrets_path": sp_val, **info})
                                    save_groups(groups)
                                st.success(f"✅ Conectado: {info.get('youtube_name','')}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {e}")
                else:
                    if st.button("🔄 Reconectar", key=f"reconn_{selected_niche}_{i}"):
                        tp = os.path.join(TOKENS_DIR, f"{ch['id']}.pkl")
                        if os.path.exists(tp): os.remove(tp)
                        channels[i]["authenticated"] = False
                        save_groups(groups)
                        st.rerun()

            with col3:
                st.markdown("<br><br>", unsafe_allow_html=True)
                if st.button("🗑️ Remover", key=f"del_{selected_niche}_{i}"):
                    channels.pop(i)
                    save_groups(groups)
                    st.rerun()

    # Adicionar canal ao grupo
    if len(channels) < 5:
        st.markdown("---")
        st.markdown("#### ➕ Adicionar Canal ao Grupo")
        with st.form(f"add_{selected_niche}"):
            new_name = st.text_input("Nome do canal", placeholder=f"Ex: {niche_label} Cortes A")
            submitted = st.form_submit_button("Adicionar")
            if submitted and new_name:
                new_id = f"{selected_niche}_ch{len(channels)+1}_{int(os.times()[4]*1000)%9999}"
                channels.append({
                    "id": new_id, "name": new_name.strip(),
                    "logo_path": "", "authenticated": False,
                    "secrets_path": secrets_default,
                    "niche": selected_niche,
                })
                save_groups(groups)
                st.success(f"Canal '{new_name}' adicionado ao grupo {niche_label}!")
                st.rerun()
    else:
        st.warning("⚠️ Limite de 5 canais por grupo atingido.")

st.markdown("---")

# ── Visão geral de todos os grupos ───────────────────────────────────────────
st.markdown("### 📊 Visão Geral — Todos os Grupos")
if not groups:
    st.info("Nenhum grupo criado ainda.")
else:
    cols = st.columns(min(len(groups), 3))
    for idx, (niche, chs) in enumerate(groups.items()):
        with cols[idx % 3]:
            authed_count = sum(1 for c in chs if is_auth(c["id"]))
            st.markdown(f"""
            <div class="group-card">
                <b>{NICHE_OPTIONS.get(niche, niche)}</b><br>
                <small>{len(chs)} canal(is) | {authed_count} conectado(s)</small><br>
            """, unsafe_allow_html=True)
            for c in chs:
                ok = "✅" if is_auth(c["id"]) else "❌"
                st.markdown(f"<small>{ok} {c['name']}</small>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
with st.expander("📖 Como usar"):
    st.markdown("""
**1.** Selecione o nicho (Futebol, Games, etc.) e clique **➕ Criar grupo**

**2.** Adicione até 5 canais ao grupo

**3.** Configure o `client_secrets.json` e clique **🔐 Conectar** para cada canal

**4.** No Autopiloto, selecione o nicho — ele busca podcasts daquele nicho E publica nos canais do grupo correspondente

**Dica:** Todos os seus 16 canais podem estar em grupos diferentes usando o mesmo `client_secrets.json`
    """)
