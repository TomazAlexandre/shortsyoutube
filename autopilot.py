"""
autopilot.py v2
Pipeline:
1. PROCESSA tudo agora (download + corte + legenda + efeitos)
2. AGENDA publicação para os horários definidos
3. Log em tempo real de cada etapa
"""

import sys, os
from pathlib import Path
APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

import json, time, random, datetime, schedule, threading, glob
import importlib.util

def _load(name):
    spec = importlib.util.spec_from_file_location(name, APP_DIR / "core" / f"{name}.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

downloader_mod = _load("downloader")
analyzer_mod   = _load("analyzer")
editor_mod     = _load("editor")
uploader_mod   = _load("uploader")

import pickle as _pickle

def _yt_upload(ch_id, secrets_path, video_path, title, description, tags, privacy, publish_at=""):
    """Chama a API do YouTube diretamente — sem cache do uploader.py."""
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
              "https://www.googleapis.com/auth/youtube.readonly"]

    token_path = str(APP_DIR / "yt_tokens" / f"{ch_id}.pkl")
    creds = None

    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = _pickle.load(f)

    # Refresh se expirado
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_path, "wb") as f:
                _pickle.dump(creds, f)
        except Exception as refresh_err:
            print(f"[upload] Token refresh falhou: {refresh_err}")
            creds = None

    # Se ainda inválido, reautenticar
    if not creds or not creds.valid:
        if not os.path.exists(secrets_path):
            raise RuntimeError(f"client_secrets.json não encontrado: {secrets_path}")
        flow  = InstalledAppFlow.from_client_secrets_file(secrets_path, SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")
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
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True,
                            chunksize=5*1024*1024)
    request = service.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    vid_id = response.get("id")
    return {"id": vid_id, "url": f"https://youtube.com/shorts/{vid_id}"}

CONFIG_FILE   = str(APP_DIR / "autopilot_config.json")
HISTORY_FILE  = str(APP_DIR / "autopilot_history.json")
QUEUE_FILE    = str(APP_DIR / "upload_queue.json")


SCHEDULER_FILE = str(APP_DIR / "scheduler_state.json")

def load_scheduler_state() -> dict:
    """Carrega estado do agendador diário."""
    if not os.path.exists(SCHEDULER_FILE):
        return {"enabled": False, "run_time": "08:00", "last_runs": {}}
    with open(SCHEDULER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_scheduler_state(state: dict):
    with open(SCHEDULER_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def already_ran_today(niche: str) -> bool:
    """Verifica se já rodou hoje para este nicho."""
    state = load_scheduler_state()
    today = datetime.date.today().isoformat()
    return state.get("last_runs", {}).get(niche) == today

def mark_ran_today(niche: str):
    """Marca que já rodou hoje para este nicho."""
    state = load_scheduler_state()
    if "last_runs" not in state:
        state["last_runs"] = {}
    state["last_runs"][niche] = datetime.date.today().isoformat()
    save_scheduler_state(state)

def get_active_niches() -> list:
    """Retorna lista de nichos que têm canais configurados."""
    gf = APP_DIR / "channel_groups.json"
    if not gf.exists():
        return ["geral"]
    groups = json.loads(gf.read_text(encoding="utf-8"))
    # Só nichos com pelo menos 1 canal autenticado
    active = []
    for niche, channels in groups.items():
        tokens_dir = APP_DIR / "yt_tokens"
        has_auth = any(
            (tokens_dir / f"{c['id']}.pkl").exists()
            for c in channels
        )
        if has_auth:
            active.append(niche)
    return active if active else ["geral"]

def run_all_niches(base_cfg: dict, log_callback=None):
    """Roda o autopiloto para todos os nichos ativos, um por vez."""
    def log(msg):
        if log_callback: log_callback(msg)
        print(msg)

    niches = get_active_niches()
    log(f"🌐 MODO AUTÔNOMO — {len(niches)} nicho(s) ativo(s): {', '.join(niches)}")
    log("=" * 50)

    for niche in niches:
        if already_ran_today(niche):
            log(f"⏭️ [{niche}] Já executado hoje — pulando")
            continue

        log(f"\n🎯 Iniciando nicho: {niche.upper()}")
        log("-" * 40)

        # Configurar para este nicho
        niche_cfg = dict(base_cfg)
        niche_cfg["niche"] = niche

        try:
            results = run_autopilot(niche_cfg, log_callback=log_callback)
            mark_ran_today(niche)
            log(f"✅ [{niche}] Concluído: {results.get('processed',0)} short(s) gerado(s), {results.get('uploaded',0)} enviado(s)")
        except Exception as e:
            log(f"❌ [{niche}] Erro: {e}")
            # Não marca como concluído para tentar de novo

    log("\n" + "=" * 50)
    log("🏁 TODOS OS NICHOS PROCESSADOS!")
    return True

def load_queue() -> list:
    """Carrega fila de uploads pendentes."""
    if not os.path.exists(QUEUE_FILE):
        return []
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_to_queue(item: dict):
    """Salva item na fila de pendentes."""
    queue = load_queue()
    # Evitar duplicatas pelo path
    if not any(q["path"] == item["path"] and q["channel_id"] == item["channel_id"] for q in queue):
        queue.append(item)
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)

def remove_from_queue(path: str, channel_id: str):
    """Remove item da fila após upload bem-sucedido."""
    queue = [q for q in load_queue() if not (q["path"] == path and q["channel_id"] == channel_id)]
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)

def load_history() -> set:
    """Carrega URLs de podcasts já processados."""
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("urls", []))

def save_history(urls: set):
    """Salva URLs processadas no histórico."""
    existing = load_history()
    all_urls  = list(existing | urls)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump({"urls": all_urls, "total": len(all_urls),
                   "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")},
                  f, ensure_ascii=False, indent=2)

