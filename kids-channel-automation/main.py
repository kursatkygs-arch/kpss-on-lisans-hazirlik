"""Mimo & Pofuduk daily kids episode: script -> illustrations -> narration -> video -> YouTube.

Runs entirely on free-tier services (Gemini free quota, Pollinations.ai image
generation, edge-tts narration, ffmpeg) so it can execute unattended on GitHub
Actions without any paid API.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).parent
RUNS = ROOT / "runs"
MUSIC_DIR = ROOT / "music"
SCENE_COUNT = 5
IMAGE_SIZE = (1920, 1080)
VOICE = "tr-TR-EmelNeural"

BLOCKED = {
    "cocomelon", "pinkfong", "baby shark", "disney", "pixar", "peppa pig",
    "paw patrol", "bluey", "mickey", "frozen", "wheels on the bus",
    "johnny johnny", "nursery rhyme", "superhero",
    "pepee", "niloya", "rafadan tayfa", "keloglan cizgi film",
}

VISUAL_BIBLE_EN = (
    "Stylized 3D cartoon character render, toon-shaded flat lighting, "
    "clearly non-photorealistic animated kids show look, bold simple "
    "shapes, high contrast simple colors, clean simple pastel background, "
    "big expressive sparkling eyes, rounded safe shapes, warm inviting "
    "palette, adorable and heart-warming mood, no text, no logos, no "
    "on-screen words. Mimo is a small round chubby creature with soft "
    "yellow-cream fur, small rounded ears on top of its head, a small "
    "fluffy round pom-pom tail, blush pink cheeks and a warm gentle "
    "smile. Pofuduk is a small lavender cloud-puppy with star-shaped "
    "ears. They live in a cosy village called Sunny Seed Village."
)

SERIES_BRIEF_TR = """Sen 'Mimo & Pofuduk' adlı, 3-5 yaş Türkçe konuşan çocuklara
yönelik bir çizgi film serisinin senaristi ve söz yazarısın. Mimo tüylü,
sarı-krem renkli, yuvarlak ve tombul, kulaklı ve pofuduk kuyruklu sevimli
bir yaratık; Pofuduk yıldız kulaklı, lavanta renginde küçük bir bulut köpek.
Güneşli Tohum Köyü'nde yaşıyorlar."""


def env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def ensure_safe(text: str, label: str) -> None:
    hits = sorted(word for word in BLOCKED if word in text.lower())
    if hits:
        raise RuntimeError(f"Rights preflight blocked {label}: {', '.join(hits)}")
    if len(text) < 40:
        raise RuntimeError(f"Rights preflight rejected an incomplete {label}.")


def next_episode() -> int:
    numbers = [int(p.name.split("-", 1)[0]) for p in RUNS.glob("*-*") if p.name.split("-", 1)[0].isdigit()]
    return max(numbers, default=0) + 1


