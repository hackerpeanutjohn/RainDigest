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

## Setup

### 1. Prerequisites
- **Docker & Docker Compose**
- **Raindrop.io Account**
- **AI API Key**: Gemini API Key (Recommended, free tier available) or OpenAI API Key.

### 2. Configuration
Copy the example environment file and edit it:
```bash
cp .env.example .env
```

**Required Variables**:
- `RAINDROP_TOKEN`: Get a "Test Token" from [Raindrop Integrations](https://app.raindrop.io/settings/integrations).
- `GEMINI_API_KEY`: Get it from [Google AI Studio](https://aistudio.google.com/).

**Optional Variables**:
- `READWISE_TOKEN`: To sync summaries to Readwise Reader.
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_DOMAIN`: Required for hosting images on Cloudflare R2.
- `MAX_ITEMS`: Maximum number of bookmarks to process per run (default: 50).
- `DRY_RUN`: Set to `true` to test fetching without consuming LLM credits.
- `ENABLE_AUTO_ORGANIZER`: Set to `true` (default) to enable auto-sorting of Unsorted items. Set to `false` to disable.

### 3. Run
**Full Service (Summarizer + Organizer)**:
```bash
docker compose up --build
```

**Organizer Only (Standalone)**:
To run only the auto-classification without summarization:
```bash
docker compose run --rm app python organize.py
```
(Or locally: `python organize.py`)

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
