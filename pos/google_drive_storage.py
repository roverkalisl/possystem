import base64
import io
import json
import os

from django.conf import settings


SCOPES = ["https://www.googleapis.com/auth/drive"]


def _get_service_account_info():
    raw_json = os.environ.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw_json:
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValueError("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc

    raw_b64 = os.environ.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_BASE64", "").strip()
    if raw_b64:
        try:
            decoded = base64.b64decode(raw_b64, validate=True)
            return json.loads(decoded.decode("utf-8"))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("GOOGLE_DRIVE_SERVICE_ACCOUNT_BASE64 is not valid base64 JSON.") from exc

    return None


def _get_folder_id():
    folder_id = os.environ.get("GOOGLE_DRIVE_BACKUP_FOLDER_ID", "").strip()
    if not folder_id:
        raise ValueError("GOOGLE_DRIVE_BACKUP_FOLDER_ID is not set.")
    return folder_id


def _get_drive_service():
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    
    service_account_info = _get_service_account_info()
    if not service_account_info:
        raise ValueError("Google Drive service account credentials are not configured.")

    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )
    credentials.refresh(Request())
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


class GoogleDriveStorage:
    location_code = "google_drive"

    def status(self):
        try:
            _get_folder_id()
            _get_drive_service().files().list(pageSize=1, fields="nextPageToken, files(id)").execute()
            return "connected"
        except ValueError:
            return "not_configured"
        except Exception:
            return "connection_failed"

    def save(self, file_name, content_bytes):
        from googleapiclient.http import MediaIoBaseUpload
        
        folder_id = _get_folder_id()
        service = _get_drive_service()
        metadata = {
            "name": file_name,
            "parents": [folder_id],
        }
        media = MediaIoBaseUpload(io.BytesIO(content_bytes), mimetype="application/gzip", resumable=False)
        file_obj = service.files().create(body=metadata, media_body=media, fields="id").execute()
        return f"gdrive://{file_obj.get('id')}"

    def delete(self, file_path, record=None):
        from googleapiclient.errors import HttpError
        
        file_id = self._extract_file_id(file_path, record)
        if not file_id:
            return
        try:
            _get_drive_service().files().delete(fileId=file_id).execute()
        except HttpError as exc:
            if exc.resp.status == 404:
                return
            raise

    def open_for_download(self, file_path, record=None):
        from googleapiclient.http import MediaIoBaseDownload
        
        file_id = self._extract_file_id(file_path, record)
        if not file_id:
            raise ValueError("No Google Drive file ID was found for this backup.")

        service = _get_drive_service()
        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        buffer.seek(0)
        return buffer

    @staticmethod
    def _extract_file_id(file_path, record=None):
        if not file_path:
            return None
        if file_path.startswith("gdrive://"):
            return file_path.replace("gdrive://", "", 1)
        if record and getattr(record, "google_drive_file_id", None):
            return record.google_drive_file_id
        return None
