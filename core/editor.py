"""
editor.py — versão limpa e estável
Corta, redimensiona, adiciona efeitos, legenda e emoji no video.
"""
import os, re, shutil, subprocess, tempfile, random, math

# ── Estilos de legenda ────────────────────────────────────────────────────────
# Formato ASS: &HAABBGGRR
SUBTITLE_STYLES = {
    "Amarela + Borda Preta": {
        "FontName":"Arial Black","FontSize":"80",
        "PrimaryColour":"&H0000FFFF","OutlineColour":"&H00000000",
        "Bold":"1","Outline":"5","Shadow":"2","BorderStyle":"1",
    },
    "Branca + Borda Preta": {
        "FontName":"Arial Black","FontSize":"80",
        "PrimaryColour":"&H00FFFFFF","OutlineColour":"&H00000000",
        "Bold":"1","Outline":"5","Shadow":"2","BorderStyle":"1",
    },
    "Gradiente Rosa/Roxo": {
        "FontName":"Arial Black","FontSize":"80",
        "PrimaryColour":"&H00FF00FF","OutlineColour":"&H00000000",
        "Bold":"1","Outline":"5","Shadow":"2","BorderStyle":"1",
    },
    "Laranja + Borda Preta": {
        "FontName":"Arial Black","FontSize":"80",
        "PrimaryColour":"&H000080FF","OutlineColour":"&H00000000",
        "Bold":"1","Outline":"5","Shadow":"2","BorderStyle":"1",
    },
}

# ── Mapa de palavras → emoji ──────────────────────────────────────────────────
EMOJI_MAP = {
    "coração":"❤️","amor":"❤️","amo":"❤️","amar":"❤️",
    "mãos":"🤲","mão":"🤲","abraço":"🤗","abraçar":"🤗",
    "olhos":"👀","olhar":"👁️","cabeça":"🧠","mente":"🧠",
    "pensar":"💭","pensamento":"💭","boca":"👄","beijo":"😘",
    "braço":"💪","força":"💪","forte":"💪","dor":"🩹",
    "bebê":"👶","nasceu":"👶","gravidez":"🤰",
    "feliz":"😊","felicidade":"😊","alegria":"😄",
    "triste":"😢","tristeza":"😢","chorar":"😭","lágrima":"😢",
    "raiva":"😡","nervoso":"😤","ódio":"🤬",
    "medo":"😱","assustado":"😨","terror":"😱",
    "surpresa":"😲","surpreendente":"😲","chocado":"😲",
    "rir":"😂","rindo":"😂","risada":"😂","engraçado":"😂",
    "vergonha":"😳","ansioso":"😰","ansiedade":"😰",
    "orgulho":"🦁","saudade":"🥺","paz":"☮️","calmo":"😌",
    "esperança":"🌟","sonho":"✨","paixão":"🔥","apaixonado":"😍",
    "liberdade":"🕊️","livre":"🕊️",
    "dinheiro":"💰","grana":"💵","rico":"🤑","milionário":"🤑",
    "pobre":"😔","banco":"🏦","investimento":"📈","lucro":"💹",
    "salário":"💸","dívida":"😬","poupança":"🐷","imposto":"😤",
    "emprego":"💼","trabalho":"💼","empresa":"🏢","startup":"🚀",
    "sucesso":"🏆","campeão":"🏆","vencer":"🥇","ganhar":"🥇",
    "meta":"🎯","objetivo":"🎯","foco":"🎯","motivação":"⚡",
    "disciplina":"💪","dedicação":"💪","desistir":"🚫",
    "aprender":"📚","conhecimento":"📚","liderança":"👑",
    "mudança":"🦋","transformação":"🦋","evolução":"⬆️",
    "casamento":"💍","casado":"💍","noivado":"💍",
    "divórcio":"💔","separação":"💔","namorada":"👫","namorado":"👫",
    "família":"👨‍👩‍👧","filho":"👶","filha":"👶","pai":"👨","mãe":"👩",
    "traição":"💔","trair":"💔","amigo":"🤝","amizade":"🤝",
    "respeito":"🙏","humildade":"🙏",
    "futebol":"⚽","gol":"⚽","bola":"⚽","torcida":"📣","copa":"🏆",
    "academia":"🏋️","treino":"🏋️","correr":"🏃","luta":"🥊",
    "celular":"📱","computador":"💻","internet":"🌐",
    "ia":"🤖","viral":"📲","game":"🎮","jogo":"🎮",
    "saúde":"❤️‍🩹","médico":"👨‍⚕️","hospital":"🏥","remédio":"💊",
    "doente":"🤒","dieta":"🥗","dormir":"😴","estresse":"😫",
    "depressão":"😞","terapia":"🧠",
    "deus":"🙏","jesus":"✝️","orar":"🙏","fé":"✝️",
    "anjo":"👼","igreja":"⛪","milagre":"✨","diabo":"😈",
    "karma":"☯️","meditação":"🧘",
    "brasil":"🇧🇷","brasileiro":"🇧🇷","política":"🏛️",
    "eleição":"🗳️","corrupção":"🤮","policia":"👮","crime":"🚨",
    "famoso":"⭐","fama":"⭐","ator":"🎬","filme":"🎬",
    "música":"🎵","cantar":"🎤","cantor":"🎤","show":"🎪",
    "carro":"🚗","moto":"🏍️","casa":"🏠","comida":"🍽️",
    "churrasco":"🥩","cerveja":"🍺","viagem":"✈️","praia":"🏖️",
    "festa":"🎉","aniversário":"🎂","natal":"🎄",
    "incrível":"🔥","absurdo":"🤯","insano":"🤯","bomba":"💣",
    "chocante":"😱","mentira":"😱","verdade":"💯","nunca":"🚫",
    "sempre":"♾️","agora":"⚡","loucura":"🤪","sofrimento":"😔",
}

