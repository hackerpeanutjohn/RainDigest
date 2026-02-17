# RainDigest

Automates the process of fetching video bookmarks from Raindrop.io, extracting metadata/transcripts, and generating structured AI summaries (using Gemini or OpenAI). It even captures keyframes for a richer reading experience in Readwise.

## Features
- **Auto-Sync**: Scans your Raindrop.io collections for new video bookmarks.
- **Auto-Classification (Beta)**: Automatically moves items from "Unsorted" to the most relevant collection using LLM analysis.
- **AI Director Mode (Beta)**: Automatically identifies high-value moments (charts, lists, key slides) in videos under 10 minutes and captures keyframes.
- **Smart Summarization**: Generates structured notes including "The Gist", "Key Takeaways", and "Critical Perspectives".
- **Multi-Source Support**: Handles YouTube, Instagram/Facebook Reels, and more via `yt-dlp`.
- **Hybrid Transcription**: 
  - Uses existing subtitles when available (fast & cheap).
  - Falls back to AI audio-to-text processing (Gemini Multimodal or OpenAI Whisper).
- **Readwise Integration**: Automatically syncs summaries, metadata, and visual highlights to **Readwise Reader**.
- **Cloud Storage**: Optional Cloudflare R2 integration for hosting captured keyframes with automatic 30-day retention cleanup.
- **Auto-Tagging**: Marks processed items with a `#summarized` tag in Raindrop.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/John-Thunder/RainDigest.git
cd RainDigest

# 2. Configure
cp .env.example .env
# Edit .env and fill in your tokens (see below)

# 3. Run (pulls pre-built image from Docker Hub)
docker compose up -d
```

**Want to build from source instead?**
```bash
docker build -t jjdock1112/raindigest:latest .
docker compose up -d
```

## Setup

### Prerequisites
- **Docker & Docker Compose**
- **Raindrop.io Account**
- **AI API Key**: Gemini API Key (Recommended, free tier available).

### Configuration

**Required**:
| Variable | Description | Where to get it |
|---|---|---|
| `RAINDROP_TOKEN` | Raindrop.io Test Token | [Raindrop Integrations](https://app.raindrop.io/settings/integrations) |
| `GEMINI_API_KEY` | Google Gemini API Key | [Google AI Studio](https://aistudio.google.com/) |

**Optional**:
| Variable | Default | Description |
|---|---|---|
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model to use (e.g. `gemini-2.5-pro`) |
| `GEMINI_PROCESSING_TIMEOUT` | `300` | Max seconds to wait for Gemini file processing |
| `READWISE_TOKEN` | — | Sync summaries to Readwise Reader |
| `R2_ACCOUNT_ID` | — | Cloudflare R2 (for hosting keyframe images) |
| `R2_ACCESS_KEY_ID` | — | Cloudflare R2 |
| `R2_SECRET_ACCESS_KEY` | — | Cloudflare R2 |
| `R2_BUCKET_NAME` | — | Cloudflare R2 |
| `R2_PUBLIC_DOMAIN` | — | Cloudflare R2 |
| `MAX_ITEMS` | `50` | Max bookmarks to process per run |
| `DRY_RUN` | `false` | Test fetching without consuming LLM credits |
| `ENABLE_AUTO_ORGANIZER` | `true` | Auto-sort Unsorted items via LLM |

### Run

**Full Service (Summarizer + Organizer)**:
```bash
docker compose up -d
```

**One-shot (no loop)**:
```bash
docker compose run --rm app python -m src.main
```

**Organizer Only**:
```bash
docker compose run --rm app python organize.py
```

## How It Works
1. **Fetch**: Scans Raindrop collections.
2. **Organize**: (If enabled) Checks "Unsorted" collection, asks AI to classify items, and moves them to the best matching collection.
3. **Download**: Uses `yt-dlp` to fetch metadata and subtitles. If no subtitles exist, it downloads the audio.
3. **AI Director**: For short videos, it asks Gemini to "watch" or "listen" and find the best timestamps for screenshots.
4. **Summarize**: Sends the transcript/audio to the LLM to generate a structured summary.
5. **Sync**: 
   - Saves a local Markdown file in `./output`.
   - Uploads keyframes to R2 (if configured).
   - Posts the final summary to Readwise Reader.
   - Tags the bookmark in Raindrop as `#summarized`.

## Customization

### 1. Modifying AI Prompts
- **Core Summary**: Change `DEFAULT_SYSTEM_PROMPT` in `src/config.py`. This defines the structure (e.g., Gist, Takeaways).
- **Title Generation**: Modify `generate_concise_title` in `src/llm.py`.
- **Visual Analysis**: Modify `analyze_visual_cues` or `analyze_visual_cues_from_video` in `src/llm.py` to change how the AI finds "important" frames.

### 2. Adjusting Logic
- **Download Parameters**: Check `src/media.py` for resolution or format settings.
- **Metadata/Tags**: Check `src/readwise.py` to customize how items appear in Readwise.
- **Filtering**: Check `src/main.py` to modify collection filtering or processing priority.

## Privacy & Costs

### Data Retention
- **Google Gemini**: Files uploaded to Gemini (Audio/Video) are stored in your Google AI Studio account and usually expire after 48 hours.
- **Cloudflare R2**: If enabled, keyframes are deleted automatically after **30 days** of retention to minimize storage costs and privacy risks.

### Cost Estimation
- **Gemini**: Using `gemini-2.0-flash` is currently free within generous rate limits (1500 requests/day).
- **OpenAI**: Using `gpt-4o` + `whisper-1` is paid and costs roughly $0.05 - $0.50 per hour of video depending on complexity.

## Roadmap
- [x] AI Director (Visual Highlights)
- [x] Cloudflare R2 Integration
- [ ] Support for long-form video (>30 mins) chunking.
- [ ] Support for Podcasting feeds.
- [ ] Web Dashboard for status monitoring.

## Build & Publish

For maintainers — build a multi-arch image and push to Docker Hub:
```bash
docker build --platform linux/amd64 -t jjdock1112/raindigest:latest .
docker push jjdock1112/raindigest:latest
```