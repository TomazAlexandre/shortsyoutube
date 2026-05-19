"""
downloader.py - versao final estavel sem cookies
"""
import yt_dlp, os, subprocess, glob

QUALITY_FORMATS = {
    "💎 Máxima (4K)":         "bestvideo[height<=2160]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
    "🔥 1080p (Recomendado)": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "⚡ 720p (Rápido)":       "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]",
    "💨 480p (Leve)":         "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]",
}

def _resolve_quality(q):
    alias = {"🔥 1080p (Melhor)": "🔥 1080p (Recomendado)"}
    return alias.get(q, q) if q not in QUALITY_FORMATS else q

def _quality_height(q):
    for k, v in {"4K":2160,"2160":2160,"1080":1080,"720":720,"480":480}.items():
        if k in q: return v
    return 1080

def _find_ffmpeg(ffmpeg_dir=""):
    if ffmpeg_dir and os.path.isdir(ffmpeg_dir):
        for name in ["ffmpeg.exe","ffmpeg"]:
            p = os.path.join(ffmpeg_dir, name)
            if os.path.isfile(p): return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except: pass
    return "ffmpeg"

def get_video_info(url):
    try:
        with yt_dlp.YoutubeDL({"quiet":True,"no_warnings":True,"skip_download":True}) as ydl:
            info = ydl.extract_info(url, download=False)
        dur = info.get("duration",0)
        h,m,s = dur//3600,(dur%3600)//60,dur%60
        vc = info.get("view_count",0)
        return {
            "title": info.get("title","N/A"),
            "uploader": info.get("uploader","N/A"),
            "duration": dur,
            "duration_str": f"{h:02d}:{m:02d}:{s:02d}" if h>0 else f"{m:02d}:{s:02d}",
            "view_count": vc,
            "view_count_str": f"{vc/1_000_000:.1f}M" if vc>=1_000_000 else f"{vc/1_000:.0f}K" if vc>=1_000 else str(vc),
            "thumbnail": info.get("thumbnail"),
            "heatmap": info.get("heatmap"),
        }
    except Exception as e:
        print(f"[downloader] Erro info: {e}")
        return None

def _get_video_id(url):
    try:
        with yt_dlp.YoutubeDL({"quiet":True,"no_warnings":True,"skip_download":True}) as ydl:
            return ydl.extract_info(url, download=False).get("id","video")
    except: return "video"

def download_youtube_video(url, output_dir, ffmpeg_dir="", quality="🔥 1080p (Recomendado)"):
    os.makedirs(output_dir, exist_ok=True)
    quality    = _resolve_quality(quality)
    height     = _quality_height(quality)
    ffmpeg_exe = _find_ffmpeg(ffmpeg_dir)
    video_id   = _get_video_id(url)
    final      = os.path.join(output_dir, f"{video_id}.mp4")

    print(f"[downloader] {quality} | ffmpeg: {os.path.basename(ffmpeg_exe)}")

    # Tentativa 1: melhor formato disponivel sem restricao de codec
    pre = os.path.join(output_dir, f"{video_id}_pre.mp4")
    try:
        with yt_dlp.YoutubeDL({
            "format": f"best[height<={height}]/best",
            "outtmpl": pre,
            "quiet": False, "no_warnings": True, "noplaylist": True,
            "merge_output_format": "mp4",
        }) as ydl:
            ydl.download([url])
        if os.path.exists(pre) and os.path.getsize(pre) > 500_000:
            os.replace(pre, final)
            print(f"[downloader] ✅ OK (pre-mesclado)")
            return final
        if os.path.exists(pre): os.remove(pre)
    except Exception as e:
        print(f"[downloader] Tentativa 1 falhou: {e}")

    # Tentativa 2: video+audio separados + merge
    print(f"[downloader] Baixando separado...")
    vid = os.path.join(output_dir, f"{video_id}_v")
    aud = os.path.join(output_dir, f"{video_id}_a")

    try:
        with yt_dlp.YoutubeDL({
            "format": f"bestvideo[height<={height}]/bestvideo",
            "outtmpl": vid+".%(ext)s",
            "quiet": False, "no_warnings": True, "noplaylist": True,
        }) as ydl:
            ydl.download([url])

        with yt_dlp.YoutubeDL({
            "format": "bestaudio[ext=m4a]/bestaudio",
            "outtmpl": aud+".%(ext)s",
            "quiet": False, "no_warnings": True, "noplaylist": True,
        }) as ydl:
            ydl.download([url])

        # Encontrar arquivos baixados
        vid_files = glob.glob(vid+".*")
        aud_files = glob.glob(aud+".*")
        if not vid_files or not aud_files:
            raise RuntimeError("Arquivos de video/audio nao encontrados apos download")

        r = subprocess.run(
            [ffmpeg_exe, "-y", "-i", vid_files[0], "-i", aud_files[0],
             "-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart", final],
            capture_output=True, text=True
        )
        for f in vid_files+aud_files:
            if os.path.exists(f): os.remove(f)

        if r.returncode != 0:
            raise RuntimeError(f"Merge falhou: {r.stderr[-300:]}")

        print(f"[downloader] ✅ OK (merge)")
        return final

    except Exception as e:
        raise RuntimeError(f"Download falhou: {e}")
