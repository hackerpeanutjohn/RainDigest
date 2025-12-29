import os
import json
import yt_dlp
from pathlib import Path
from typing import Optional, Tuple
from loguru import logger
from .config import settings

class VideoProcessor:
    def __init__(self, output_dir: Path = settings.DATA_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def verify_url(self, url: str) -> bool:
        """
        Check if the URL is supported by yt-dlp and is a video.
        """
        ydl_opts = {
            'simulate': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True, # Fast check
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                # If it's a playlist, info might be valid but have entries.
                # Use basic check: if info exists, it's widely supported.
                return True
            except Exception as e:
                logger.warning(f"Verification failed for {url}: {e}")
                return False

    def process(self, url: str) -> Tuple[Optional[str], Optional[Path], dict]:
        """
        Returns (transcript_text, audio_file_path, metadata).
        metadata includes 'duration', 'uploader', 'title'.
        """
        # Create a unique ID or use hash? 
        # For simplicity, let yt-dlp handle naming, but we need to find it back.
        # We'll use a specific template.
        file_id = f"%(id)s"
        out_tmpl = str(self.output_dir / f"{file_id}.%(ext)s")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': out_tmpl,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'zh-Hant', 'zh-Hans', 'zh'], # Prioritize Chinese, then English
            'quiet': True,
            'no_warnings': True,
        }
        
        meta = {}

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_id = info.get('id')
                
                # Extract Metadata
                meta['id'] = video_id
                meta['duration'] = info.get('duration', 0)
                meta['uploader'] = info.get('uploader') or info.get('channel') or "Unknown"
                meta['title'] = info.get('title')
                
                # Check for subtitles file
                transcript = self._find_and_parse_subs(video_id)
                
                audio_path = self.output_dir / f"{video_id}.mp3"
                if not audio_path.exists():
                    audio_path = None
                
                return transcript, audio_path, meta
                
        except Exception as e:
            logger.error(f"Download failed for {url}: {e}")
            return None, None, {}

    def _find_and_parse_subs(self, video_id: str) -> Optional[str]:
        """
        Look for generated subtitle files and parse them into plain text.
        """
        # Priorities
        langs = ['zh-Hant', 'zh-Hans', 'zh', 'en']
        
        for lang in langs:
            # yt-dlp format: id.lang.vtt
            # Check vtt and srt
            for ext in ['vtt', 'srt']:
                path = self.output_dir / f"{video_id}.{lang}.{ext}"
                if path.exists():
                    logger.info(f"Found subtitles: {path}")
                    return self._parse_vtt_or_srt(path)
        
        # Fallback: check any file starting with id and having sub extension
        # (This handles 'auto' generated subs properly if named differently)
        # Actually yt-dlp auto subs usually follow the pattern, e.g. video_id.en.vtt
        
        return None

    def _parse_vtt_or_srt(self, path: Path) -> str:
        """
        Simple parser to extract text from VTT/SRT, removing timestamps.
        """
        content = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            seen_lines = set()
            for line in lines:
                line = line.strip()
                if not line: continue
                if '-->' in line: continue 
                if line.isdigit(): continue
                if line.startswith('WEBVTT'): continue
                
                if line not in seen_lines:
                    content.append(line)
                    seen_lines.add(line)
            
            return "\n".join(content)
        except Exception as e:
            logger.error(f"Error parsing subtitle {path}: {e}")
            return None

    def get_transcript_with_timestamps(self, video_id: str) -> str:
        """
        Returns raw transcript with timestamps for LLM analysis.
        Tries to find the best subtitle file and return its content directly.
        """
        # Priorities: vtt, srt
        langs = ['zh-Hant', 'zh-Hans', 'zh', 'en']
        for lang in langs:
            for ext in ['vtt', 'srt']:
                path = self.output_dir / f"{video_id}.{lang}.{ext}"
                if path.exists():
                    try:
                        return path.read_text(encoding='utf-8')
                    except Exception as e:
                        logger.error(f"Error reading {path}: {e}")
        return ""

    def download_video_temp(self, url: str) -> Optional[Path]:
        """
        Download video for frame extraction (temp usage).
        Returns path to .mp4 file.
        """
        out_tmpl = str(self.output_dir / "temp_director_video.%(ext)s")
        # Ensure we get mp4 for opencv compatibility
        # Force H.264 (avc1) to avoid AV1 issues on some platforms (like ARM64 docker)
        ydl_opts = {
            'format': 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': out_tmpl,
            'quiet': True,
            'overwrites': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                # Find the file (yt-dlp might change extension slightly?)
                # We forced mp4/mkv, but let's check.
                # Usually it will be temp_director_video.mp4
                p = self.output_dir / "temp_director_video.mp4"
                if p.exists(): return p
                # Fallback check
                for f in self.output_dir.glob("temp_director_video.*"):
                    return f
                return None
        except Exception as e:
            logger.error(f"Temp video download failed: {e}")
            return None

    def capture_best_frames(self, video_path: Path, timestamps: list, output_dir: Path) -> list:
        """
        Capture frames at specific timestamps.
        Implements Multi-frame sampling (t, t+1, t+2) to find best image.
        """
        import cv2
        import numpy as np
        
        if not cv2 or not video_path.exists():
            return []
            
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.error("Failed to open video for capture.")
            return []
            
        saved_frames = []
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for item in timestamps:
            target_time = item.get('timestamp', 0)
            reason = item.get('reason', 'key_moment')
            
            best_score = -1
            best_frame = None
            best_time = target_time
            
            # Multi-frame sampling: check t, t+1, t+1.5
            offsets = [0, 1.0, 1.5] 
            
            for offset in offsets:
                check_time = target_time + offset
                cap.set(cv2.CAP_PROP_POS_MSEC, check_time * 1000)
                ret, frame = cap.read()
                if not ret: continue
                
                # Calculate Information Density (Edge Detection)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, 100, 200)
                score = np.mean(edges)
                
                if score > best_score:
                    best_score = score
                    best_frame = frame
                    best_time = check_time
            
            if best_frame is not None:
                # Save Frame
                safe_reason = "".join([c for c in reason if c.isalnum()])[:20]
                frame_name = f"{int(best_time)}_{safe_reason}.jpg"
                out_path = output_dir / frame_name
                cv2.imwrite(str(out_path), best_frame)
                saved_frames.append(str(out_path))
                logger.info(f"Captured frame at {best_time}s: {reason}")
                
        cap.release()
        return saved_frames
