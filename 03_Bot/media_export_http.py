"""Authenticated HTTP bridge for Relife patient report media.

Legacy patient photos are durable Telegram file IDs. This module extends the
small Render health server so the Owner Web App can stream those files without
exposing BOT_TOKEN, Telegram file IDs, or the master bridge secret.

Normal server-to-server calls use X-Relife-Media-Key. A batch archive endpoint
also accepts a short-lived HMAC signature so migration tooling can download a
patient-wise ZIP without putting the master secret in a URL.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import re
import time
import zipfile
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

from http.server import HTTPServer


_INSTALLED = False
_ORIGINAL_FINISH_REQUEST = None


def _send(handler, status: int, body: bytes, content_type: str, **headers) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Cache-Control", "private, no-store")
    for key, value in headers.items():
        handler.send_header(key.replace("_", "-"), str(value))
    handler.end_headers()
    handler.wfile.write(body)


def _json(handler, status: int, payload: object) -> None:
    _send(
        handler,
        status,
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        "application/json; charset=utf-8",
    )


def _secret() -> str:
    return os.environ.get("MEDIA_EXPORT_SECRET", "").strip()


def _header_authorized(handler) -> bool:
    configured = _secret()
    supplied = str(handler.headers.get("X-Relife-Media-Key", "")).strip()
    return bool(configured) and hmac.compare_digest(configured, supplied)


def _department(value: str) -> str | None:
    normalized = str(value or "").strip().casefold()
    if normalized == "physio":
        return "Physio"
    if normalized == "dental":
        return "Dental"
    return None


def _int_query(query: dict[str, list[str]], key: str, default: int) -> int:
    try:
        return int((query.get(key) or [str(default)])[0])
    except (TypeError, ValueError):
        return default


def _batch_signature_message(
    department: str, start: int, limit: int, expires: int
) -> bytes:
    return f"batch|{department}|{start}|{limit}|{expires}".encode("utf-8")


def _signed_batch_authorized(
    query: dict[str, list[str]], department: str, start: int, limit: int
) -> bool:
    configured = _secret()
    if not configured:
        return False
    expires = _int_query(query, "expires", 0)
    supplied = str((query.get("sig") or [""])[0]).strip()
    now = int(time.time())
    # Signed migration links are deliberately short-lived; reject both expired
    # links and unexpectedly long-lived tickets.
    if expires < now or expires > now + 3600 or not supplied:
        return False
    expected = hmac.new(
        configured.encode("utf-8"),
        _batch_signature_message(department, start, limit, expires),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, supplied)


def _report_rows(department: str) -> list[dict]:
    # Lazy imports avoid a config/sheets circular import during bot bootstrap.
    import config
    import sheet_scope
    import sheets

    with sheet_scope.use_sheet(config.sheet_id_for_department(department)):
        ws = sheets._worksheet(config.SHEET_REPORTS)
        return sheets.safe_get_all_records(ws, _use_cache=False)


def _find_report(department: str, report_id: str) -> dict | None:
    wanted = str(report_id or "").strip()
    for row in _report_rows(department):
        if str(row.get("Report_ID", "")).strip() == wanted:
            return row
    return None


def _telegram_file_bytes(file_id: str) -> tuple[bytes, str]:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not configured")

    get_file_url = (
        f"https://api.telegram.org/bot{quote(token, safe=':')}/getFile?"
        f"file_id={quote(file_id, safe='')}"
    )
    with urlopen(
        Request(get_file_url, headers={"User-Agent": "Relife-Media-Bridge/1"}),
        timeout=20,
    ) as response:
        payload = json.loads(response.read().decode("utf-8"))
    file_path = str((payload.get("result") or {}).get("file_path") or "").strip()
    if not payload.get("ok") or not file_path:
        raise RuntimeError("Telegram getFile did not return a file path")

    download_url = f"https://api.telegram.org/file/bot{quote(token, safe=':')}/{file_path}"
    with urlopen(
        Request(download_url, headers={"User-Agent": "Relife-Media-Bridge/1"}),
        timeout=30,
    ) as response:
        body = response.read()
        content_type = response.headers.get_content_type() or "application/octet-stream"
    return body, content_type


def _safe_filename(value: str, fallback: str) -> str:
    name = str(value or "").strip().replace("\r", "_").replace("\n", "_")
    name = name.replace('"', "'")
    return name[:180] or fallback


def _safe_path_part(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", str(value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return (cleaned[:120] or fallback)


def _eligible_rows(department: str) -> list[dict]:
    return [
        row
        for row in _report_rows(department)
        if str(row.get("Report_ID", "")).strip()
        and str(row.get("File_Telegram_ID", "")).strip()
    ]


def _batch_zip(department: str, rows: list[dict], start: int) -> bytes:
    buffer = io.BytesIO()
    manifest = []
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for offset, row in enumerate(rows):
            report_id = str(row.get("Report_ID", "")).strip()
            patient_id = str(row.get("Patient_ID", "")).strip() or "UNKNOWN"
            patient_name = str(row.get("Patient_Name", "")).strip() or "Unknown"
            file_name = _safe_filename(
                str(row.get("File_Name", "")), f"{report_id}.bin"
            )
            patient_dir = _safe_path_part(
                f"{patient_id} - {patient_name}", patient_id
            )
            archive_name = f"{patient_dir}/{report_id}_{_safe_path_part(file_name, report_id)}"
            item = {
                "index": start + offset,
                "reportId": report_id,
                "patientId": patient_id,
                "patientName": patient_name,
                "fileName": file_name,
                "uploadDate": str(row.get("Upload_Date", "")).strip(),
                "archivePath": archive_name,
                "ok": False,
            }
            try:
                body, _content_type = _telegram_file_bytes(
                    str(row.get("File_Telegram_ID", "")).strip()
                )
                archive.writestr(archive_name, body)
                item["ok"] = True
            except Exception as exc:
                error_path = f"{patient_dir}/{report_id}.error.txt"
                archive.writestr(error_path, str(exc)[:500])
                item["error"] = str(exc)[:160]
            manifest.append(item)
        archive.writestr(
            "_relife_manifest.json",
            json.dumps(
                {"department": department, "start": start, "items": manifest},
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
        )
    return buffer.getvalue()


def _handle_media_export(handler) -> bool:
    parsed = urlparse(handler.path)
    if not parsed.path.startswith("/internal/media-export/"):
        return False

    query = parse_qs(parsed.query, keep_blank_values=True)
    department = _department((query.get("department") or [""])[0])
    if not department:
        _json(handler, 400, {"ok": False, "error": "invalid_department"})
        return True

    start = max(0, _int_query(query, "start", 0))
    limit = min(25, max(1, _int_query(query, "limit", 25)))
    batch_signed = (
        parsed.path == "/internal/media-export/batch"
        and _signed_batch_authorized(query, department, start, limit)
    )
    if not (_header_authorized(handler) or batch_signed):
        _json(handler, 404, {"ok": False})
        return True

    if parsed.path == "/internal/media-export/manifest":
        rows = _eligible_rows(department)
        items = [
            {
                "reportId": str(row.get("Report_ID", "")).strip(),
                "patientId": str(row.get("Patient_ID", "")).strip(),
                "patientName": str(row.get("Patient_Name", "")).strip(),
                "fileName": str(row.get("File_Name", "")).strip(),
                "fileType": str(row.get("File_Type", "")).strip(),
                "uploadDate": str(row.get("Upload_Date", "")).strip(),
                "driveLink": str(row.get("File_Drive_Link", "")).strip(),
                "department": department,
            }
            for row in rows
        ]
        _json(handler, 200, {"ok": True, "department": department, "items": items})
        return True

    if parsed.path == "/internal/media-export/batch":
        rows = _eligible_rows(department)
        selected = rows[start : start + limit]
        body = _batch_zip(department, selected, start)
        _send(
            handler,
            200,
            body,
            "application/zip",
            Content_Disposition=(
                f'attachment; filename="relife-{department.lower()}-media-{start:03d}.zip"'
            ),
            X_Relife_Total=str(len(rows)),
            X_Relife_Batch_Count=str(len(selected)),
        )
        return True

    if parsed.path == "/internal/media-export/file":
        report_id = (query.get("report_id") or [""])[0]
        report = _find_report(department, report_id)
        if not report:
            _json(handler, 404, {"ok": False, "error": "report_not_found"})
            return True
        file_id = str(report.get("File_Telegram_ID", "")).strip()
        if not file_id:
            _json(handler, 404, {"ok": False, "error": "telegram_file_missing"})
            return True
        try:
            body, content_type = _telegram_file_bytes(file_id)
        except Exception as exc:
            _json(
                handler,
                502,
                {
                    "ok": False,
                    "error": "telegram_fetch_failed",
                    "detail": str(exc)[:160],
                },
            )
            return True

        filename = _safe_filename(
            str(report.get("File_Name", "")),
            f"{report_id}.bin",
        )
        _send(
            handler,
            200,
            body,
            content_type,
            Content_Disposition=f'inline; filename="{filename}"',
            X_Relife_Report_Id=report_id,
            X_Relife_Patient_Id=str(report.get("Patient_ID", "")),
        )
        return True

    _json(handler, 404, {"ok": False})
    return True


def install_media_export_hook() -> None:
    """Wrap only the bot's tiny Render health handler at request time."""
    global _INSTALLED, _ORIGINAL_FINISH_REQUEST
    if _INSTALLED:
        return
    _INSTALLED = True
    _ORIGINAL_FINISH_REQUEST = HTTPServer.finish_request

    def finish_request(server, request, client_address):
        handler_cls = server.RequestHandlerClass
        if (
            getattr(handler_cls, "__name__", "") == "_HealthHandler"
            and not getattr(handler_cls, "_relife_media_export_wrapped", False)
        ):
            original_do_get = handler_cls.do_GET

            def do_GET(handler):
                try:
                    if _handle_media_export(handler):
                        return
                except Exception as exc:
                    _json(
                        handler,
                        500,
                        {
                            "ok": False,
                            "error": "media_bridge_error",
                            "detail": str(exc)[:160],
                        },
                    )
                    return
                return original_do_get(handler)

            handler_cls.do_GET = do_GET
            handler_cls._relife_media_export_wrapped = True
        return _ORIGINAL_FINISH_REQUEST(server, request, client_address)

    HTTPServer.finish_request = finish_request