def _find_emoji(text):
    t = text.lower()
    for word, emoji in EMOJI_MAP.items():
        if word in t:
            return emoji
    return None

# ── Helpers ───────────────────────────────────────────────────────────────────
def _run(cmd, label=""):
    result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"{label} falhou:\n{result.stderr[-500:]}")
    return result

def seconds_to_str(s):
    h = int(s//3600); m = int((s%3600)//60); sec = s%60
    return f"{h:02d}:{m:02d}:{sec:06.3f}"

def time_str_to_seconds(t):
    try:
        parts = t.split(":")
        return int(parts[0])*3600+int(parts[1])*60+float(parts[2])
    except: return 0

# ── Whisper ───────────────────────────────────────────────────────────────────
def _whisper_srt(video_path, srt_path, ffmpeg_exe="ffmpeg", words_per_line=2, whisper_model="tiny"):
    try:
        import whisper
        audio_wav = srt_path.replace(".srt", "_audio.wav")
        _run([ffmpeg_exe,"-y","-i",video_path,"-ar","16000","-ac","1","-vn",audio_wav], "Audio extract")
        model = whisper.load_model(whisper_model)
        result = model.transcribe(audio_wav, language="pt", word_timestamps=True)
        os.remove(audio_wav)

        # Agrupar palavras em blocos de N palavras
        segments = []
        for seg in result["segments"]:
            words = seg.get("words", [])
            if not words:
                segments.append({"start":seg["start"],"end":seg["end"],"text":seg["text"].strip()})
                continue
            chunk, t0 = [], None
            for w in words:
                if t0 is None: t0 = w["start"]
                chunk.append(w["word"].strip())
                if len(chunk) >= words_per_line:
                    segments.append({"start":t0,"end":w["end"],"text":" ".join(chunk)})
                    chunk, t0 = [], None
            if chunk:
                segments.append({"start":t0,"end":words[-1]["end"],"text":" ".join(chunk)})

        # Escrever SRT
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, 1):
                f.write(f"{i}\n")
                f.write(f"{seconds_to_str(seg['start']).replace('.',',')} --> {seconds_to_str(seg['end']).replace('.',',')}\n")
                f.write(f"{seg['text']}\n\n")
        return os.path.exists(srt_path) and os.path.getsize(srt_path) > 10
    except Exception as e:
        print(f"[editor] Whisper erro: {e}")
        return False

