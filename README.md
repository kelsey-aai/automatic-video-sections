# Automatically determine video sections with AI

Automatically generate named chapters with timestamps for an audio or video file, formatted as a YouTube Chapters block.

Companion repo for [Automatically determine video sections with AI using Python](https://www.assemblyai.com/blog/automatically-determine-video-sections-with-ai-using-python).

## How it works

Two API calls:

1. **[Speech Understanding Summarization](https://www.assemblyai.com/docs/speech-understanding/summarization)** transcribes the file and returns it split into ordered topic sections, each with a `headline`, `text`, and `start`/`end` timestamps in milliseconds.
2. **[LLM Gateway](https://www.assemblyai.com/docs/llm-gateway/quickstart)** rewrites the section headlines into something a viewer would click, preserving the timestamps.

The timestamps always come from the transcription API — the LLM only renames things — and the script asserts that the model returned the same number of lines with the same timestamps before printing anything. That check is what makes this safe to run unattended.

> **Note on Auto Chapters.** An earlier version of this project used the `auto_chapters` parameter and LeMUR, both of which are deprecated. Summarization is the replacement for Auto Chapters; the [migration guide](https://www.assemblyai.com/docs/speech-understanding/migration-guides/auto-chapters) maps every field. Per section, the old `summary` field is now `text` and `gist` is gone — use `headline` for a short label.

## Quick start

### 1. Clone

```shell
git clone https://github.com/kelsey-aai/automatic-video-sections.git
cd automatic-video-sections
```

### 2. Create a virtual environment

```shell
# Mac/Linux:
python3 -m venv venv
. venv/bin/activate

# Windows:
python -m venv venv
venv\Scripts\activate.bat
```

### 3. Install the requirements

```shell
pip install -r requirements.txt
```

### 4. Set your AssemblyAI key

Get one for free [here](https://www.assemblyai.com/dashboard/signup).

```shell
# Mac/Linux:
export ASSEMBLYAI_API_KEY=<YOUR_KEY>

# Windows:
set ASSEMBLYAI_API_KEY=<YOUR_KEY>
```

The same key authenticates both the transcription and the LLM Gateway request — there is no second account to create.

### 5. Run it

`python main.py <FILENAME>`, where `<FILENAME>` is either a publicly-accessible remote URL or a local filepath. Local files are uploaded first.

```shell
python main.py https://storage.googleapis.com/aai-web-samples/meeting.mp4
```

Output:

```plaintext
TIMESTAMPS:
00:00 Proposing Department Key Reviews
01:40 Clarifying Merge Request Rate Definitions
03:51 Fixing the Wider Merge Request Rate Metric
08:18 Confirming Wider Rate is Community-Only
08:40 Data Team Lag Issues
09:40 Discussing Postgres Replication
13:05 Defect Tracking and SLO Update
18:32 Smaller Security Metric Decline Seen as Improvement
20:42 Investigating Below-Target Narrow Merge Request Rate
23:50 Wrapping Up the Meeting
```

## Configuration

Both are constants at the top of `main.py`:

- **`LLM_MODEL`** — which model rewrites the headlines. Defaults to `claude-sonnet-4-6`; swap for any ID on the [available models list](https://www.assemblyai.com/docs/llm-gateway/available-models).
- **`speech_models`** — set to `["assemblyai-stt-3-7", "universal-2"]`. AssemblyAI-STT-3.7 handles its 32 languages and Universal-2 catches everything else, for 99 in total. Pin it explicitly rather than relying on the account default, which can change. See [selecting a speech model](https://www.assemblyai.com/docs/pre-recorded-audio/select-the-speech-model).

`summary_type` accepts `paragraph` (the default here) or `bullets`. There is also an optional `effort` field, `low` by default, worth raising to `medium` for long or multilingual audio.

## YouTube Chapters

The output is a valid YouTube Chapters block: timestamps at the start of the line, in ascending order, at least three of them, and the first one at `00:00`. Paste it straight into a video description.
