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

r2_storage = R2Storage()