def build_episode(episode_no: int) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=env("GEMINI_API_KEY"))
    prompt = f"""{SERIES_BRIEF_TR}

{episode_no}. bölümü kesinlikle sadece JSON olarak üret. Anahtarlar: title,
description, tags, lesson, scenes.
- title: 70 karakterden kısa, Türkçe, merak uyandıran bir başlık.
- description: 2-3 cümlelik Türkçe video açıklaması.
- tags: 5-10 Türkçe/İngilizce karışık anahtar kelimeden oluşan bir liste.
- lesson: bölümün verdiği tek cümlelik yumuşak ders (paylaşma, renkler,
  sayma 1-5, nezaket, el yıkama, duygulari tanima, bir hayvana yardım gibi
  konulardan biri).
Hikaye yapısı tam olarak {SCENE_COUNT} sahnede şu akışı izlemeli:
  1. Meraklandırıcı, enerjik bir açılış.
  2. Mimo ile Pofuduk'un karşılaştığı küçük, çocuklara uygun bir sorun ya da engel.
  3. İkisinin birlikte denediği bir çözüm girişimi (belki ilk denemede tam
     başaramazlar).
  4. Coşkulu, tatmin edici bir çözüm/başarı anı.
  5. Sıcak bir kapanış; ders (lesson) hikayenin içinde doğal şekilde
     hissettirilir.

- scenes: tam olarak {SCENE_COUNT} obje içeren bir liste (yukarıdaki 5 hikaye
  adımıyla aynı sırada). Her obje şu anahtarlara sahip olmalı:
  - narration_tr: sahnede Mimo ya da Pofuduk'un söylediği ya da anlatıcının
    seslendirdiği, basit ve sıcak Türkçe metin (1-3 kısa cümle).
  - scene_prompt_en: bu sahnenin İLK anını tarif eden kısa, HAREKETLİ bir
    İngilizce görsel açıklama — karakter net bir eylem içinde olsun (örn.
    "Mimo reaching up excitedly toward a red apple on a tree branch").
    Asla durağan/duruyor bir poz tarif etme. Karakter görünümünü tekrar
    tarif etme, sadece o anki eylemi ve ortamı anlat.
  - scene_prompt_en_b: aynı sahnenin hemen ardından gelen İKİNCİ anı —
    scene_prompt_en'deki hareketin doğal devamı ya da net bir tepki/duygu
    anı (örn. "Mimo happily hugging the apple with sparkling eyes, tiny
    petals floating around"). Bu ikinci an ilkinden görünür şekilde farklı
    bir poz/eylem olmalı, aynı ortamda geçmeli.

Hikaye tamamen orijinal olmalı. Var olan hiçbir karaktere, markaya, şarkıya,
ninniye ya da yaratıcıya atıfta bulunma, onları taklit etme ya da andırma.
Şarkı sözü kullanılacaksa tamamen yeni ve özgün olsun."""
    models_to_try = ["gemini-3.5-flash-lite", "gemini-flash-latest"]
    response = None
    last_exc = None
    for model_name in models_to_try:
        for attempt in range(4):
            try:
                response = client.models.generate_content(
                    model=model_name, contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                break
            except Exception as exc:
                last_exc = exc
                if attempt < 3:
                    time.sleep(20 * (attempt + 1))
        if response is not None:
            break
    if response is None:
        raise last_exc
    data = json.loads(response.text)
    if len(data.get("scenes", [])) != SCENE_COUNT:
        raise RuntimeError("Episode writer did not return the expected scene count.")
    ensure_safe(json.dumps(data, ensure_ascii=False), "episode script")
    return data


def _fetch_pollinations_image(prompt: str, width: int, height: int, seed: int, target: Path) -> None:
    url = (
        "https://image.pollinations.ai/prompt/"
        f"{urllib.parse.quote(prompt)}"
        f"?width={width}&height={height}&seed={seed}&model=flux&nologo=true"
    )
    response = requests.get(url, timeout=180)
    response.raise_for_status()
    target.write_bytes(response.content)


def generate_images(episode: dict, output: Path) -> list[tuple[Path, Path]]:
    images_dir = output / "images"
    images_dir.mkdir(exist_ok=True)
    width, height = IMAGE_SIZE
    base_seed = abs(hash(episode["title"])) % 1_000_000
    images = []
    for index, scene in enumerate(episode["scenes"], start=1):
        prompt_a = f"{VISUAL_BIBLE_EN} Scene: {scene['scene_prompt_en']}"
        prompt_b = f"{VISUAL_BIBLE_EN} Scene: {scene['scene_prompt_en_b']}"
        ensure_safe(prompt_a, f"scene {index} image prompt A")
        ensure_safe(prompt_b, f"scene {index} image prompt B")
        target_a = images_dir / f"scene-{index:02d}a.jpg"
        target_b = images_dir / f"scene-{index:02d}b.jpg"
        _fetch_pollinations_image(prompt_a, width, height, base_seed + index * 2, target_a)
        _fetch_pollinations_image(prompt_b, width, height, base_seed + index * 2 + 1, target_b)
        images.append((target_a, target_b))
    return images


def synthesize_narration(episode: dict, output: Path) -> list[Path]:
    audio_dir = output / "audio"
    audio_dir.mkdir(exist_ok=True)
    clips = []
    for index, scene in enumerate(episode["scenes"], start=1):
        text_file = audio_dir / f"scene-{index:02d}.txt"
        text_file.write_text(scene["narration_tr"], encoding="utf-8")
        target = audio_dir / f"scene-{index:02d}.mp3"
        subprocess.run(
            ["edge-tts", "--voice", VOICE, "--file", str(text_file), "--write-media", str(target)],
            check=True,
        )
        clips.append(target)
    return clips


def synthesize_chime(output: Path) -> Path:
    chime = output / "chime.mp3"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=0.18",
            "-f", "lavfi", "-i", "sine=frequency=1175:duration=0.18",
            "-f", "lavfi", "-i", "sine=frequency=1568:duration=0.24",
            "-filter_complex",
            "[0:a]afade=t=out:st=0.11:d=0.07[a0];"
            "[1:a]adelay=110|110,afade=t=out:st=0.11:d=0.07[a1];"
            "[2:a]adelay=220|220,afade=t=out:st=0.14:d=0.10[a2];"
            "[a0][a1][a2]amix=inputs=3:duration=longest,volume=6dB",
            "-ar", "44100", str(chime),
        ],
        check=True, capture_output=True,
    )
    return chime


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def render_scene(
    image_a: Path, image_b: Path, audio: Path, chime: Path, target: Path, direction: int = 1
) -> None:
    """Render one story beat as two zoompan'd stills crossfading mid-scene,
    giving the character a sense of motion between two poses without any
    paid animation tooling."""
    width, height = IMAGE_SIZE
    duration = probe_duration(audio)
    crossfade = min(0.6, duration * 0.18)
    seg = duration / 2 + crossfade / 2
    frames = max(int(seg * 25), 25)
    pan = 70 * direction

    def zoompan_chain(input_index: int, pan_amount: float) -> str:
        return (
            f"[{input_index}:v]scale={width * 2}:{height * 2},"
            f"zoompan=z='min(zoom+0.002,1.22)':"
            f"x='iw/2-(iw/zoom/2)+(on/{frames})*{pan_amount}':"
            f"y='ih/2-(ih/zoom/2)+(on/{frames})*20':"
            f"d={frames}:s={width}x{height}:fps=25[v{input_index}]"
        )

    filter_complex = (
        f"{zoompan_chain(0, pan)};{zoompan_chain(1, -pan)};"
        f"[v0][v1]xfade=transition=fade:duration={crossfade:.2f}:offset={seg - crossfade:.2f}[v];"
        "[3:a]volume=0.5[chime];[2:a][chime]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(image_a),
            "-loop", "1", "-i", str(image_b),
            "-i", str(audio), "-i", str(chime),
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[aout]",
            "-c:v", "libx264", "-tune", "stillimage",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-t", f"{duration:.2f}", str(target),
        ],
        check=True,
    )


