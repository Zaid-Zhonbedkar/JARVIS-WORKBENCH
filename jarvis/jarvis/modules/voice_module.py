"""
JARVIS Voice Module
Speech-to-text, text-to-speech, and wake word detection.
Runs in a background thread, calls back into the assistant.
"""

import threading
import queue
import time
from typing import Callable, Optional
from core.config import Config


class VoiceModule:
    """
    Manages microphone input, wake-word detection, STT, and TTS.

    STT backends: google (online) | whisper (offline) | vosk (offline)
    TTS backends: pyttsx3 (offline) | coqui (offline, better quality)
    """

    def __init__(
        self,
        config: Config,
        on_command: Callable[[str], None],
        on_listening: Callable[[bool], None],
    ):
        self.config = config
        self.on_command = on_command
        self.on_listening = on_listening

        self._running = False
        self._speak_queue: queue.Queue = queue.Queue()
        self._listen_thread: Optional[threading.Thread] = None
        self._speak_thread: Optional[threading.Thread] = None

        self._recognizer = None
        self._tts_engine = None
        self._whisper_model = None

        self._init_stt()
        self._init_tts()

    # ------------------------------------------------------------------ #
    #  Initialization
    # ------------------------------------------------------------------ #

    def _init_stt(self):
        import speech_recognition as sr
        self._recognizer = sr.Recognizer()
        self._recognizer.energy_threshold = self.config.voice.energy_threshold
        self._recognizer.pause_threshold = self.config.voice.pause_threshold
        self._microphone = sr.Microphone()

        if self.config.voice.stt_backend == "whisper":
            import whisper
            self._whisper_model = whisper.load_model(self.config.voice.whisper_model)
            print(f"[Voice] Whisper model '{self.config.voice.whisper_model}' loaded")

        print(f"[Voice] STT backend: {self.config.voice.stt_backend}")

    def _init_tts(self):
        if self.config.voice.tts_engine == "pyttsx3":
            import pyttsx3
            self._tts_engine = pyttsx3.init()
            self._tts_engine.setProperty("rate", self.config.voice.tts_rate)
            self._tts_engine.setProperty("volume", self.config.voice.tts_volume)
            # Try to use a better voice
            voices = self._tts_engine.getProperty("voices")
            for v in voices:
                if "english" in v.name.lower() or "en" in v.id.lower():
                    self._tts_engine.setProperty("voice", v.id)
                    break
        elif self.config.voice.tts_engine == "coqui":
            from TTS.api import TTS
            self._tts_engine = TTS("tts_models/en/ljspeech/tacotron2-DDC")
            print("[Voice] Coqui TTS loaded")

        print(f"[Voice] TTS engine: {self.config.voice.tts_engine}")

    # ------------------------------------------------------------------ #
    #  Lifecycle
    # ------------------------------------------------------------------ #

    def start(self):
        self._running = True
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._speak_thread = threading.Thread(target=self._speak_loop, daemon=True)
        self._listen_thread.start()
        self._speak_thread.start()
        print(f"[Voice] Listening for wake word: '{self.config.voice.wake_word}'")

    def stop(self):
        self._running = False

    # ------------------------------------------------------------------ #
    #  Listening loop
    # ------------------------------------------------------------------ #

    def _listen_loop(self):
        import speech_recognition as sr
        wake = self.config.voice.wake_word.lower()

        with self._microphone as source:
            self._recognizer.adjust_for_ambient_noise(source, duration=1)

        while self._running:
            try:
                with self._microphone as source:
                    audio = self._recognizer.listen(source, timeout=5, phrase_time_limit=10)

                text = self._transcribe(audio).lower().strip()
                if not text:
                    continue

                print(f"[Voice] Heard: {text}")

                # Wake word detection
                if wake in text:
                    # Strip wake word from command
                    command = text.replace(wake, "").strip(", ").strip()
                    if not command:
                        # Wake word only — prompt for command
                        self.speak("Yes?")
                        self.on_listening(True)
                        with self._microphone as source:
                            audio2 = self._recognizer.listen(source, timeout=8, phrase_time_limit=15)
                        command = self._transcribe(audio2).strip()
                        self.on_listening(False)

                    if command:
                        self.on_command(command)

            except Exception:
                # Timeout or recognition failure — just keep looping
                pass

    def _transcribe(self, audio) -> str:
        import speech_recognition as sr
        backend = self.config.voice.stt_backend

        try:
            if backend == "google":
                return self._recognizer.recognize_google(
                    audio, language=self.config.voice.language
                )
            elif backend == "whisper":
                import tempfile, os
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(audio.get_wav_data())
                    tmp_path = f.name
                result = self._whisper_model.transcribe(tmp_path)
                os.unlink(tmp_path)
                return result["text"]
            elif backend == "vosk":
                import json
                from vosk import Model, KaldiRecognizer
                # Vosk setup (requires model path in config)
                rec = KaldiRecognizer(self._vosk_model, 16000)
                rec.AcceptWaveform(audio.get_raw_data())
                res = json.loads(rec.FinalResult())
                return res.get("text", "")
        except Exception as e:
            print(f"[Voice] Transcription error: {e}")
            return ""

    # ------------------------------------------------------------------ #
    #  Speaking
    # ------------------------------------------------------------------ #

    def speak(self, text: str):
        """Queue text for speech output (non-blocking)."""
        self._speak_queue.put(text)

    def _speak_loop(self):
        while self._running:
            try:
                text = self._speak_queue.get(timeout=1)
                self._say(text)
            except queue.Empty:
                continue

    def _say(self, text: str):
        """Actually synthesize and play speech."""
        engine = self.config.voice.tts_engine
        try:
            if engine == "pyttsx3":
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()
            elif engine == "coqui":
                import tempfile, os, subprocess
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    out = f.name
                self._tts_engine.tts_to_file(text=text, file_path=out)
                subprocess.run(["aplay", out], capture_output=True)
                os.unlink(out)
        except Exception as e:
            print(f"[Voice] TTS error: {e}")