# ── Legenda ───────────────────────────────────────────────────────────────────
def _burn_subtitle(src, srt_path, dst, style_name, position, ffmpeg_exe, font_size=80):
    """Queima legenda E emojis no vídeo usando subtitles filter."""
    style = SUBTITLE_STYLES.get(style_name, SUBTITLE_STYLES["Amarela + Borda Preta"])

    if position == "Cima":
        alignment, margin_v = 8, 80
    elif position == "Centro":
        alignment, margin_v = 5, 0
    else:
        alignment, margin_v = 2, 180

    # Gerar ASS com emojis incluídos
    ass_path = srt_path.replace(".srt", ".ass")
    _srt_to_ass_with_emoji(srt_path, ass_path, style, alignment, margin_v, font_size)

    # Escapar path para FFmpeg
    ass_esc = ass_path.replace("\\", "/").replace(":", "\\:")

    _run([
        ffmpeg_exe, "-y", "-i", src,
        "-vf", f"ass='{ass_esc}'",
        "-c:v", "libx264", "-preset", "medium", "-crf", "17",
        "-profile:v", "high", "-level", "4.2",
        "-pix_fmt", "yuv420p",
        "-b:v", "6000k", "-maxrate", "8000k", "-bufsize", "16000k",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        dst,
    ], "Burn legenda+emoji")

def _srt_to_ass_with_emoji(srt_path, ass_path, style, alignment, margin_v, font_size):
    """Converte SRT para ASS com emojis acima das falas."""
    def srt_time_to_ass(t):
        # 00:00:01,234 -> 0:00:01.23
        t2 = t.replace(",",".")
        parts = t2.split(":")
        h,m,s = parts[0],parts[1],parts[2]
        return f"{int(h)}:{m}:{float(s):05.2f}"

    with open(srt_path,"r",encoding="utf-8",errors="ignore") as f:
        srt = f.read()

    blocks = re.split(r"\n\n+", srt.strip())

    lines_out   = []
    emoji_lines = []
    used_ts     = []

    for block in blocks:
        blines = block.strip().splitlines()
        time_line = next((l for l in blines if "-->" in l), None)
        if not time_line: continue
        text = " ".join(l for l in blines if "-->" not in l and not l.strip().isdigit())
        t_start, t_end = [x.strip() for x in time_line.split("-->")]
        ass_s = srt_time_to_ass(t_start)
        ass_e = srt_time_to_ass(t_end)
        lines_out.append(f"Dialogue: 0,{ass_s},{ass_e},Sub,,0,0,0,,{text.strip()}")

        # Emoji
        emoji = _find_emoji(text)
        if emoji:
            def _ts(t):
                try:
                    h,m,s = t.split(":")
                    return int(h)*3600+int(m)*60+float(s.replace(",","."))
                except: return 0
            ts = _ts(t_start)
            if not any(abs(ts-u)<2.5 for u in used_ts):
                used_ts.append(ts)
                # Emoji centralizado acima da legenda
                emoji_lines.append(
                    f"Dialogue: 0,{ass_s},{ass_e},Emoji,,0,0,0,,{{\\an5\\pos(540,1500)}}{emoji}"
                )

    # Cabeçalho ASS
    fn    = style["FontName"]
    fs    = font_size
    pc    = style["PrimaryColour"]
    oc    = style["OutlineColour"]
    bold  = style["Bold"]
    ol    = style["Outline"]
    sh    = style["Shadow"]
    bs    = style["BorderStyle"]

    ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{fn},{fs},{pc},&H00000000,{oc},&H00000000,{bold},0,0,0,100,100,0,0,{bs},{ol},{sh},{alignment},20,20,{margin_v},1
Style: Emoji,Arial,100,&H00FFFFFF,&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,3,5,20,20,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with open(ass_path,"w",encoding="utf-8") as f:
        f.write(ass_header)
        for l in lines_out:
            f.write(l+"\n")
        for l in emoji_lines:
            f.write(l+"\n")
    print(f"[editor] ASS gerado: {len(lines_out)} falas, {len(emoji_lines)} emojis")

# ── Efeitos ───────────────────────────────────────────────────────────────────
def _apply_effect(src, dst, effect, ffmpeg_exe):
    filters = {
        "Vinheta":                  "vignette=PI/4",
        "Saturação +":              "eq=saturation=1.8:contrast=1.1",
        "Contraste Cinematográfico":"eq=contrast=1.3:brightness=-0.05:saturation=1.2",
        "Filtro Vintage":           "curves=vintage",
        "Filtro Quente":            "colortemperature=temperature=5500",
        "Brilho + Contraste":       "eq=brightness=0.05:contrast=1.2",
    }
    vf = filters.get(effect)
    if not vf:
        shutil.copy2(src, dst)
        return
    _run([
        ffmpeg_exe,"-y","-i",src,"-vf",vf,
        "-c:v","libx264","-preset","medium","-crf","17",
        "-profile:v","high","-pix_fmt","yuv420p",
        "-c:a","copy","-movflags","+faststart",dst,
    ], f"Efeito {effect}")

