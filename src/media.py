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
                
            seen_lines = set() # Dedup lines that might repeat in vtt
            for line in lines:
                line = line.strip()
                if not line: continue
                if '-->' in line: continue # Timestamp
                if line.isdigit(): continue # Sequnce number
                if line.startswith('WEBVTT'): continue
                
                # Basic dedup
                if line not in seen_lines:
                    content.append(line)
                    seen_lines.add(line)
            
            return "\n".join(content)
        except Exception as e:
            logger.error(f"Error parsing subtitle {path}: {e}")
            return None
