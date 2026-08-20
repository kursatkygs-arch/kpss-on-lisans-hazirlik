"""Mimo & Pofuduk daily kids episode: script -> illustrations -> narration -> video -> YouTube.

Runs entirely on free-tier services (Gemini free quota, Pollinations.ai image
generation, edge-tts narration, ffmpeg) so it can execute unattended on GitHub
Actions without any paid API.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).parent
RUNS = ROOT / "runs"
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
    "Original children's animation style, soft 3D clay-render look, rounded "
    "safe shapes, warm daylight palette, no text, no logos, no on-screen "
    "words. Mimo is a gentle mint-green round little creature with a yellow "
    "raincoat and a tiny red backpack. Pofuduk is a small lavender "
    "cloud-puppy with star-shaped ears. They live in a cosy village called "
    "Sunny Seed Village."
)

SERIES_BRIEF_TR = """Sen 'Mimo & Pofuduk' adlÄ±, 3-5 yaÅŸ TÃ¼rkÃ§e konuÅŸan Ã§ocuklara
yÃ¶nelik bir Ã§izgi film serisinin senaristi ve sÃ¶z yazarÄ±sÄ±n. Mimo nazik,
nane yeÅŸili yuvarlak bir yaratÄ±k; Pofuduk yÄ±ldÄ±z kulaklÄ±, lavanta renginde
kÃ¼Ã§Ã¼k bir bulut kÃ¶pek. GÃ¼neÅŸli Tohum KÃ¶yÃ¼'nde yaÅŸÄ±yorlar."""


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

{episode_no}. bÃ¶lÃ¼mÃ¼ kesinlikle sadece JSON olarak Ã¼ret. Anahtarlar: title,
description, tags, lesson, scenes.
- title: 70 karakterden kÄ±sa, TÃ¼rkÃ§e, merak uyandÄ±ran bir baÅŸlÄ±k.
- description: 2-3 cÃ¼mlelik TÃ¼rkÃ§e video aÃ§Ä±klamasÄ±.
- tags: 5-10 TÃ¼rkÃ§e/Ä°ngilizce karÄ±ÅŸÄ±k anahtar kelimeden oluÅŸan bir liste.
- lesson: bÃ¶lÃ¼mÃ¼n verdiÄŸi tek cÃ¼mlelik yumuÅŸak ders (paylaÅŸma, renkler,
  sayma 1-5, nezaket, el yÄ±kama, duygulari tanima, bir hayvana yardÄ±m gibi
  konulardan biri).
- scenes: tam olarak {SCENE_COUNT} obje iÃ§eren bir liste. Her obje ÅŸu
  anahtarlara sahip olmalÄ±:
  - narration_tr: sahnede Mimo ya da Pofuduk'un sÃ¶ylediÄŸi ya da anlatÄ±cÄ±nÄ±n
    seslendirdiÄŸi, basit ve sÄ±cak TÃ¼rkÃ§e metin (1-3 kÄ±sa cÃ¼mle).
  - scene_prompt_en: sadece bu sahnedeki eylemi/sahneyi tarif eden kÄ±sa bir
    Ä°ngilizce gÃ¶rsel aÃ§Ä±klama (Ã¶rn: "Mimo pointing at five red apples in a
    sunny meadow"). Karakter gÃ¶rÃ¼nÃ¼mÃ¼nÃ¼ tekrar tarif etme, sadece o anki
    eylemi ve ortamÄ± anlat.

Hikaye tamamen orijinal olmalÄ±. Var olan hiÃ§bir karaktere, markaya, ÅŸarkÄ±ya,
ninniye ya da yaratÄ±cÄ±ya atÄ±fta bulunma, onlarÄ± taklit etme ya da andÄ±rma.
ÅarkÄ± sÃ¶zÃ¼ kullanÄ±lacaksa tamamen yeni ve Ã¶zgÃ¼n olsun."""
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


def generate_images(episode: dict, output: Path) -> list[Path]:
    images_dir = output / "images"
    images_dir.mkdir(exist_ok=True)
    width, height = IMAGE_SIZE
    seed = abs(hash(episode["title"])) % 1_000_000
    images = []
    for index, scene in enumerate(episode["scenes"], start=1):
        prompt = f"{VISUAL_BIBLE_EN} Scene: {scene['scene_prompt_en']}"
        ensure_safe(prompt, f"scene {index} image prompt")
        url = (
            "https://image.pollinations.ai/prompt/"
            f"{urllib.parse.quote(prompt)}"
            f"?width={width}&height={height}&seed={seed}&nologo=true"
        )
        response = requests.get(url, timeout=180)
        response.raise_for_status()
        target = images_dir / f"scene-{index:02d}.jpg"
        target.write_bytes(response.content)
        images.append(target)
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


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def render_scene(image: Path, audio: Path, target: Path) -> None:
    width, height = IMAGE_SIZE
    duration = probe_duration(audio)
    frames = max(int(duration * 25), 25)
    zoompan = (
        f"scale={width * 2}:{height * 2},"
        f"zoompan=z='min(zoom+0.0012,1.15)':d={frames}:s={width}x{height}:fps=25"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(image), "-i", str(audio),
            "-vf", zoompan, "-c:v", "libx264", "-tune", "stillimage",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-t", f"{duration:.2f}", "-shortest", str(target),
        ],
        check=True,
    )


def compose(images: list[Path], clips: list[Path], output: Path) -> Path:
    scenes_dir = output / "scenes"
    scenes_dir.mkdir(exist_ok=True)
    scene_videos = []
    for index, (image, audio) in enumerate(zip(images, clips), start=1):
        target = scenes_dir / f"scene-{index:02d}.mp4"
        render_scene(image, audio, target)
        scene_videos.append(target)
    list_file = output / "scenes.txt"
    list_file.write_text("".join(f"file '{clip.as_posix()}'\n" for clip in scene_videos), encoding="utf-8")
    final = output / "final.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(final)],
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