def _apply_mirror(src, dst, ffmpeg_exe):
    _run([
        ffmpeg_exe,"-y","-i",src,"-vf","hflip",
        "-c:v","libx264","-preset","medium","-crf","17",
        "-pix_fmt","yuv420p","-c:a","copy",dst,
    ], "Mirror")

def _apply_music(src, dst, music_path, music_vol, orig_vol, ffmpeg_exe):
    _run([
        ffmpeg_exe,"-y","-i",src,"-i",music_path,
        "-filter_complex",
        f"[0:a]volume={orig_vol}[a0];[1:a]volume={music_vol},aloop=loop=-1:size=2e+09[a1];[a0][a1]amix=inputs=2:duration=first[aout]",
        "-map","0:v","-map","[aout]",
        "-c:v","copy","-c:a","aac","-b:a","192k","-ar","48000",
        "-movflags","+faststart",dst,
    ], "Música")

# ── Create Short ──────────────────────────────────────────────────────────────
def create_short(
    video_path, start, end, output_path,
    width=1080, height=1920,
    effect="Nenhum",
    enable_subtitles=True,
    subtitle_style="Amarela + Borda Preta",
    subtitle_position="Baixo",
    audio_boost=0,
    ffmpeg_exe="ffmpeg",
    music_files=None,
    music_volume=0.10,
    original_volume=1.0,
    url="",
    words_per_line=2,
    font_size=80,
    logo_path=None,
    logo_position="",
    logo_size_pct=12,
    video_title="",
    mirror=False,
    whisper_model="tiny",
    broll_dir="",
    use_dynamic_zoom=False,
):
    duration = end - start

    with tempfile.TemporaryDirectory() as tmp:
        # 1. Cortar
        cut = os.path.join(tmp, "cut.mp4")
        _run([
            ffmpeg_exe,"-y","-ss",str(start),"-i",video_path,"-t",str(duration),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,"
                   f"crop={width}:{height},"
                   f"unsharp=5:5:0.8:3:3:0",
            "-c:v","libx264","-preset","medium","-crf","17",
            "-profile:v","high","-level","4.2","-pix_fmt","yuv420p",
            "-c:a","aac","-b:a","192k","-ar","48000",
            "-movflags","+faststart",cut,
        ], "Corte")
        current = cut

        # 2. Efeito
        if effect and effect != "Nenhum":
            eff = os.path.join(tmp,"effect.mp4")
            try: _apply_effect(current, eff, effect, ffmpeg_exe); current = eff
            except Exception as e: print(f"[editor] Efeito erro: {e}")

        # 3. Espelho
        if mirror:
            mir = os.path.join(tmp,"mirror.mp4")
            try: _apply_mirror(current, mir, ffmpeg_exe); current = mir
            except Exception as e: print(f"[editor] Mirror erro: {e}")

        # 4. Música
        if music_files:
            music = random.choice(music_files)
            mus = os.path.join(tmp,"music.mp4")
            try: _apply_music(current, mus, music, music_volume, original_volume, ffmpeg_exe); current = mus
            except Exception as e: print(f"[editor] Música erro: {e}")

        # 5. Legenda + Emoji
        if enable_subtitles:
            srt_path = os.path.join(tmp,"sub.srt")
            srt_ok   = _whisper_srt(current, srt_path, ffmpeg_exe, words_per_line, whisper_model)
            if srt_ok:
                sub = os.path.join(tmp,"subtitled.mp4")
                try:
                    _burn_subtitle(current, srt_path, sub, subtitle_style, subtitle_position, ffmpeg_exe, font_size)
                    current = sub
                    print("[editor] ✅ Legenda + emoji OK!")
                except Exception as e:
                    print(f"[editor] Legenda erro: {e}")
            else:
                print("[editor] Whisper não gerou legenda")

        shutil.copy2(current, output_path)
        print(f"[editor] ✅ Short pronto: {output_path}")
