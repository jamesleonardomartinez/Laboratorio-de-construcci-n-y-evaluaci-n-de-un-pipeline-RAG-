"""Audio/video transcription entry point (4.5) and video key-frame extraction (4.6)."""

import subprocess
import tempfile
from pathlib import Path

import cv2

from app.config import settings
from app.embeddings.transcription import Transcript, transcribe
from app.ffmpeg_utils import ensure_ffmpeg_on_path
from app.ingestion.structure import StructuredBlock

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}


def is_video(path: str) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS


def _extract_audio_track(video_path: str) -> str:
    """Extracts the audio track to a temp WAV file via ffmpeg, for Whisper input."""
    ensure_ffmpeg_on_path()
    tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_wav.close()
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            tmp_wav.name,
        ],
        check=True,
        capture_output=True,
    )
    return tmp_wav.name


def transcribe_media(path: str) -> Transcript:
    """Transcribes audio or video source. For video, the audio track is extracted
    to a temp WAV first, which is removed once transcription finishes."""
    if not is_video(path):
        return transcribe(path)

    audio_path = _extract_audio_track(path)
    try:
        return transcribe(audio_path)
    finally:
        Path(audio_path).unlink(missing_ok=True)


def transcript_to_blocks(transcript: Transcript) -> list[StructuredBlock]:
    """Feeds transcript text into the same cleaning/chunking flow used for documents
    (specs/document-ingestion Requirement: Audio and Video Transcription)."""
    if transcript.segments:
        return [StructuredBlock(kind="paragraph", text=seg.text) for seg in transcript.segments if seg.text]
    return [StructuredBlock(kind="paragraph", text=transcript.text)] if transcript.text else []


def extract_key_frames(video_path: str, project_id: str, source_id: str) -> list[str]:
    """Samples one frame every VIDEO_FRAME_INTERVAL_SECONDS and saves each as a JPEG
    asset, returning the list of saved frame paths."""
    interval_s = settings.video_frame_interval_seconds
    dest_dir = Path(settings.upload_dir) / project_id / "assets" / source_id / "frames"
    dest_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 1.0
    frame_interval = max(int(fps * interval_s), 1)

    saved_paths: list[str] = []
    frame_index = 0
    saved_index = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_index % frame_interval == 0:
            frame_path = dest_dir / f"frame_{saved_index:05d}.jpg"
            cv2.imwrite(str(frame_path), frame)
            saved_paths.append(str(frame_path))
            saved_index += 1
        frame_index += 1
    cap.release()

    return saved_paths
