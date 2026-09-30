"""
The Roast Auditor — a voice accountability agent.

You talk to it about what you actually did today. It cross-references what
you say against a list of things you committed to, calls out vagueness or
contradictions, and pushes back with one sharp follow-up instead of just
nodding along. Built for the AssemblyAI Voice Agent Hackathon.

Pipeline:
  Your voice --> AssemblyAI Realtime STT --> Gemini (adversarial coach) --> pyttsx3 TTS --> spoken reply

Run:
    python roast_auditor.py

Say "give me my verdict" at any point to get a final accountability summary
and end the session (useful for wrapping up a demo recording cleanly).
"""

import json
import os
import queue
import sys
import threading
import time
from datetime import datetime

import google.generativeai as genai
import pyttsx3
import sounddevice as sd
from dotenv import load_dotenv
from assemblyai.streaming.v3 import (
    BeginEvent,
    RealTimeError,
    RealTimeEvents,
    RealTimeParameters,
    RealTimeTranscriber,
    RealTimeTranscriberOptions,
    TerminationEvent,
    TurnEvent,
)

load_dotenv()

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
COMMITMENTS_PATH = os.path.join(os.path.dirname(__file__), "commitments.json")

if not ASSEMBLYAI_API_KEY:
    sys.exit("Missing ASSEMBLYAI_API_KEY. Copy .env.example to .env and fill it in.")
if not GEMINI_API_KEY:
    sys.exit("Missing GEMINI_API_KEY. Copy .env.example to .env and fill it in.")

genai.configure(api_key=GEMINI_API_KEY, transport="rest")

MODEL = genai.GenerativeModel("gemini-flash-lite-latest")

SYSTEM_PROMPT = """You are "The Roast Auditor" — a sharp, funny, but genuinely useful
accountability coach. The user is telling you what they actually did today. You have
a list of things they committed to. Your job:

1. Compare what they just said against the commitments list.
2. If they're vague ("yeah I did some of it"), call it out and ask for a specific number
   or detail. Do not let vagueness slide.
3. If what they say contradicts something they said earlier in this conversation, point
   out the contradiction directly.
4. If they clearly did the thing, give them real credit — don't roast people who
   actually delivered. The roast is for excuses and dodges, not honesty.
5. Keep every reply to 2-3 sentences. This is spoken out loud, not read, so no lists,
   no markdown, no long paragraphs.
6. Tone: witty, direct, a little savage when earned, never cruel, never generic
   "great job!" filler.

If the user says something like "give me my verdict" or "wrap it up", instead of a
short reply, give a final 4-6 sentence verdict: go through each commitment, say
done / partially done / not done based on the whole conversation, and end with one
blunt sentence of overall judgment.
"""


def load_commitments():
    with open(COMMITMENTS_PATH) as f:
        return json.load(f)


def speak(text: str):
    print(f"\n[Roast Auditor]: {text}\n")
    engine = pyttsx3.init()
    engine.setProperty("rate", 178)
    engine.say(text)
    engine.runAndWait()


class RoastAuditor:
    def __init__(self):
        self.commitments = load_commitments()
        self.history = []
        self.chat = MODEL.start_chat(history=[])
        self._primed = False
        self._stop = False

    def _prime(self):
        commitments_text = "\n".join(
            f"- {c['text']}" for c in self.commitments["commitments"]
        )
        priming = (
            SYSTEM_PROMPT
            + "\n\nHere are today's commitments:\n"
            + commitments_text
            + "\n\nThe user is about to start talking. Wait for their first message, "
            "then respond according to the rules above. Do not reply to this priming "
            "message itself, just acknowledge readiness in one short line."
        )
        response = self.chat.send_message(priming)
        print(f"[system ready]: {response.text.strip()}")
        self._primed = True

    def respond_to(self, user_text: str):
        if not self._primed:
            self._prime()

        self.history.append({"role": "user", "text": user_text})
        response = self.chat.send_message(user_text)
        reply = response.text.strip()
        self.history.append({"role": "auditor", "text": reply})
        speak(reply)

        if "verdict" in user_text.lower() or "wrap it up" in user_text.lower():
            self._stop = True

    def on_final_transcript(self, text: str):
        text = text.strip()
        if not text:
            return
        print(f"\n[You said]: {text}")
        self.respond_to(text)


