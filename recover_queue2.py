"""
recover_queue2.py
Varre a pasta output_shorts e popula a fila com todos os videos encontrados.
Cole na pasta do projeto e rode: python recover_queue2.py
"""
import os, json, glob
from pathlib import Path
from datetime import datetime, timedelta
import pytz

APP_DIR    = Path(__file__).resolve().parent
QUEUE_FILE = str(APP_DIR / "upload_queue.json")
OUTPUT_DIR = APP_DIR / "output_shorts"
BRT        = pytz.timezone("America/Sao_Paulo")

def load_channels():
    chs = {}
    gf = APP_DIR / "channel_groups.json"
    if gf.exists():
        for niche, channels in json.loads(gf.read_text(encoding="utf-8")).items():
            for c in channels:
                chs[c["name"]] = c
    cf = APP_DIR / "channels.json"
    if cf.exists():
        for c in json.loads(cf.read_text(encoding="utf-8")):
            chs[c["name"]] = c
    return chs

def slot_to_iso(date, time_str):
    h, m = map(int, time_str.split(":"))
    dt_brt = BRT.localize(datetime(date.year, date.month, date.day, h, m))
    return dt_brt.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

ch_map    = load_channels()
ch_list   = list(ch_map.values())
schedules = ["10:30", "12:00", "18:00", "21:30"]
secrets   = str(APP_DIR / "client_secrets.json")

# Encontrar todos os mp4 gerados (mais recentes primeiro)
all_videos = []
for folder in sorted(OUTPUT_DIR.glob("*"), reverse=True):
    if not folder.is_dir(): continue
    vids = sorted([f for f in folder.glob("*.mp4")
                   if not any(x in f.name for x in ["_v.", "_a.", "_pre.", "teste"])])
    all_videos.extend(vids)
    if all_videos: break  # Pega só a pasta mais recente

if not all_videos:
    print("❌ Nenhum vídeo encontrado em output_shorts!")
    exit()

print(f"📁 Encontrados: {len(all_videos)} vídeo(s)")

# Carregar fila existente para não duplicar
existing = []
if os.path.exists(QUEUE_FILE):
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        existing = json.load(f)
existing_paths = {e["path"] for e in existing}

# Data base: amanhã
base_date = (datetime.now(BRT) + timedelta(days=1)).date()

queue = list(existing)
added = 0

for idx, video_path in enumerate(all_videos):
    if str(video_path) in existing_paths:
        print(f"⏭️ Já na fila: {video_path.name}")
        continue

    # Distribuir canal e horário
    ch      = ch_list[idx % len(ch_list)] if ch_list else None
    slot    = schedules[idx % len(schedules)]
    day_off = idx // len(schedules)  # dia extra por grupo de slots
    pub_date = base_date + timedelta(days=day_off % 7)  # max 7 dias

    if not ch:
        print(f"⚠️ Sem canais configurados!")
        break

    pub_iso  = slot_to_iso(pub_date, slot)
    slot_str = f"{pub_date.strftime('%d/%m/%Y')} {slot}"

    queue.append({
        "path":         str(video_path),
        "channel_id":   ch["id"],
        "channel_name": ch["name"],
        "secrets_path": ch.get("secrets_path", secrets),
        "title":        video_path.stem.replace("_", " ").title()[:80],
        "description":  "#shorts #podcast #viral #brasil",
        "publish_at":   pub_iso,
        "slot":         slot_str,
        "queued_at":    datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    print(f"✅ [{idx+1}] {ch['name']} | {slot_str} | {video_path.name}")
    added += 1

with open(QUEUE_FILE, "w", encoding="utf-8") as f:
    json.dump(queue, f, ensure_ascii=False, indent=2)

print(f"\n{'='*50}")
print(f"✅ {added} vídeo(s) adicionados à fila!")
print(f"Total na fila: {len(queue)}")
print(f"\nAbra o Autopiloto → aba ⏳ Fila → clique Enviar!")
