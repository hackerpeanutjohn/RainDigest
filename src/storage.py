import boto3
from botocore.exceptions import ClientError
from pathlib import Path
from loguru import logger
from .config import settings

class R2Storage:
    def __init__(self):
        self.enabled = False
        if all([settings.R2_ACCOUNT_ID, settings.R2_ACCESS_KEY_ID, settings.R2_SECRET_ACCESS_KEY, settings.R2_BUCKET_NAME, settings.R2_PUBLIC_DOMAIN]):
            self.enabled = True
            try:
                self.s3_client = boto3.client(
                    service_name='s3',
                    endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
                    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                    region_name='auto' 
                )
                logger.info("Cloudflare R2 Storage Initialized.")
            except Exception as e:
                logger.error(f"Failed to init R2 Storage: {e}")
                self.enabled = False
        else:
            logger.warning("R2 Credentials missing. Image uploads disabled.")

    def upload_file(self, file_path: Path, object_name: str = None) -> str:
        """
        Upload a file to R2 and return its Public URL.
        """
        if not self.enabled:
            return None

        if object_name is None:
            object_name = file_path.name

        try:
            # Determine Content Type
            content_type = 'application/octet-stream'
            if file_path.suffix.lower() in ['.jpg', '.jpeg']:
                content_type = 'image/jpeg'
            elif file_path.suffix.lower() == '.png':
                content_type = 'image/png'

            self.s3_client.upload_file(
                str(file_path), 
                settings.R2_BUCKET_NAME, 
                object_name,
                ExtraArgs={'ContentType': content_type}
            )
            
            # Construct Public URL
            # Ensure no double slashes if domain ends with /
            domain = settings.R2_PUBLIC_DOMAIN.rstrip('/')
            url = f"{domain}/{object_name}"
            
            logger.info(f"Uploaded to R2: {url}")
            return url

        except ClientError as e:
            logger.error(f"R2 Upload Failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Storage Error: {e}")
            return None


    def cleanup_old_files(self, retention_days: int = 30):
        """
        Delete files in R2 bucket older than retention_days.
        """
        if not self.enabled:
            return

        try:
            from datetime import datetime, timezone, timedelta
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
            logger.info(f"Checking for R2 files older than {retention_days} days (before {cutoff_date})...")

            # List objects
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=settings.R2_BUCKET_NAME)

            objects_to_delete = []
            
            for page in page_iterator:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    if obj['LastModified'] < cutoff_date:
                        objects_to_delete.append({'Key': obj['Key']})

            if objects_to_delete:
                logger.info(f"Found {len(objects_to_delete)} old files to delete.")
                
                # Delete in batches of 1000 (S3 limit)
                for i in range(0, len(objects_to_delete), 1000):
                    batch = objects_to_delete[i:i+1000]
                    self.s3_client.delete_objects(
                        Bucket=settings.R2_BUCKET_NAME,
                        Delete={'Objects': batch}
                    )
                    logger.info(f"Deleted batch of {len(batch)} files.")
            else:
                logger.info("No old files found to cleanup.")

        except Exception as e:
            logger.error(f"R2 Cleanup failed: {e}")

r2_storage = R2Storage()

