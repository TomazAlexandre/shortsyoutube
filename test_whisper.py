"""
Rode este arquivo no terminal para diagnosticar o problema da legenda:
python test_whisper.py "C:\caminho\para\seu\video.mp4" "C:\ffmpeg\bin\ffmpeg.exe"
"""
import sys, os, subprocess

video = sys.argv[1] if len(sys.argv) > 1 else input("Caminho do video MP4: ").strip()
ffmpeg = sys.argv[2] if len(sys.argv) > 2 else input("Caminho do ffmpeg.exe: ").strip()

print(f"\n=== DIAGNÓSTICO DE LEGENDA ===")
print(f"Video : {video}")
print(f"FFmpeg: {ffmpeg}")
print(f"Video existe: {os.path.exists(video)}")
print(f"FFmpeg existe: {os.path.exists(ffmpeg)}")

# 1. Testar extração de áudio
print("\n[1] Extraindo audio WAV com ffmpeg...")
wav = video + "_test.wav"
cmd = [ffmpeg, "-y", "-i", video, "-ar", "16000", "-ac", "1", "-f", "wav", wav]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(f"ERRO ao extrair audio:\n{r.stderr[-500:]}")
    sys.exit(1)
print(f"OK — WAV gerado: {wav} ({os.path.getsize(wav)//1024} KB)")

# 2. Testar Whisper
print("\n[2] Testando Whisper...")
try:
    import whisper
    print(f"Whisper importado OK — versao: {whisper.__version__ if hasattr(whisper,'__version__') else 'desconhecida'}")
except ImportError as e:
    print(f"ERRO: Whisper nao instalado: {e}")
    print("Execute: pip install openai-whisper")
    sys.exit(1)

print("[3] Carregando modelo 'base'...")
model = whisper.load_model("base")
print("Modelo carregado OK")

print("[4] Transcrevendo (pode demorar 1-2 min)...")
result = model.transcribe(wav, fp16=False, language="pt", word_timestamps=True)
segs = result.get("segments", [])
print(f"Segmentos: {len(segs)}")

if segs:
    print(f"Primeiro segmento: {segs[0]['text'][:80]}")
    words = segs[0].get("words", [])
    print(f"Palavras no primeiro segmento: {len(words)}")
    if words:
        print(f"Primeira palavra: {words[0]}")

    # Gerar SRT de teste
    srt = video + "_test.srt"
    entries = []
    for seg in segs:
        words_list = seg.get("words", [])
        if words_list:
            chunk = []
            for w in words_list:
                chunk.append(w)
                if len(chunk) >= 3:
                    entries.append((chunk[0]["start"], chunk[-1]["end"],
                                    " ".join(x["word"].strip() for x in chunk)))
                    chunk = []
            if chunk:
                entries.append((chunk[0]["start"], chunk[-1]["end"],
                                " ".join(x["word"].strip() for x in chunk)))
        else:
            entries.append((seg["start"], seg["end"], seg["text"].strip()))

    def srt_time(s):
        h,m,sec,ms = int(s//3600),int((s%3600)//60),int(s%60),int((s%1)*1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

    with open(srt, "w", encoding="utf-8") as f:
        for i,(ts,te,txt) in enumerate(entries,1):
            f.write(f"{i}\n{srt_time(ts)} --> {srt_time(te)}\n{txt}\n\n")
    print(f"\nSRT gerado: {srt}")
    print("Primeiras 5 entradas:")
    with open(srt) as f:
        print(f.read()[:400])
else:
    print("NENHUM segmento — audio pode estar vazio ou inaudivel")

# 3. Testar burn de legenda
print("\n[5] Testando burn de legenda no video...")
out = video + "_com_legenda.mp4"
srt_esc = srt.replace("\\", "/").replace(":", "\\:")
cmd2 = [
    ffmpeg, "-y", "-i", video,
    "-vf", f"subtitles='{srt_esc}':force_style='FontSize=14,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Alignment=2,MarginV=120'",
    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
    "-c:a", "copy", out
]
r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=300)
if r2.returncode != 0:
    print(f"ERRO no burn:\n{r2.stderr[-800:]}")
else:
    print(f"OK — Video com legenda: {out}")

# Limpar
if os.path.exists(wav): os.remove(wav)
print("\n=== FIM DO DIAGNÓSTICO ===")
