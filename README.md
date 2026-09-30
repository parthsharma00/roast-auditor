# The Roast Auditor

A voice accountability agent. You tell it what you actually did today — it
cross-references what you say against a list of things you committed to,
calls out vagueness or contradictions in real time, and gives you a final
verdict when you're done. Built for the **AssemblyAI Voice Agent Hackathon**
(lablab.ai), using AssemblyAI's Realtime Speech-to-Text as the listening
layer and Gemini as the reasoning/response engine.

## Why this exists

Every daily check-in app just logs what you say. This one argues with you.
It holds your own words against your stated commitments, spots when you're
dodging, and gives credit when you actually delivered. It's the built-in
skepticism a good coach or accountability partner brings, as a voice agent.

## Architecture

```
Your voice
   -> AssemblyAI Realtime STT (streaming transcription over WebSocket)
   -> Gemini 2.0 Flash (adversarial-coach reasoning over conversation + commitments)
   -> pyttsx3 (offline text-to-speech)
   -> spoken reply
```

`commitments.json` holds the list of things you're accountable for today —
edit it before each run to match what you actually committed to.

## Setup

1. **Python 3.10+** and a working microphone.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
   On Linux you may also need `sudo apt-get install portaudio19-dev` before
   `pyaudio` will build. On Mac, `brew install portaudio` first.
3. Copy `.env.example` to `.env` and fill in your keys:
   - `ASSEMBLYAI_API_KEY` — from your AssemblyAI dashboard (sign up via the
     link on the hackathon page to get free credits).
   - `GEMINI_API_KEY` — from https://aistudio.google.com/apikey (free tier
     is enough).
4. Edit `commitments.json` with today's real commitments.

## Run

Voice mode (the real thing):
```
python roast_auditor.py
```
Speak naturally. Say **"give me my verdict"** at any point to get a final
accountability summary and end the session — good for wrapping up a demo
recording cleanly.

Text mode (fallback, useful for testing without a mic or without burning
AssemblyAI minutes):
```
python roast_auditor.py --text
```

## Demo recording tips

- Have 2-3 commitments in `commitments.json` that mix: one you actually did,
  one you half-did, one you skipped. The contrast is what makes the demo
  interesting — showing it give real credit *and* call out a dodge in the
  same session proves it's not just randomly negative.
- Keep the recording to 2-3 minutes: a quick intro sentence on what it is,
  then 2-3 real exchanges, then "give me my verdict" for a clean ending.

## Hackathon submission checklist

- [ ] Public GitHub repo (push this project)
- [ ] Demo video (2-3 min, screen + voice recording of a real session)
- [ ] Short + long description (see below for a draft)
- [ ] Cover image / slide deck
- [ ] Submitted on lablab.ai before Sep 30, 8:30 PM IST

### Draft short description

"The Roast Auditor is a voice accountability agent: tell it what you
actually did today, and it cross-references your own words against your
commitments, calls out vagueness and contradictions live, and gives you a
blunt final verdict. Built on AssemblyAI's Realtime STT."

### Draft long description

"Most check-in tools just log what you say. The Roast Auditor argues with
you. Using AssemblyAI's Realtime Speech-to-Text, it transcribes what you say
about your day as you say it, then an adversarial-coach LLM layer compares
your claims against a list of things you committed to — catching vague
answers, contradictions between what you said a minute ago and what you're
saying now, and genuinely rewarding you when you followed through. Say 'give
me my verdict' and it delivers a blunt, itemized final judgment on the day.
It's the skepticism a real accountability partner brings, built as a voice
agent instead of a chat log nobody re-reads."

## Notes

- This is an MVP built in a single day for the hackathon deadline — the
  commitments list is a static JSON file rather than a synced task tracker
  by design, to keep the demo fast and self-contained.
- pyttsx3 is used for TTS to keep the project dependency-light and fully
  offline for that half of the pipeline; swapping in a nicer TTS voice is a
  natural next step but wasn't necessary to prove the core idea.