def pick_music() -> Path | None:
    if not MUSIC_DIR.exists():
        return None
    tracks = [p for ext in ("*.mp3", "*.wav", "*.m4a") for p in MUSIC_DIR.glob(ext)]
    return random.choice(tracks) if tracks else None


def synthesize_ambient_pad(duration: float, output: Path) -> Path:
    pad = output / "ambient_pad.mp3"
    d = f"{duration:.2f}"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"sine=frequency=261.63:duration={d}",
            "-f", "lavfi", "-i", f"sine=frequency=329.63:duration={d}",
            "-f", "lavfi", "-i", f"sine=frequency=392.00:duration={d}",
            "-filter_complex",
            "[0:a][1:a][2:a]amix=inputs=3:duration=longest,"
            "tremolo=f=0.15:d=0.4,lowpass=f=2200,volume=0.5",
            "-ar", "44100", str(pad),
        ],
        check=True, capture_output=True,
    )
    return pad


def compose(images: list[tuple[Path, Path]], clips: list[Path], output: Path) -> Path:
    scenes_dir = output / "scenes"
    scenes_dir.mkdir(exist_ok=True)
    chime = synthesize_chime(output)
    scene_videos = []
    for index, ((image_a, image_b), audio) in enumerate(zip(images, clips), start=1):
        target = scenes_dir / f"scene-{index:02d}.mp4"
        direction = 1 if index % 2 else -1
        render_scene(image_a, image_b, audio, chime, target, direction)
        scene_videos.append(target)
    list_file = output / "scenes.txt"
    list_file.write_text("".join(f"file '{clip.as_posix()}'\n" for clip in scene_videos), encoding="utf-8")
    concatenated = output / "concatenated.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(concatenated)],
        check=True,
    )
    music = pick_music()
    loop_args: list[str] = []
    if music is None:
        music = synthesize_ambient_pad(probe_duration(concatenated), output)
    else:
        loop_args = ["-stream_loop", "-1"]
    final = output / "final.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(concatenated), *loop_args, "-i", str(music),
            "-filter_complex",
            "[1:a]volume=0.12[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]",
            "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-shortest", str(final),
        ],
        check=True,
    )
    return final


def upload(video: Path, episode: dict) -> str:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(
        None,
        refresh_token=env("YOUTUBE_REFRESH_TOKEN"),
        client_id=env("YOUTUBE_CLIENT_ID"),
        client_secret=env("YOUTUBE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {
            "title": episode["title"], "description": episode["description"],
            "tags": episode["tags"], "categoryId": "1",
            "defaultLanguage": "tr", "defaultAudioLanguage": "tr",
        },
        "status": {
            "privacyStatus": os.getenv("PUBLISH_PRIVACY", "public"),
            "selfDeclaredMadeForKids": True, "containsSyntheticMedia": True,
        },
    }
    response = youtube.videos().insert(
        part="snippet,status", body=body,
        media_body=MediaFileUpload(str(video), resumable=True),
    ).execute()
    return response["id"]


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", type=int)
    parser.add_argument("--next", action="store_true")
    args = parser.parse_args()
    episode_no = args.episode or (next_episode() if args.next else None)
    if not episode_no:
        parser.error("use --episode NUMBER or --next")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = RUNS / f"{episode_no:03d}-{stamp}"
    output.mkdir(parents=True)
    try:
        episode = build_episode(episode_no)
        (output / "episode.json").write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
        images = generate_images(episode, output)
        clips = synthesize_narration(episode, output)
        final = compose(images, clips, output)
        video_id = upload(final, episode)
        (output / "published.json").write_text(
            json.dumps({"video_id": video_id, "published_at": stamp}, indent=2), encoding="utf-8"
        )
        print(f"Published https://youtu.be/{video_id}")
    except Exception as exc:
        (output / "FAILED.txt").write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
