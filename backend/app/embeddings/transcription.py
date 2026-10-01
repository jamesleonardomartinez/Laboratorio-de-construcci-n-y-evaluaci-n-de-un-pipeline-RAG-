"""whisper-small/base transcription wrapper (3.3). MIT-licensed."""

from dataclasses import dataclass
from functools import lru_cache

from transformers import pipeline

from app.config import settings
from app.ffmpeg_utils import ensure_ffmpeg_on_path


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class Transcript:
    text: str
    segments: list[TranscriptSegment]


@lru_cache(maxsize=1)
def _get_pipeline():
    # The ASR pipeline decodes audio files with ffmpeg.
    ensure_ffmpeg_on_path()
    return pipeline(
        "automatic-speech-recognition",
        model=f"openai/whisper-{settings.whisper_model}",
        chunk_length_s=30,
        return_timestamps=True,
    )


def transcribe(audio_path: str) -> Transcript:
    asr = _get_pipeline()
    result = asr(audio_path)

    segments = [
        TranscriptSegment(
            start=chunk["timestamp"][0] or 0.0,
            end=chunk["timestamp"][1] or 0.0,
            text=chunk["text"].strip(),
        )
        for chunk in result.get("chunks", [])
    ]
    return Transcript(text=result["text"].strip(), segments=segments)
