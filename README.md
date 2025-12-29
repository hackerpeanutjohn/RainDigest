# RainDigest

Automates the process of fetching video bookmarks from Raindrop.io, downloading/transcribing them, and generating structured summaries using AI (Gemini or OpenAI).

## Features
- **Auto-Fetch**: Scan Raindrop bookmarks (Unsorted or specific collection).
- **Smart Detection**: Identifies video links (YouTube, Instagram/Facebook Reels, etc.).
- **Auto-Tagging**: Adds `#summarized` tag to processed bookmarks in Raindrop so you can easily filter them.
- **Hybrid Processing**:
  - Downloads Subtitles (if available) for fast processing.
  - Fallback to Audio download + Cloud AI processing (Gemini Multimodal or OpenAI Whisper).
- **Design Consultant Persona**: Generates structured, educational notes.

## Setup

1. **Prerequisites**
   - Docker & Docker Compose
   - Raindrop.io Account
   - Gemini API Key (Google AI Studio) OR OpenAI API Key.

## Configuration
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   Edit `.env`. **The following variables are required**:

   - **`RAINDROP_TOKEN`** (Required):
     - Go to [Raindrop Integrations](https://app.raindrop.io/settings/integrations).
     - Create a "New App", name it "VideoSummarizer".
     - Copy the **Test Token**.
   - **`GEMINI_API_KEY`** (Required):
     - Get it from [Google AI Studio](https://aistudio.google.com/).

   **Optional Storage (for Images):**
   - **`R2_ACCOUNT_ID`**, **`R2_ACCESS_KEY_ID`**, **`R2_SECRET_ACCESS_KEY`**, **`R2_BUCKET_NAME`**, **`R2_PUBLIC_DOMAIN`**:
     - Required only if you want to host extracted keyframes on Cloudflare R2.
     - If omitted, images are stored locally in `./output/images`.

   **Other Settings:**
   - `RAINDROP_COLLECTION_ID`: ID of the collection to watch (default `0` for Unsorted).
   - `MAX_ITEMS`: Max items to process per run (default `50`).

3. **Run**
   Start the service:
   ```bash
   docker compose up --build
   ```

## Output
- Summaries are saved to `./output` folder as Markdown files.
  - **Filename Limit**: Titles are truncated to 50 characters to prevent filesystem errors.
- Processed bookmarks are tracked in `./data/history.json`.

## Data Privacy & Cloud Storage

### Google Gemini (Audio/Video)
- Audio and video files are uploaded to Google Gemini for processing.
- **Privacy**: Files are stored in your Google AI Studio account.
- **Retention**: This tool relies on Google's default auto-expiry (usually 48 hours for files uploaded via API). They are **not** immediately deleted by this tool to allow for debugging, but they are not public.

### Cloudflare R2 (Images)
- If R2 is configured, extracted keyframes are uploaded to a public bucket.
- **Retention**: This tool automatically runs a cleanup job on every execution. **Files older than 30 days are permanently deleted** from the R2 bucket to save costs and privacy.
- **Public Access**: Files in R2 are accessible via the `R2_PUBLIC_DOMAIN` you configured.

## Cost Estimation
This tool heavily relies on **LLM APIs**.

### Gemini (Google)
- **Model**: `gemini-2.0-flash` (or 1.5-flash)
- **Cost**: **Currently Free** (within rate limits on Google AI Studio). 
- **Usage**:
  - Audio upload consumes "Tokens" based on audio length.
  - Text summarization consumes tokens based on transcript length.
  - Generous free tier is usually sufficient for personal use (1500 req/day).

### OpenAI
- **Model**: `gpt-4o` + `whisper-1`
- **Cost**: **Paid**.
- **Usage**:
  - **Whisper**: ~$0.006 / minute of audio. (1 hour = $0.36)
  - **GPT-4o**: Depends on text length. 10min video transcript is roughly ~1.5k tokens. Summarizing costs ~$0.01 - $0.05 per video.
  
**Recommendation**: Use **Gemini** for the most cost-effective (free) experience.

## Readwise Integration
If `READWISE_TOKEN` is set, summaries are automatically saved to **Readwise Reader**:
- **Title**: `[Video/Short] Title - Speaker`
- **Tags**: `RaindropCollectionName`, `summarized`, `Video/Short`
- **Content**: The AI generated summary.

## Future Plans: Keyframe Extraction
We plan to integrate **PySceneDetect** (https://github.com/Breakthrough/PySceneDetect) to capture visual context.
*   **Logic**: 
    - If video length < 10 mins:
    - Run `detect-content` to find key scene changes.
    - Save 3-5 keyframes.
    - Feed frames + audio to Gemini (Multimodal) for richer "Visual Notes".

## Continuous Monitoring (Future)
Currently, the script runs once and exits. To monitor for new bookmarks continuously:

1.  **Cron Method (Recommended)**:
    Add a cron job on your host machine to run it every hour:
    ```bash
    0 * * * * cd /path/to/RainDrop-Auto && docker compose up
    ```

2.  **Daemon Method**:
    Modify `src/main.py` to add a loop:
    ```python
    import time
    if __name__ == "__main__":
        while True:
            main()
            logger.info("Sleeping for 1 hour...")
            time.sleep(3600)
    ```
    Then run with `docker compose up -d`.
