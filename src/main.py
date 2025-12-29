import json
import time
import os
from pathlib import Path
from loguru import logger
from datetime import datetime
from .config import settings
from .raindrop import raindrop_client
from .media import VideoProcessor
from .llm import get_provider

HISTORY_FILE = settings.DATA_DIR / "history.json"

def load_history() -> set:
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_history(history: set):
    with open(HISTORY_FILE, "w") as f:
        json.dump(list(history), f)

def main():
    logger.info("Starting Raindrop Video Summarizer...")
    
    # 1. Init
    history = load_history()
    video_processor = VideoProcessor()
    llm = get_provider(settings.DEFAULT_LLM_PROVIDER)
    
    # 2. Fetch
    # 2. Fetch Collections
    logger.info("Fetching Collections...")
    collections = raindrop_client.get_collections()
    logger.info(f"Found {len(collections)} collections to process (skipping Unsorted).")
    
    # 2.5 Run Cleanup (once per run)
    from .storage import r2_storage
    if r2_storage.enabled:
        r2_storage.cleanup_old_files(retention_days=30)
    
    # Global processed counter
    processed_count = 0
    
    for c_id, c_title in collections.items():
        # Check global limit before starting collection
        if settings.MAX_ITEMS > 0 and processed_count >= settings.MAX_ITEMS:
            logger.info(f"Reached MAX_ITEMS ({settings.MAX_ITEMS}). Stopping.")
            break

        logger.info(f"--- Collection: {c_title} [{c_id}] ---")
        
        candidates = raindrop_client.get_candidate_bookmarks(collection_id=c_id)
        new_candidates = [c for c in candidates if c['_id'] not in history]
        
        logger.info(f"Unprocessed in '{c_title}': {len(new_candidates)}")
        
        for item in new_candidates:
            # Check Global Limit per item
            if settings.MAX_ITEMS > 0 and processed_count >= settings.MAX_ITEMS:
                logger.info(f"Reached MAX_ITEMS ({settings.MAX_ITEMS}). Stopping.")
                break

            r_id = item['_id']
            raindrop_title = item.get('title', 'Untitled')
            url = item.get('link')
            
            logger.info(f"Processing ({processed_count + 1}/{settings.MAX_ITEMS}): {raindrop_title} ({url})")
            
            # DRY RUN Check
            if settings.DRY_RUN:
                if video_processor.verify_url(url):
                    logger.success(f"[DRY RUN] Valid: {url}")
                    # Increment count for dry run too, to test limit logic
                    processed_count += 1
                continue

            # 3. Verify Video
            if not video_processor.verify_url(url):
                logger.warning(f"Skipping value: {url}")
                continue
                
            try:
                # 4. Process Media
                transcript, audio_path, meta = video_processor.process(url)
                
                if not transcript and not audio_path:
                    logger.error("Failed to get media.")
                    continue
                
                # 5. LLM Summarize
                summary = ""
                images_md = ""

                # --- AI Director Mode (beta) ---
                # Only for videos < 10 mins to save bandwidth/time
                video_id = meta.get('id')
                duration_sec = meta.get('duration', 0)
                
                if video_id and duration_sec > 0 and duration_sec < 600:
                    logger.info("🎬 Entering AI Director Mode...")
                if video_id and duration_sec > 0 and duration_sec < 600:
                    logger.info("🎬 Entering AI Director Mode...")
                    try:
                        # 1. Init vars
                        visual_cues = []
                        temp_vid_path = None
                        
                        # 2. Strategy Selection
                        raw_transcript = video_processor.get_transcript_with_timestamps(video_id)
                        
                        if raw_transcript:
                            # Strategy A: Text Analysis (Fast, if subs exist)
                            logger.info("Analyzing Transcript for Visual Cues...")
                            visual_cues = llm.analyze_visual_cues(raw_transcript)
                            
                            if visual_cues:
                                # We have cues, NOW download the video to capture them
                                logger.info(f"Found {len(visual_cues)} cues. Downloading video...")
                                temp_vid_path = video_processor.download_video_temp(url)
                                
                        else:
                            # Strategy B: Video Analysis (Accurate, Fallback for FB/Reels)
                            logger.info("No transcript found. Downloading Video for Visual Analysis...")
                            temp_vid_path = video_processor.download_video_temp(url)
                            
                            if temp_vid_path and temp_vid_path.exists():
                                logger.info("Video downloaded. Asking AI to watch and find highlights...")
                                visual_cues = llm.analyze_visual_cues_from_video(temp_vid_path)

                        # 3. Execution (Capture)
                        logger.info(f"AI Final Decision: {len(visual_cues)} visual cues found.")
                        
                        if visual_cues and temp_vid_path and temp_vid_path.exists():
                                    # 4. Capture Frames
                                    frames_dir = settings.OUTPUT_DIR / "images" / video_id
                                    frames = video_processor.capture_best_frames(temp_vid_path, visual_cues, frames_dir)
                                    logger.info(f"Captured {len(frames)} frames.")
                                    
                                    # 5. Cleanup Video (Only if we are done with it)
                                    # Actually we delete it at the end of this block usually
                                    
                                    # 6. Upload to R2 and Delete Local
                                    from .storage import r2_storage
                                    import hashlib
                                    
                                    if frames:
                                        images_md = "\n\n## 🎬 Visual Highlights\n"
                                        
                                        # For Readwise HTML
                                        images_html_block = "<h3>🎬 Visual Highlights</h3>"
                                        
                                        for frame_path_str in frames:
                                            f_path = Path(frame_path_str)
                                            
                                            # Default to local path for detailed Markdown
                                            rel_path = f_path.relative_to(settings.OUTPUT_DIR)
                                            link_url = str(rel_path) 
                                            
                                            # Attempt R2 Upload
                                            if r2_storage.enabled:
                                                # Use Content Hash for Filename to allow deduplication/caching
                                                file_hash = hashlib.md5(f_path.read_bytes()).hexdigest()
                                                object_key = f"images/{file_hash}.jpg"
                                                
                                                public_url = r2_storage.upload_file(f_path, object_key)
                                                
                                                if public_url:
                                                    link_url = public_url
                                                    # Remove local file to save space
                                                    if f_path.exists():
                                                        os.remove(f_path)
                                                    logger.info(f"Uploaded & Deleted: {f_path.name} -> {object_key}")
                                            
                                            # Append to outputs
                                            images_md += f"![Key Frame]({link_url})\n"
                                            images_html_block += f'<img src="{link_url}" alt="Key Frame" style="max-width:100%; margin-top:10px; border-radius:8px;"><br>'
                                        
                                        images_html_block += "<hr>"

                                        # Clean up empty dir if all deleted
                                        if r2_storage.enabled:
                                            try:
                                                frames_dir.rmdir() 
                                            except: 
                                                pass

                        # Final Cleanup of temp video
                        if temp_vid_path and temp_vid_path.exists():
                            os.remove(temp_vid_path)
                            
                    except Exception as e:
                        logger.error(f"AI Director Mode failed: {e}")
                # -------------------------------
                # -------------------------------

                if transcript:
                    summary = llm.summarize_text(transcript)
                elif audio_path:
                    summary = llm.process_audio(audio_path)
                
                # 6. Prepare Output Metadata
                # Re-extract to ensure scope availability
                duration_sec = meta.get('duration', 0)
                uploader = meta.get('uploader', 'Unknown')
                
                # AI Title Generation
                logger.info("Generating concise title...")
                ai_title = llm.generate_concise_title(summary, raindrop_title)
                logger.info(f"AI Title: {ai_title}")
                
                # Filename Type Logic
                # > 8 mins (480s) = Video, else Short
                type_prefix = "[Video]" if duration_sec > 480 else "[Short]"
                
                def sanitize(s): return "".join([c for c in s if c.isalnum() or c in (' ','-','_')]).strip()
                
                # Use AI Title instead of raw title
                final_title_str = f"{type_prefix} {sanitize(ai_title)} - {sanitize(uploader)}"
                
                # Truncate if too long (max 100 to be safe logic?)
                if len(final_title_str) > 100:
                    final_title_str = final_title_str[:100]
                
                filename = f"{final_title_str}.md"
                output_path = settings.OUTPUT_DIR / filename

                
                # Markdown Content: Header -> Images -> Summary
                md_content = f"# {raindrop_title}\n\n**Source**: {url}\n**Author**: {uploader}\n**Collection**: {c_title}\n"
                
                if images_md:
                     md_content += images_md
                
                md_content += f"\n{summary}"
                
                # Save Local
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(md_content)
                logger.success(f"Saved: {output_path}")
                
                # 7. Save to Readwise
                from .readwise import readwise_client
                import markdown
                
                # Convert Markdown to HTML for Reader API
                # Extensions: extra (tables, footnotes), nl2br (newlines to br)
                html_rendered_summary = markdown.markdown(summary, extensions=['extra', 'nl2br'])
                
                # Add Metadata header to HTML
                html_header = f"""
                <p><strong>Source:</strong> <a href="{url}">{url}</a></p>
                <p><strong>Author:</strong> {uploader}</p>
                <p><strong>Collection:</strong> {c_title}</p>
                <hr>
                """
                
                # HTML Content: Header -> Images -> Summary
                final_html_body = html_header
                if 'images_html_block' in locals() and images_html_block:
                    final_html_body += images_html_block
                
                final_html_body += html_rendered_summary
                
                # Extract Cover Image
                cover_url = item.get('cover')
                
                readwise_client.save_summary(
                    url=url,
                    title=final_title_str,
                    summary_html=final_html_body,
                    tags=[c_title], # Tags: Collection Name Only
                    author=uploader,
                    image_url=cover_url
                )
                
                # 8. Update Raindrop
                existing_tags = item.get("tags", [])
                new_tags = list(set(existing_tags + ["summarized"]))
                raindrop_client.update_bookmark(r_id, tags=new_tags)
                
                # 9. Mark Done
                history.add(r_id)
                save_history(history)
                
                # Increment Counter (Count as processed since we saved results)
                processed_count += 1
                
                # Cleanup
                if audio_path and audio_path.exists():
                    os.remove(audio_path)
                    logger.info(f"Deleted audio file: {audio_path.name}")
                    
            except Exception as e:
                logger.error(f"Error processing {raindrop_title}: {e}")
                continue

if __name__ == "__main__":
    main()