def clear_history():
    """Limpa o histórico (usar com cuidado)."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump({"urls": [], "total": 0}, f)

DEFAULT_CONFIG = {
    "enabled": False,
    "run_time": "08:00",
    "openai_key": "",
    "ffmpeg_path": "",
    "clips_per_podcast": 2,   # 2 cortes por podcast — foco em qualidade
    "clip_duration": 60,
    "skip_intro": 720,  # ignorar 12min iniciais (intro/patrocinio)
    "effect": "Nenhum",
    "enable_subtitles": True,
    "subtitle_style": "Amarela + Borda Preta",
    "font_size": 69,
    "words_per_line": 2,
    "whisper_model": "tiny",
    "music_folder": str(APP_DIR / "musicas"),
    "mirror": True,
    "publish_schedules": ["12:00", "15:00", "18:00", "21:30"],
    "publish_privacy": "public",
    "description_template": "",
    "max_podcasts_per_day": 1,  # 1 podcast por dia — foco em qualidade
    "niche": "geral",              # geral | politica | policia_relatos | futebol
}

TOP_PODCAST_QUERIES = [
    "flow podcast", "podpah", "inteligência ltda", "ticaracaticast",
    "jovem pan podcast", "xadrez verbal", "nerdcast", "café da manhã podcast",
    "quem pode pode podcast", "bill podcast", "Venus podcast", "primo pobre podcast",
]

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def get_music_files(music_folder: str) -> list:
    if not os.path.isdir(music_folder):
        return []
    return [
        os.path.join(music_folder, f)
        for f in os.listdir(music_folder)
        if f.lower().endswith((".mp3", ".m4a", ".wav", ".ogg"))
    ]

def _find_ffmpeg(ffmpeg_dir: str) -> str:
    if not ffmpeg_dir:
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except:
            return "ffmpeg"
    for name in ["ffmpeg.exe", "ffmpeg"]:
        p = os.path.join(ffmpeg_dir, name)
        if os.path.isfile(p):
            return p
    matches = glob.glob(os.path.join(ffmpeg_dir, "**", "ffmpeg.exe"), recursive=True)
    return matches[0] if matches else "ffmpeg"


# ── Busca podcasts ────────────────────────────────────────────────────────────

def search_top_podcasts(max_results: int = 10, log=None, niche: str = "geral") -> list[dict]:
    import yt_dlp

    _NICHES = {
        "geral": [
            "flow podcast", "podpah", "inteligência ltda podcast",
            "ticaracaticast podcast", "quem pode pode podcast",
            "bill podcast brasil", "venus podcast brasil",
            "primo pobre podcast", "papo de homem podcast",
            "café da manhã podcast folha", "inteligência ltda",
            "podpah episodio", "flow podcast completo",
            "lord podcast brasil", "overtime podcast brasil",
            "podcast brasil entretenimento", "podcast conversa brasil",
            "podcast famosos brasil", "renato cariani podcast",
            "eli coruja podcast", "choquei podcast",
            "podcast de humor brasil", "mano a mano podcast",
            "programa do porchat", "lady night podcast",
            "podpeople podcast", "mundo podcast brasil",
            "irmãos podcast brasil", "brascast podcast",
            "posto 9 podcast", "compilado podcast brasil",
        ],
        "politica": [
            "jovem pan podcast política", "xadrez verbal podcast",
            "os pingos nos is podcast", "direto ao ponto podcast",
            "poder360 podcast", "antagonista podcast",
            "brasil paralelo podcast", "inteligência ltda política",
            "renova mídia podcast", "revista oeste podcast",
            "joel jota podcast", "pablo marçal podcast",
            "nikolas ferreira podcast", "sergio moro podcast",
            "podcast governo brasil", "podcast congresso brasil",
            "podcast economia brasil", "podcast direita brasil",
            "podcast esquerda brasil", "podcast eleições brasil",
            "podcast stf brasil", "lula podcast entrevista",
            "bolsonaro podcast entrevista", "podcast reforma brasil",
            "podcast constituição brasil", "pedro bial podcast",
            "podcast jornalismo brasil", "podcast política brasileira",
            "podcast presidente brasil", "cnn brasil podcast",
        ],
        "policia_relatos": [
            "podcast policial brasil", "relatos verdadeiros podcast brasil",
            "podcast crimes reais brasil", "investigação criminal podcast",
            "delegacia podcast brasil", "crimes podcast brasil",
            "podcast caso real brasil", "aqui jaz podcast",
            "podcast true crime brasil", "modus operandi podcast brasil",
            "podcast serial killer brasil", "podcast mistério brasil",
            "podcast assassinato brasil", "podcast delegado brasil",
            "podcast penitenciária brasil", "podcast presídio brasil",
            "podcast policia civil brasil", "podcast sequestro brasil",
            "podcast tráfico brasil", "podcast caso não resolvido",
            "podcast feminicídio brasil", "podcast violência brasil",
            "podcast investigação brasil", "podcast roubo brasil",
            "podcast bandido brasil", "podcast tribunal brasil",
            "podcast juri brasil", "podcast criminalidade brasil",
            "dark side podcast brasil", "podcast facção brasil",
        ],
        "esportes": [
            # Futebol
            "charla podcast","posse de bola podcast","boleiragem podcast",
            "gripando podcast","fut podcast brasil","resenha gol podcast",
            "podcast brasileirao","podcast libertadores brasil",
            "podcast champions league brasil","podcast premier league brasil",
            "podcast la liga brasil","podcast serie a brasil",
            "podcast copa do brasil","podcast copa america",
            "podcast copa do mundo 2026","podcast bola na area",
            "podcast esquadrão podcast","podcast bola dividida",
            "podcast camisa 10 podcast","podcast futebol de verdade",
            # Times brasileiros
            "podcast flamengo","podcast corinthians","podcast palmeiras",
            "podcast sao paulo futebol","podcast atletico mineiro",
            "podcast gremio","podcast santos","podcast botafogo",
            "podcast vasco","podcast cruzeiro","podcast internacional",
            "podcast atletico paranaense","podcast fluminense",
            "podcast sport recife","podcast bahia","podcast ceara",
            "podcast fortaleza","podcast goias","podcast coritiba",
            # Jogadores
            "podcast neymar","podcast vini junior","podcast rodrygo",
            "podcast endrick","podcast raphinha","podcast gabriel barbosa",
            "podcast lucas paqueta","podcast thiago silva",
            "podcast ederson","podcast alisson podcast",
            # MMA / Luta
            "podcast mma brasil","podcast ufc brasil","podcast boxe brasileiro",
            "podcast luta livre brasil","podcast muay thai brasil",
            "podcast jiu jitsu brasil","podcast karate brasil",
            "podcast alex poatan","podcast jose aldo podcast",
            "podcast anderson silva","podcast charles oliveira",
            "podcast deiveson figueiredo","podcast glover teixeira",
            # Basquete
            "podcast basquete brasil","podcast nba brasil",
            "podcast nbb podcast","podcast basquete feminino brasil",
            "podcast lakers brasil","podcast celtics brasil",
            # Outros esportes
            "podcast tenis brasil","podcast roger federer brasil",
            "podcast rafael nadal brasil","podcast novak djokovic brasil",
            "podcast carlos alcaraz brasil","podcast iga swiatek brasil",
            "podcast atletismo brasil","podcast natacao brasil",
            "podcast volei brasil","podcast olimpiadas brasil",
            "podcast formula 1 brasil","podcast motogp brasil",
            "podcast ciclismo brasil","podcast tour de france brasil",
            "podcast crossfit brasil","podcast bodybuilding brasil",
            "podcast fisiculturismo brasil","podcast powerlifting brasil",
            "podcast corrida brasil","podcast maratona brasil",
            "podcast triathlon brasil","podcast surf brasil",
            "podcast skate brasil","podcast gymnastica brasil",
            "podcast esporte americano brasil","podcast nfl brasil",
            "podcast nhl brasil","podcast mlb brasil",
            "podcast esporte olimpico brasil","podcast paralimpiadas brasil",
        ],
        "futebol": [
            "charla podcast futebol","posse de bola podcast",
            "boleiragem podcast","gripando podcast futebol",
            "seleção sportv podcast","fut podcast brasil",
            "resenha do esquema podcast","bola na area podcast",
            "podcast flamengo","podcast corinthians","podcast palmeiras",
            "podcast sao paulo","podcast atletico mineiro","podcast gremio",
            "podcast santos","podcast botafogo","podcast vasco",
            "podcast cruzeiro","podcast internacional","podcast fluminense",
            "podcast brasileirao 2026","podcast libertadores 2026",
            "podcast copa do brasil 2026","podcast selecao brasileira",
            "podcast neymar","podcast vini junior","podcast rodrygo",
            "podcast endrick","podcast gabriel barbosa",
            "podcast lucas paqueta","podcast transferencia futebol",
            "podcast mercado bola brasil","podcast futebol europeu brasil",
            "podcast premier league brasil","podcast la liga brasil",
            "podcast champions league brasil","podcast copa do mundo 2026",
            "podcast tecnico futebol","podcast arbitragem futebol",
            "podcast estadio futebol","podcast torcida organizada",
            "podcast futsal brasil","podcast futebol feminino brasil",
            "podcast base futebol brasil","podcast goleiro brasil",
            "podcast atacante brasil","podcast meio campo brasil",
            "podcast zagueiro brasil","podcast lateral brasil",
        ],
        "games": [
            # Podcasts/canais de games conhecidos
            "nerdcast jogos","voxel podcast","rpgcast","jovem nerd jogos",
            "acecast","nerd ao cubo","gamescast","papo de gamer",
            "podcast gamer brasileiro","ultraplays podcast",
            "alcast podcast","gamers club podcast","draft5 podcast",
            "time out podcast games","player select podcast",
            "reload podcast games","start select podcast",
            "checkpoint podcast brasil","save point podcast",
            "game over podcast brasil","insert coin podcast",
            "konami code podcast","cheat code podcast brasil",
            # Streamers brasileiros famosos
            "gaules podcast","casimiro podcast","cellbit podcast",
            "alanzoka podcast","flakes power podcast","nobru podcast",
            "jukes podcast","brtt podcast","mwzera podcast",
            "felps podcast","kscerato podcast","fer podcast",
            "fallen podcast","cold podcast cs","loud podcast",
            "pain podcast games","furia podcast","kabum podcast",
            "loud cortes podcast","qck podcast","tinowns podcast",
            "baiano podcast games","cris eu jogo podcast",
            "zangado podcast","lolito podcast","lacrador podcast",
            "porta dos fundos games","marotex podcast",
            # Jogos populares brasil
            "free fire podcast brasil","league of legends brasil podcast",
            "valorant brasil podcast","cs2 podcast brasil",
            "minecraft podcast brasil","fortnite podcast brasil",
            "genshin impact podcast brasil","fifa podcast brasil",
            "efootball podcast brasil","warzone podcast brasil",
            "apex legends podcast brasil","overwatch podcast brasil",
            "rocket league podcast brasil","rainbow six podcast brasil",
            "pubg podcast brasil","among us podcast brasil",
            "roblox podcast brasil","stumble guys podcast brasil",
            "call of duty podcast brasil","battlefield podcast brasil",
            "god of war podcast brasil","the last of us podcast brasil",
            "zelda podcast brasil","pokemon podcast brasil",
            "diablo podcast brasil","elden ring podcast brasil",
            "cyberpunk podcast brasil","gta podcast brasil",
            "red dead podcast brasil","hogwarts podcast brasil",
            # Categorias / esports
            "esports brasil podcast","cblol podcast","vct brasil podcast",
            "csa brasil podcast","cbcs podcast","re brasil podcast",
            "esports cortes brasil","streamer brasileiro podcast",
            "twitch brasil podcast","youtube gaming brasil podcast",
            "podcast xbox brasil","podcast playstation brasil",
            "podcast nintendo switch brasil","podcast pc gamer brasil",
            "podcast indie games brasil","podcast retrogame brasil",
            "podcast moba brasil","podcast fps brasil",
            "podcast rpg brasil","podcast mmorpg brasil",
            "podcast battle royale brasil","podcast strategy game brasil",
            "podcast pro player brasil","podcast coach games brasil",
            "podcast campeonato games brasil","podcast torneio games brasil",
            "podcast draft games brasil","podcast patch notes brasil",
            "podcast tier list brasil","podcast ranking games brasil",
            "podcast historia games","podcast geek games brasil",
        ],
        "humor": [
            "podcast humor brasil", "porta dos fundos podcast",
            "stand up podcast brasil", "matheus ceará podcast",
            "choque de cultura podcast", "os cabeças podcast",
            "barbixas podcast", "pânico podcast",
            "podcast comédia brasileira", "rafinha bastos podcast",
            "comediante podcast brasil", "diogo defante podcast",
            "léo lins podcast", "fábio porchat podcast",
            "gregório duvivier podcast", "whindersson podcast",
            "podcast youtuber humor brasil", "kéfera podcast",
            "podcast meme brasil", "podcast stand up comedy brasil",
            "podcast piada brasil", "desconstruindo podcast humor",
            "podcast comediante famoso brasil", "podcast risada brasil",
            "podcast zueira brasil", "cortes humor podcast brasil",
            "podcast entretenimento humor", "podcast festival humor",
            "podcast netflix brasil humor", "podcast show humor brasil",
        ],
        "financas": [
            "me poupe podcast", "primo rico podcast",
            "os economistas podcast", "stock pickers podcast",
            "podcast dinheiro brasil", "podcast investimento brasil",
            "podcast renda variável", "podcast renda fixa brasil",
            "podcast criptomoeda brasil", "podcast bitcoin brasil",
            "podcast tesouro direto", "podcast bolsa de valores brasil",
            "podcast empreendedorismo brasil", "podcast startup brasil",
            "podcast imposto renda brasil", "podcast previdência brasil",
            "podcast aposentadoria brasil", "podcast finanças pessoais",
            "podcast liberdade financeira", "podcast milionário brasil",
            "podcast poupar dinheiro", "podcast gastar menos brasil",
            "podcast educação financeira", "podcast economia brasil",
            "podcast banco central brasil", "podcast inflação brasil",
            "rico de pobre podcast", "thulio massimo podcast",
            "podcast warren buffett brasil", "podcast barsi brasil",
        ],
        "tecnologia": [
            "nerdcast tecnologia", "dragões de garagem podcast",
            "hipsters podcast", "podcast programação brasil",
            "startups podcast brasil", "tecnoblog podcast",
            "podcast inteligência artificial brasil", "podcast ia brasil",
            "podcast chatgpt brasil", "podcast python brasil",
            "podcast javascript brasil", "podcast dev brasil",
            "podcast inovação brasil", "podcast silicon valley brasil",
            "podcast apple brasil", "podcast google brasil",
            "podcast microsoft brasil", "podcast android brasil",
            "podcast iphone brasil", "podcast linux brasil",
            "podcast cibersegurança brasil", "podcast hacker brasil",
            "podcast blockchain brasil", "podcast web3 brasil",
            "podcast metaverso brasil", "podcast robótica brasil",
            "podcast elon musk brasil", "podcast tesla brasil",
            "podcast spacex brasil", "podcast tecnologia futuro brasil",
        ],
        "saude": [
            "podcast saúde brasil", "podcast médico brasil",
            "drauzio varella podcast", "podcast nutrição brasil",
            "podcast psicologia brasil", "podcast mental saúde",
            "podcast depressão brasil", "podcast ansiedade brasil",
            "podcast terapia brasil", "podcast bem estar brasil",
            "podcast emagrecer brasil", "podcast dieta brasil",
            "podcast academia podcast", "podcast musculação brasil",
            "podcast corrida brasil", "podcast yoga brasil",
            "podcast meditação brasil", "podcast longevidade brasil",
            "podcast câncer brasil", "podcast diabetes brasil",
            "podcast autoconhecimento brasil", "podcast espiritualidade brasil",
            "podcast mindfulness brasil", "podcast autoestima brasil",
            "podcast relacionamento saudável", "podcast burnout brasil",
            "podcast sono brasil", "podcast alimentação saudável",
            "podcast exercício físico brasil", "podcast medicina brasil",
        ],
        "negocios": [
            "podcast empreendedorismo brasil", "podcast startup brasil",
            "podcast negócios brasil", "podcast liderança brasil",
            "podcast gestão brasil", "podcast marketing brasil",
            "podcast vendas brasil", "podcast ceo brasil",
            "podcast empresário brasil", "podcast mbe podcast",
            "podcast cases brasil", "podcast sucesso empresarial",
            "podcast investidor brasil", "podcast pitch brasil",
            "podcast escala brasil", "podcast franquia brasil",
            "podcast ecommerce brasil", "podcast dropshipping brasil",
            "podcast digital marketing brasil", "podcast growth brasil",
            "podcast produto digital brasil", "podcast curso online brasil",
            "podcast influencer marketing", "podcast personal branding",
            "podcast gestão pessoas brasil", "podcast rh brasil",
            "podcast inovação empresarial", "podcast transformação digital",
            "podcast b2b brasil", "podcast saas brasil",
        ],
        "educacao": [
            "podcast educação brasil", "podcast professor brasil",
            "podcast escola brasil", "podcast universidade brasil",
            "podcast vestibular brasil", "podcast enem podcast",
            "podcast história brasil", "podcast ciência brasil",
            "podcast filosofia brasil", "podcast sociologia brasil",
            "podcast biologia podcast", "podcast física podcast",
            "podcast química podcast", "podcast matemática brasil",
            "podcast literatura brasil", "podcast português brasil",
            "podcast inglês brasil", "podcast idioma podcast",
            "podcast estudo podcast", "podcast concurso público brasil",
            "podcast oab podcast", "podcast medicina faculdade brasil",
            "podcast direito podcast", "podcast psicologia faculdade",
            "podcast economia faculdade", "podcast administração podcast",
            "podcast pedagogia podcast", "podcast ensino podcast",
            "podcast aprendizado podcast", "podcast conhecimento brasil",
        ],
    }
    query_pool = _NICHES.get(niche, _NICHES["geral"])
    queries    = random.sample(query_pool, min(6, len(query_pool)))
    results, seen = [], set()

    # Palavras para filtrar podcasts estrangeiros ou indesejados
    BLOCK_WORDS = [
        "english", "spanish", "español", "gringo", "american",
        "united states", "uk podcast", "french", "german",
        "living the", "how to", "why i", "my life", "the best",
        "i was", "i am", "we are", "this is", "watch this",
        "you need", "must see", "full episode", "interview with",
        "reacts to", "reaction to",
    ]
    
    # Detectar se título parece ser em inglês (maioria das palavras são inglesas)
    def _is_english(text):
        import re
        words = re.findall(r"[a-zA-Z]+", text.lower())
        if len(words) < 3: return False
        # Palavras comuns em inglês que não aparecem em português
        eng_words = {"the","of","and","to","in","is","it","that","was","for",
                     "on","are","as","with","his","they","at","be","this","from",
                     "or","an","but","not","what","all","were","we","when","your",
                     "can","said","there","use","each","she","which","do","how",
                     "their","if","will","up","other","about","out","many","then",
                     "them","these","so","some","her","would","make","like","him",
                     "into","time","has","look","two","more","write","go","see",
                     "number","no","way","could","people","my","than","first","been"}
        eng_count = sum(1 for w in words if w in eng_words)
        return eng_count / len(words) > 0.25  # mais de 25% palavras inglesas
    

    # Filtrar videos com age restriction na busca
    AGE_RESTRICTED = ["age-restricted", "sign in to confirm", "18+", "+18"]

    # Palavras que indicam que NAO é um podcast de conversa
    NOT_PODCAST_WORDS = [
        "top 10", "top10", "ranking", "melhores jogos", "piores jogos",
        "gameplay", "lets play", "let's play", "playthrough", "speedrun",
        "review", "análise de jogo", "trailer", "gameplay completo",
        "montagem", "compilação", "highlights", "melhores momentos do jogo",
    ]

    for query in queries:
        if len(results) >= max_results:
            break
        try:
            if log: log(f"  🔎 Buscando: '{query}'")
            with yt_dlp.YoutubeDL({
                "quiet": True, "no_warnings": True,
                "extract_flat": True,
            }) as ydl:
                search_q = f"ytsearch8:{query}"
                info = ydl.extract_info(search_q, download=False)
                for e in (info.get("entries") or []):
                    url   = f"https://www.youtube.com/watch?v={e.get('id','')}"
                    dur   = e.get("duration", 0) or 0
                    title = (e.get("title") or "").lower()

                    # Filtros: duração mínima 30min, sem palavras bloqueadas
                    views = e.get("view_count", 0) or 0
                    min_views = cfg.get("min_views", 500_000) if "cfg" in dir() else 500_000
                    if url in seen or dur < 1800 or views < min_views:
                        if url not in seen and dur >= 1800 and views < min_views:
                            if log: log(f"  ⛔ Ignorado (poucas views: {views:,}): {e.get('title','')[:40]}")
                        continue
                    if any(bw in title for bw in BLOCK_WORDS) or _is_english(title):
                        if log: log(f"  ⛔ Ignorado (estrangeiro): {e.get('title','')[:50]}")
                        continue
                    if any(bw in title for bw in NOT_PODCAST_WORDS):
                        if log: log(f"  ⛔ Ignorado (não é podcast): {e.get('title','')[:50]}")
                        continue
                    # Pular videos com restrição de idade
                    if e.get("age_limit", 0) and e.get("age_limit", 0) >= 18:
                        if log: log(f"  ⛔ Ignorado (18+): {e.get('title','')[:50]}")
                        continue

                    seen.add(url)
                    results.append({
                        "title":    e.get("title", ""),
                        "url":      url,
                        "channel":  e.get("channel", e.get("uploader", "")),
                        "views":    e.get("view_count", 0) or 0,
                        "duration": dur,
                    })
        except Exception as ex:
            if log: log(f"  ⚠️ Busca erro: {ex}")

    results.sort(key=lambda x: x["views"], reverse=True)
    if log: log(f"  ✅ {len(results)} podcast(s) brasileiros encontrados no nicho: {niche}")
    return results[:max_results]


# ── ChatGPT ───────────────────────────────────────────────────────────────────

def generate_content(title: str, channel: str, openai_key: str, extra_prompt: str = "") -> dict:
    guest = title.split(" - ")[0].strip() if " - " in title else title.split("|")[0].strip()
    podcast_name = channel.strip()

    default = {
        "title":       f"{guest} FALOU TUDO no {podcast_name} 🔥",
        "description": f"🎙️ {guest} no {podcast_name}!\n\nSiga para mais cortes virais! 👊\n\nCréditos: {podcast_name}",
        "hashtags":    f"#shorts #podcast #viral #brasil #{guest.lower().replace(' ','')} #{podcast_name.lower().replace(' ','')}",
        "hook":        f"Você NÃO vai acreditar no que {guest} disse... 👀",
    }

    if not openai_key:
        return default

    try:
        import openai
        client = openai.OpenAI(api_key=openai_key)

        system_prompt = """Você gera conteúdo para Shorts de cortes de podcast no YouTube.
