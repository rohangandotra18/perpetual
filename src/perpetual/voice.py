"""Birth announcement. Fail-open: a missing key or a bad network must never block compile."""
from __future__ import annotations

import os
import threading


def announce(name: str) -> None:
    """Speak 'Compiling <name>' in a daemon thread. No-op without a key or in mock mode."""
    if os.environ.get("PERPETUAL_MOCK") == "1":
        return
    key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    if not key:
        return
    threading.Thread(target=_speak, args=(name, key), daemon=True).start()


def _speak(name: str, key: str) -> None:
    try:
        from elevenlabs import ElevenLabs, play

        spoken = name.replace("_", " ")
        client = ElevenLabs(api_key=key)
        audio = client.text_to_speech.convert(
            voice_id=os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
            text=f"Compiling {spoken}",
            model_id="eleven_flash_v2_5",
        )
        play(audio)
    except Exception:
        pass