def sounddevice_microphone_stream(sample_rate: int = 16_000, chunk_ms: int = 50):
    """
    A drop-in replacement for aai.extras.MicrophoneStream that doesn't need
    PyAudio (which has no precompiled Windows wheel and requires a C++
    compiler to build from source). sounddevice ships precompiled wheels for
    all recent Python versions, so this avoids that entirely.

    Yields raw 16-bit PCM mono audio chunks, which is exactly what
    AssemblyAI's RealTimeTranscriber.stream() expects from a generator
    audio source.
    """
    q: "queue.Queue[bytes]" = queue.Queue()
    block_size = int(sample_rate * chunk_ms / 1000)

    def callback(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        q.put(bytes(indata))

    stream = sd.RawInputStream(
        samplerate=sample_rate,
        blocksize=block_size,
        dtype="int16",
        channels=1,
        callback=callback,
    )
    with stream:
        while True:
            yield q.get()


def build_realtime_transcriber(auditor: RoastAuditor):
    def on_begin(client, event: BeginEvent):
        print(f"Session started: {event.id}")

    def on_turn(client, event: TurnEvent):
        # Only react once AssemblyAI marks the turn as finished speaking,
        # equivalent to a "final" transcript rather than a live partial one.
        if event.end_of_turn and event.transcript:
            auditor.on_final_transcript(event.transcript)

    def on_terminated(client, event: TerminationEvent):
        print(f"\nSession closed ({event.audio_duration_seconds}s of audio processed).")

    def on_error(client, error: RealTimeError):
        print(f"AssemblyAI realtime error: {error}")

    transcriber = RealTimeTranscriber(
        RealTimeTranscriberOptions(
            api_key=ASSEMBLYAI_API_KEY,
            api_host="streaming.assemblyai.com",
        )
    )
    transcriber.on(RealTimeEvents.Begin, on_begin)
    transcriber.on(RealTimeEvents.Turn, on_turn)
    transcriber.on(RealTimeEvents.Termination, on_terminated)
    transcriber.on(RealTimeEvents.Error, on_error)
    return transcriber


def run_voice_mode():
    auditor = RoastAuditor()
    transcriber = build_realtime_transcriber(auditor)
    transcriber.connect(RealTimeParameters(sample_rate=16_000))

    try:
        transcriber.stream(sounddevice_microphone_stream(sample_rate=16_000))
    except KeyboardInterrupt:
        pass
    finally:
        transcriber.disconnect(terminate=True)
        print("\nSession ended.")


def run_text_mode():
    """
    Fallback mode: type instead of speak. Useful if a mic isn't available
    (e.g. recording a demo on a machine without working audio input), or for
    quickly testing the Gemini prompting logic without burning AssemblyAI
    minutes. Still uses AssemblyAI-transcribed style text, just typed by hand.
    """
    auditor = RoastAuditor()
    print("Text mode: type what you did today. Type 'quit' to exit.\n")
    while not auditor._stop:
        try:
            user_text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user_text.lower() in {"quit", "exit"}:
            break
        if not user_text:
            continue
        auditor.respond_to(user_text)


def main():
    print("=" * 60)
    print("THE ROAST AUDITOR")
    print("Tell it what you actually did today. It will hold you to it.")
    print('Say (or type) "give me my verdict" to end with a final summary.')
    print("=" * 60)

    if "--text" in sys.argv:
        run_text_mode()
    else:
        run_voice_mode()


if __name__ == "__main__":
    main()