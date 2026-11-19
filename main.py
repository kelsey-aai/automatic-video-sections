import argparse
import os
import re
import time

import requests

parser = argparse.ArgumentParser(
    description="Automatically generate named chapters with timestamps for an audio or video file"
)
parser.add_argument('filename', help="a publicly-accessible URL or a local filepath")

BASE_URL = "https://api.assemblyai.com"
LLM_GATEWAY_URL = "https://llm-gateway.assemblyai.com/v1/chat/completions"

try:
    HEADERS = {"authorization": os.environ["ASSEMBLYAI_API_KEY"]}
except KeyError:
    raise SystemExit(
        "ASSEMBLYAI_API_KEY is not set. Get a key at "
        "https://www.assemblyai.com/dashboard/signup and export it:\n"
        "    export ASSEMBLYAI_API_KEY=<YOUR_KEY>"
    )

# the model that rewrites the section headlines. swap for any ID on
# https://www.assemblyai.com/docs/llm-gateway/available-models
LLM_MODEL = "claude-sonnet-4-6"

PROMPT = """
ROLE:
You are a YouTube content professional. You are very competent and able to come up with catchy names for the different sections of video transcripts that are submitted to you.
CONTEXT:
This transcript is of a logistics meeting at GitLab
INSTRUCTION:
You are provided information about the sections of the transcript under TIMESTAMPS, where the format for each line is `<TIMESTAMP> <SECTION SUMMARY>`.
TIMESTAMPS:
{timestamp_lines}
FORMAT:
<TIMESTAMP> <CATCHY SECTION TITLE>
OUTPUT:
""".strip()


def resolve_audio_url(filename):
    """ return a URL the API can fetch, uploading the file first if it is local """
    if re.match(r'https?://', filename):
        return filename

    # local file: stream it as raw bytes to /v2/upload. it must be raw bytes —
    # sending JSON here returns a usable upload_url that then fails at transcoding.
    with open(filename, "rb") as f:
        response = requests.post(f"{BASE_URL}/v2/upload", headers=HEADERS, data=f)
    response.raise_for_status()
    return response.json()["upload_url"]


def transcribe(audio_url):
    """ transcribe the audio and request topic sections via Speech Understanding """
    data = {
        "audio_url": audio_url,
        # plural array on pre-recorded audio. assemblyai-stt-3-7 handles its 32
        # languages; universal-2 catches everything else, for 99 in total.
        "speech_models": ["assemblyai-stt-3-7", "universal-2"],
        # Summarization replaces the deprecated auto_chapters parameter. it returns
        # the transcript split into ordered topic sections with timestamps.
        "speech_understanding": {
            "request": {
                "summarization": {
                    "summary_type": "paragraph"
                }
            }
        }
    }

    response = requests.post(f"{BASE_URL}/v2/transcript", json=data, headers=HEADERS)
    response.raise_for_status()

    transcript_id = response.json()["id"]
    polling_endpoint = f"{BASE_URL}/v2/transcript/{transcript_id}"

    while True:
        transcript = requests.get(polling_endpoint, headers=HEADERS).json()
        if transcript["status"] == "completed":
            return transcript
        if transcript["status"] == "error":
            raise RuntimeError(f"Transcription failed: {transcript['error']}")
        time.sleep(3)


def get_sections(transcript):
    """ read the topic sections out of the Speech Understanding response """
    summarization = transcript["speech_understanding"]["response"]["summarization"]

    # transcription and Summarization can succeed and fail independently
    if summarization["status"] != "success":
        raise RuntimeError("Summarization did not complete successfully")

    return summarization["summary"]


def ms_to_hms(start):
    """ convert milliseconds to (hour, minutes, seconds) tuple """
    s, ms = divmod(start, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return h, m, s


def create_timestamps(sections):
    """ given sections, return timestamps formatted as (HH):MM:SS <SECTION_HEADLINE> """
    last_hour = ms_to_hms(sections[-1]["start"])[0]
    time_format = "{m:02d}:{s:02d}" if last_hour == 0 else "{h:02d}:{m:02d}:{s:02d}"

    lines = []
    for idx, section in enumerate(sections):
        # first YouTube timestamp must be at zero
        h, m, s = (0, 0, 0) if idx == 0 else ms_to_hms(section["start"])
        lines.append(f"{time_format.format(h=h, m=m, s=s)} {section['headline']}")

    return "\n".join(lines)


def rewrite_headlines(timestamp_lines):
    """ ask an LLM to rewrite the section headlines, preserving the timestamps """
    response = requests.post(
        LLM_GATEWAY_URL,
        headers=HEADERS,
        json={
            "model": LLM_MODEL,
            "messages": [
                {"role": "user", "content": PROMPT.format(timestamp_lines=timestamp_lines)}
            ],
            "max_tokens": 1000,
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def filter_timestamps(text):
    lines = text.splitlines()
    timestamped_lines = [line for line in lines if re.match(r'\d+:\d+', line)]  # Use regex to filter lines starting with a timestamp
    filtered_text = '\n'.join(timestamped_lines)
    return filtered_text


def verify_timestamps(a, b):
    """ verify that the timestamps in two strings match """
    original = a.splitlines()
    filtered = b.splitlines()

    # check the line count first: zip() stops at the shorter sequence, so without
    # this a dropped section would compare only the survivors and pass silently
    if len(original) != len(filtered):
        raise RuntimeError(
            f"Line count mismatch - expected {len(original)}, got {len(filtered)}"
        )

    for o, f in zip(original, filtered):
        original_time = o.split(' ')[0]
        filtered_time = f.split(' ')[0]
        if not original_time == filtered_time:
            raise RuntimeError(f"Timestamp mismatch - original timestamp '{original_time}' does not match LLM timestamp '{filtered_time}'")


if __name__ == "__main__":
    args = parser.parse_args()

    transcript = transcribe(resolve_audio_url(args.filename))
    sections = get_sections(transcript)

    # build the timestamps from the API response, not from the LLM
    timestamp_lines = create_timestamps(sections)

    # rewrite only the titles, then filter out any preamble the model added
    output = rewrite_headlines(timestamp_lines)
    filtered_output = filter_timestamps(output)

    # verify the LLM did not modify or drop any timestamps
    verify_timestamps(timestamp_lines, filtered_output)

    # print the results
    print("TIMESTAMPS:")
    print(filtered_output)