Responda APENAS JSON com este formato exato:
{"titulo": "...", "descricao": "...", "hashtags": "...", "hook": "..."}

Regras:
- TITULO: curto, clickbait, CAIXA ALTA nas partes importantes, emojis, max 80 chars
- DESCRICAO: viral, SEO, frase chamativa no início, convite para seguir, créditos no final
- HASHTAGS: 10 a 15 hashtags (#shorts obrigatório, nome do convidado, podcast, termos virais)
- HOOK: frase ultra curta para os primeiros 2 segundos, altamente chamativa
- Linguagem simples, direta, foco em viralização
- Sempre emojis estratégicos"""

        user_msg = f"{guest} - {podcast_name}"
        if extra_prompt:
            user_msg += f"\n\n{extra_prompt}"

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}],
            max_tokens=400, temperature=0.85,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        return {
            "title":       data.get("titulo",   default["title"])[:100],
            "description": data.get("descricao", default["description"])[:5000],
            "hashtags":    data.get("hashtags",  default["hashtags"]),
            "hook":        data.get("hook",       default["hook"]),
        }
    except Exception as e:
        print(f"[autopilot] ChatGPT erro: {e}")
        return default


def generate_description(title, channel, openai_key, extra_prompt=""):
    c = generate_content(title, channel, openai_key, extra_prompt)
    return c["description"] + "\n\n" + c["hashtags"]


# ── Pipeline principal ────────────────────────────────────────────────────────

def run_autopilot(cfg: dict, log_callback=None) -> dict:
    """
    Fase 1 — PROCESSA todos os vídeos agora
    Fase 2 — AGENDA publicação para os horários configurados
    """
    logs = []
    def log(msg, emoji=""):
        full = f"{emoji} {msg}" if emoji else msg
        print(f"[autopilot] {full}")
        logs.append(full)
        if log_callback:
            log_callback(full)

    t0 = time.time()
    results = {"processed": 0, "uploaded": 0, "errors": [], "videos": [], "logs": logs}

    def elapsed():
        s = int(time.time() - t0)
        return f"{s//60:02d}:{s%60:02d}"

    log("="*50)
    log(f"🤖 AUTOPILOTO INICIADO — {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    log("="*50)

    ffmpeg_exe = _find_ffmpeg(cfg.get("ffmpeg_path",""))
    # Fallback: imageio_ffmpeg embutido
    if not os.path.isfile(ffmpeg_exe):
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            log(f"🔧 FFmpeg via imageio: {Path(ffmpeg_exe).name}")
        except:
            log("⚠️ FFmpeg não encontrado — configure o caminho na aba Geral")
    else:
        log(f"🔧 FFmpeg: {Path(ffmpeg_exe).name}")
    music_files = get_music_files(cfg.get("music_folder",""))
    # Carregar canais do grupo do nicho selecionado
    niche = cfg.get("niche", "geral")
    groups_file = APP_DIR / "channel_groups.json"
    if groups_file.exists():
        import json as _json2
        all_groups = _json2.loads(groups_file.read_text(encoding="utf-8"))
        niche_channels = all_groups.get(niche, [])
        channels = [c for c in niche_channels
                    if os.path.exists(os.path.join(str(APP_DIR / "yt_tokens"), f"{c['id']}.pkl"))]
        if not channels:
            # Fallback: canais antigos do channels.json
            channels = [c for c in uploader_mod.load_channels() if uploader_mod.is_authenticated(c["id"])]
    else:
        channels = [c for c in uploader_mod.load_channels() if uploader_mod.is_authenticated(c["id"])]
    schedules_  = cfg.get("publish_schedules", ["12:00","15:00","18:00","21:30"])
    output_dir  = str(APP_DIR / "output_shorts" / datetime.date.today().strftime("%Y-%m-%d"))
    os.makedirs(output_dir, exist_ok=True)

    log(f"🔧 FFmpeg: {Path(ffmpeg_exe).name}")
    log(f"🎵 Músicas: {len(music_files)}")
    log(f"📡 Canais: {len(channels)}")
    log(f"📅 Horários: {', '.join(schedules_)}")
    log("")

    if not channels:
        log("❌ Nenhum canal conectado! Configure em channels.py")
        results["errors"].append("Nenhum canal conectado")
        return results

    # ── FASE 1: Buscar podcasts ───────────────────────────────────────────────
    log("🔍 FASE 1 — Buscando podcasts em alta...")
    niche      = cfg.get("niche", "geral")
    max_needed = cfg.get("max_podcasts_per_day", 4)
    log(f"🎯 Nicho: {niche} | Meta: {max_needed} podcast(s)")

    # Carregar histórico
    history = load_history()
    log(f"📚 Histórico: {len(history)} podcast(s) já processado(s)")

    podcasts     = []
    tentativa    = 0
    max_tentativas = 5

    while len(podcasts) < max_needed and tentativa < max_tentativas:
        tentativa += 1
        # A cada tentativa busca mais resultados
        search_size = max_needed * (4 + tentativa * 2)
        log(f"🔎 Tentativa {tentativa}/{max_tentativas} — buscando {search_size} candidatos...")

        candidates = search_top_podcasts(
            max_results=search_size,
            log=log,
            niche=niche
        )

        # Filtrar já processados e já encontrados nesta rodada
        found_urls = {p["url"] for p in podcasts}
        novos = [
            p for p in candidates
            if p["url"] not in history and p["url"] not in found_urls
        ]

        skipped = len(candidates) - len(novos)
        if skipped > 0:
            log(f"⏭️  {skipped} ignorado(s) — já processados")

        podcasts.extend(novos)
        podcasts = podcasts[:max_needed]  # nunca passar do limite

        if len(podcasts) >= max_needed:
            break

        if tentativa < max_tentativas:
            log(f"⚠️ Só {len(podcasts)}/{max_needed} encontrado(s) — tentando mais...")

    # Se mesmo assim não achou o suficiente, avisa mas continua com o que tem
    if len(podcasts) < max_needed:
        if len(podcasts) == 0:
            log("⚠️ Nenhum podcast novo encontrado para este nicho!")
            log("   Histórico preservado. Considere adicionar mais queries ao nicho.")
        else:
            log(f"⚠️ Só foi possível encontrar {len(podcasts)}/{max_needed} podcast(s) novos")
            log("   Considere limpar o histórico na aba ⚙️ Geral")

    if not podcasts:
        log("❌ Nenhum podcast encontrado. Abortando.")
        return results

    log(f"✅ {len(podcasts)}/{max_needed} podcast(s) encontrado(s) [{elapsed()}]")
    log("")

    # ── FASE 2: Processar todos os vídeos ────────────────────────────────────
    log("✂️  FASE 2 — Processando vídeos...")
    all_generated = []
    effects_pool  = ["Vinheta","Saturação +","Contraste Cinematográfico","Filtro Quente","Filtro Vintage","Brilho + Contraste"]

    for pod_idx, podcast in enumerate(podcasts):
        log(f"\n📺 Podcast {pod_idx+1}/{len(podcasts)}: {podcast['title'][:55]}")
        log(f"   Canal: {podcast['channel']} | Views: {podcast['views']:,}")

        try:
            # Download
            log(f"   📥 Baixando vídeo... [{elapsed()}]")
            try:
                video_path = downloader_mod.download_youtube_video(
                    url=podcast["url"], output_dir=output_dir,
                    ffmpeg_dir=cfg.get("ffmpeg_path",""),
                    quality="🔥 1080p (Recomendado)",
                )
            except Exception as dl_err:
                err_str = str(dl_err).lower()
                if "not a bot" in err_str or "confirm" in err_str:
                    log(f"   ⛔ Pulando: YouTube bloqueou (detecção de bot) — tente exportar cookies")
                elif "age" in err_str:
                    log(f"   ⛔ Pulando: vídeo com restrição de idade")
                elif "format" in err_str or "not available" in err_str:
                    log(f"   ⛔ Pulando: formato não disponível neste vídeo")
                else:
                    log(f"   ❌ Erro no download: {str(dl_err)[:100]}")
                save_history({podcast["url"]})
                continue
            log(f"   ✅ Download OK: {Path(video_path).name} [{elapsed()}]")

            # Heatmap
            log(f"   📊 Analisando heatmap...")
            segments = analyzer_mod.find_most_watched_segments(
                url=podcast["url"],
                num_clips=cfg.get("clips_per_podcast",1),
                clip_duration=cfg.get("clip_duration",60),
                skip_intro_seconds=cfg.get("skip_intro",120),
            )
            log(f"   🔥 {len(segments)} segmento(s) encontrado(s)")

            # Cada clipe vai para um canal diferente
            # Canal é atribuído dentro do loop de segmentos

            # Gerar cada clipe
            for seg_idx, seg in enumerate(segments):
                # Canal específico para este clipe (1 clipe = 1 canal)
                ch_idx    = seg_idx % len(channels)
                channel   = channels[ch_idx]
                logo_path = channel.get("logo_path","")

                effect         = random.choice(effects_pool)
                subtitle_style = random.choice([
                    "Amarela + Borda Preta",
                    "Branca + Borda Preta",
                    "Gradiente Rosa/Roxo",
                    "Laranja + Borda Preta",
                ])
                short_name = f"pod{pod_idx+1}_clip{seg_idx+1}_{channel['id']}.mp4"
                out_path   = os.path.join(output_dir, short_name)

                log(f"   ✂️  Clipe {seg_idx+1} → Canal: {channel['name']} | {seg['start_str']} | {effect} | legenda: {subtitle_style[:6]} [{elapsed()}]")

                editor_mod.create_short(
                    video_path=video_path,
                    start=seg["start"], end=seg["end"],
                    output_path=out_path,
                    width=1080, height=1920,
                    effect=effect,
                    enable_subtitles=cfg.get("enable_subtitles",True),
                    subtitle_style=subtitle_style,
                    subtitle_position="Baixo",
                    audio_boost=0,
                    ffmpeg_exe=ffmpeg_exe,
                    music_files=music_files or None,
                    music_volume=cfg.get("music_volume", 0.10),
                    original_volume=1.0,
                    url=podcast["url"],
                    words_per_line=cfg.get("words_per_line",2),
                    font_size=cfg.get("font_size",69),
                    logo_path=logo_path if os.path.exists(logo_path or "") else None,
                    logo_position="Canto superior direito",
                    logo_size_pct=12,
                    video_title=podcast["title"][:55],
                    mirror=cfg.get("mirror",True),
                    whisper_model=cfg.get("whisper_model","tiny"),
                    broll_dir=cfg.get("broll_dir", str(APP_DIR / "broll_images")),
                    use_dynamic_zoom=cfg.get("use_dynamic_zoom",False),
                )

                log(f"   ✅ Clipe {seg_idx+1} pronto! [{elapsed()}]")
                results["processed"] += 1

                # ChatGPT — gera titulo unico por clipe (varia levemente)
                log(f"   🤖 Gerando título para clipe {seg_idx+1}...")
                _extra = cfg.get("description_template","")
                _extra_clip = f"{_extra}\nEste é o clipe {seg_idx+1} do podcast. Varie o título em relação aos outros clipes do mesmo episódio."
                ai = generate_content(
                    title=podcast["title"], channel=podcast["channel"],
                    openai_key=cfg.get("openai_key",""),
                    extra_prompt=_extra_clip,
                )
                # Validar que titulo nao é duplicado
                _existing_titles = [g["title"] for g in all_generated if g["podcast"]["url"] == podcast["url"]]
                if ai["title"] in _existing_titles:
                    ai["title"] = ai["title"].rstrip("!") + f" #{seg_idx+1}! 🔥"
                log(f"   📌 Título: {ai['title']}")
                log(f"   🎣 Hook: {ai['hook']}")

                all_generated.append({
                    "path":        out_path,
                    "title":       ai["title"],
                    "description": ai["description"] + "\n\n" + ai["hashtags"],
                    "hook":        ai["hook"],
                    "channel_obj": channel,
                    "podcast":     podcast,
                })

        except Exception as e:
            log(f"   ❌ ERRO no podcast {pod_idx+1}: {e}")
            results["errors"].append(str(e))

    log(f"\n✅ FASE 2 concluída — {results['processed']} short(s) gerado(s) [{elapsed()}]")

    # Salvar URLs processadas no histórico
    processed_urls = {p["url"] for p in podcasts}
    save_history(processed_urls)
    log(f"📚 Histórico atualizado: {len(processed_urls)} URL(s) salva(s)")
    log("")

    # ── FASE 3: Agendar publicação ────────────────────────────────────────────
    log("📅 FASE 3 — Agendando publicação para AMANHÃ...")
    tomorrow     = datetime.date.today() + datetime.timedelta(days=1)

    for idx, item in enumerate(all_generated):
        ch      = item["channel_obj"]
        secrets = ch.get("secrets_path","")

        if not secrets or not os.path.exists(secrets):
            log(f"   ⚠️ {ch['name']}: client_secrets.json não encontrado")
            continue

        # Horário deste slot
        slot   = schedules_[idx % len(schedules_)]
        h, m   = map(int, slot.split(":"))
        dt_pub = datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, h, m)

        try:
            import pytz
            tz     = pytz.timezone("America/Sao_Paulo")
            dt_utc = tz.localize(dt_pub).astimezone(pytz.utc)
            pub_iso = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        except:
            pub_iso = ""

        log(f"   📤 [{idx+1}] {ch['name']} → {tomorrow.strftime('%d/%m')} às {slot} (Brasília)")
        log(f"       Título: {item['title'][:50]}")

        try:
            result = _yt_upload(
                ch_id=ch["id"],
                secrets_path=secrets,
                video_path=item["path"],
                title=item["title"],
                description=item["description"],
                tags=["shorts","podcast","viral","brasil"],
                privacy="private",       # privado até o horário agendado
                publish_at=pub_iso,      # muda para público automaticamente
            )
            log(f"   ✅ Agendado! {result['url']} [{elapsed()}]")
            results["uploaded"] += 1
            results["videos"].append({
                "url":     result["url"],
                "channel": ch["name"],
                "slot":    f"{tomorrow.strftime('%d/%m')} {slot}",
                "title":   item["title"],
            })
        except Exception as e:
            err_str = str(e)
            if "quotaExceeded" in err_str or "403" in err_str or "invalid_grant" in err_str or "Token" in err_str:
                motivo = "Quota excedida" if "quota" in err_str.lower() else "Token expirado"
                log(f"   ⏳ {motivo} — salvando na fila para enviar depois")
                save_to_queue({
                    "path":        item["path"],
                    "channel_id":  ch["id"],
                    "channel_name": ch["name"],
                    "secrets_path": secrets,
                    "title":       item["title"],
                    "description": item["description"],
                    "publish_at":  pub_iso,
                    "slot":        f"{pub_date.strftime('%d/%m/%Y')} {slot}",
                    "queued_at":   datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
            else:
                log(f"   ❌ Upload erro: {err_str[:80]}")
            results["errors"].append(f"{ch['name']}: {err_str[:80]}")

    log("")
    log("="*50)
    log(f"🎉 CONCLUÍDO em {elapsed()}")
    log(f"   ✅ {results['processed']} short(s) gerado(s)")
    log(f"   📅 {results['uploaded']} agendado(s) para amanhã")
    if results["errors"]:
        log(f"   ❌ {len(results['errors'])} erro(s)")
    log("="*50)
    return results


# ── Agendador diário ──────────────────────────────────────────────────────────

_scheduler_running = False

def start_scheduler(cfg: dict, log_callback=None):
    global _scheduler_running
    _scheduler_running = True
    schedule.clear()
    run_time = cfg.get("run_time","08:00")
    schedule.every().day.at(run_time).do(run_autopilot, cfg=cfg, log_callback=log_callback)

    def _loop():
        while _scheduler_running:
            schedule.run_pending()
            time.sleep(30)

    threading.Thread(target=_loop, daemon=True).start()
    print(f"[autopilot] Agendador ativo — executa todo dia às {run_time}")

def stop_scheduler():
    global _scheduler_running
    _scheduler_running = False
    schedule.clear()
