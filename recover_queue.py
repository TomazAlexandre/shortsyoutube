"""
recover_queue.py - recupera os 20 videos do log de 21/04/2026
Cole na pasta do projeto e rode: python recover_queue.py
"""
import os, json, glob
from pathlib import Path
from datetime import datetime
import pytz

APP_DIR    = Path(__file__).resolve().parent
QUEUE_FILE = str(APP_DIR / "upload_queue.json")
OUTPUT_DIR = APP_DIR / "output_shorts"
BRT        = pytz.timezone("America/Sao_Paulo")

def slot_to_iso(slot_str):
    dt     = datetime.strptime(slot_str, "%d/%m/%Y %H:%M")
    dt_brt = BRT.localize(dt)
    return dt_brt.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def find_video(pod_idx, clip_idx):
    """Busca o mp4 em todas as subpastas de output_shorts."""
    for folder in sorted(OUTPUT_DIR.glob("*"), reverse=True):
        if not folder.is_dir(): continue
        for pat in [f"pod{pod_idx}_clip{clip_idx}_*.mp4",
                    f"pod{pod_idx}_clip{clip_idx}.mp4"]:
            matches = list(folder.glob(pat))
            if matches:
                return str(matches[0])
    return ""

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

# 20 entradas extraídas do log
ENTRIES = [
    (1,1,"NexisCortes",  "22/04/2026 12:00","NEYMAR JR. REVELA SEGREDOS! ⚡️😱 | PODPAH CLIP 1"),
    (1,2,"CortesNow",    "22/04/2026 15:00","NEYMAR JR. REVELA SEGREDOS! 😲⚽️ | Podpah"),
    (1,3,"CortesTurbo",  "22/04/2026 18:00","NEYMAR FALA SOBRE A PRESSÃO! ⚽💥 Você não vai acreditar!"),
    (1,4,"Shorts Fade",  "22/04/2026 21:30","NEYMAR REVELA SEGREDO CHOCANTE! 😱⚽️"),
    (1,5,"Shorts Blast", "22/04/2026 12:00","NEYMAR JR. REVELOU um SEGREDO INCRÍVEL! 😱⚽️"),
    (2,1,"NexisCortes",  "22/04/2026 15:00","🔥 PASTOR CLÁUDIO DUARTE REVELA SEGREDOS! 😱✨"),
    (2,2,"CortesNow",    "22/04/2026 18:00","DESCUBRA O SEGREDO DO SUCESSO! 🚀✨"),
    (2,3,"CortesTurbo",  "22/04/2026 21:30","🔥 O Segredo Que TRANSFORMOU A VIDA do Pastor Cláudio Duarte! 😱"),
    (2,4,"Shorts Fade",  "22/04/2026 12:00","🔥 O SEGREDO que PASTOR CLÁUDIO DUARTE NUNCA REVELOU! 😱"),
    (2,5,"Shorts Blast", "22/04/2026 15:00","🔊 O SEGREDO que TRANSFORMA VIDAS! 😱 | PASTOR CLÁUDIO DUARTE"),
    (3,1,"NexisCortes",  "22/04/2026 18:00","SANDY REVELA SEGREDOS 🌟 Que NINGUÉM SABIA! 🤫"),
    (3,2,"CortesNow",    "22/04/2026 21:30","SANDY REVELA SEGREDOS INCRÍVEIS! 🌟🎤"),
    (3,3,"CortesTurbo",  "22/04/2026 12:00","SANDY REVELA SEGREDOS CHOCANTES! 🤯✨"),
    (3,4,"Shorts Fade",  "22/04/2026 15:00","SANDY REVELA SEGREDOS CHOCANTES! 😱🎤"),
    (3,5,"Shorts Blast", "22/04/2026 18:00","SANDY REVELA SEGREDOS INCRÍVEIS! 🤯✨ #GIOH"),
    (4,1,"NexisCortes",  "22/04/2026 21:30","PAOLLA OLIVEIRA REVELA SEGREDOS! 😲✨"),
    (4,2,"CortesNow",    "22/04/2026 12:00","🔥 PAOLLA OLIVEIRA REVELA SEGREDO INESPERADO! 😲 #Shorts"),
    (4,3,"CortesTurbo",  "22/04/2026 15:00","PAOLLA OLIVEIRA FALA SOBRE AMOR E SUCESSO! 💖✨"),
    (4,4,"Shorts Fade",  "22/04/2026 18:00","PAOLLA OLIVEIRA REVELA SEGREDO SURPREENDENTE! 😱✨"),
    (4,5,"Shorts Blast", "22/04/2026 21:30","PAOLLA OLIVEIRA REVELA SEGREDOS! 😲✨ #Shorts"),
]

ch_map = load_channels()
queue  = []
secrets = str(APP_DIR / "client_secrets.json")

for pod_idx, clip_idx, ch_name, slot, title in ENTRIES:
    ch = ch_map.get(ch_name)
    if not ch:
        print(f"⚠️ Canal não encontrado: {ch_name}")
        continue

    video = find_video(pod_idx, clip_idx)
    if not video:
        print(f"❌ Vídeo não encontrado: pod{pod_idx}_clip{clip_idx} ({ch_name})")
        continue

    queue.append({
        "path":         video,
        "channel_id":   ch["id"],
        "channel_name": ch_name,
        "secrets_path": ch.get("secrets_path", secrets),
        "title":        title,
        "description":  "#shorts #podcast #viral #brasil",
        "publish_at":   slot_to_iso(slot),
        "slot":         slot,
        "queued_at":    datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    print(f"✅ {ch_name} | {slot} | {os.path.basename(video)}")

with open(QUEUE_FILE, "w", encoding="utf-8") as f:
    json.dump(queue, f, ensure_ascii=False, indent=2)

print(f"\n{'='*50}")
print(f"✅ {len(queue)}/20 vídeo(s) na fila!")
print(f"Abra o Autopiloto → aba ⏳ Fila → clique Enviar após 03:00 BRT")
