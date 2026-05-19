"""
refresh_tokens.py
Renova todos os tokens OAuth dos canais.
Cole na pasta do projeto e rode: python refresh_tokens.py
"""
import os, json, pickle
from pathlib import Path

APP_DIR    = Path(__file__).resolve().parent
TOKENS_DIR = APP_DIR / "yt_tokens"

def load_all_channels():
    chs = []
    gf = APP_DIR / "channel_groups.json"
    if gf.exists():
        for niche, channels in json.loads(gf.read_text(encoding="utf-8")).items():
            for c in channels:
                chs.append(c)
    cf = APP_DIR / "channels.json"
    if cf.exists():
        for c in json.loads(cf.read_text(encoding="utf-8")):
            chs.append(c)
    return chs

channels = load_all_channels()
secrets  = str(APP_DIR / "client_secrets.json")

print(f"🔑 Renovando tokens de {len(channels)} canal(is)...")
print("=" * 50)

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

for ch in channels:
    ch_id      = ch["id"]
    ch_name    = ch.get("name", ch_id)
    token_path = str(TOKENS_DIR / f"{ch_id}.pkl")
    sp         = ch.get("secrets_path", secrets)

    print(f"\n📡 {ch_name}")

    # Tentar refresh primeiro
    if os.path.exists(token_path):
        try:
            with open(token_path, "rb") as f:
                creds = pickle.load(f)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(token_path, "wb") as f:
                    pickle.dump(creds, f)
                if creds.valid:
                    print(f"   ✅ Token renovado via refresh!")
                    continue
        except Exception as e:
            print(f"   ⚠️ Refresh falhou: {e}")

    # Reautenticar via browser
    print(f"   🌐 Abrindo browser para autenticação...")
    if not os.path.exists(sp):
        print(f"   ❌ client_secrets.json não encontrado: {sp}")
        continue
    try:
        flow  = InstalledAppFlow.from_client_secrets_file(sp, SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent",
                                       success_message="✅ Pode fechar esta janela!")
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
        print(f"   ✅ Reautenticado com sucesso!")
    except Exception as e:
        print(f"   ❌ Erro: {e}")

print("\n" + "=" * 50)
print("✅ Pronto! Agora pode enviar a fila no Autopiloto.")
