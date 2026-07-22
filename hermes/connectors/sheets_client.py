"""Google Sheets connector for Hermes (service-account auth).

Reads/writes the PO Tracker spreadsheet. Auth is a service-account key — no user
consent and no token expiry. The Sheet must be shared with the service account's
email (Editor so Hermes can write order updates). It only reads, appends, updates
cell ranges, and *additively* creates/formats tabs — it has no method that deletes
the spreadsheet, a tab, or any data.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsError(RuntimeError):
    pass


@dataclass
class SheetsClient:
    service: object
    spreadsheet_id: str

    @classmethod
    def from_config(cls, cfg: dict, key: str = "spreadsheet_id") -> "SheetsClient":
        """``key`` picks which sheets.<key> id to bind: the PO Tracker (default)
        or the separate Quotes workbook (key="quotes_spreadsheet_id")."""
        sh = cfg["sheets"]
        sa_path = Path(sh["service_account_path"])
        spreadsheet_id = sh.get(key) or ""
        if not sa_path.exists():
            raise SheetsError(f"Missing service-account key at {sa_path}")
        if not spreadsheet_id:
            raise SheetsError(f"sheets.{key} is not set — add its env var to .secrets/.env (see .env.example)")
        creds = Credentials.from_service_account_file(str(sa_path), scopes=SCOPES)
        service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        return cls(service=service, spreadsheet_id=spreadsheet_id)

    # ---- read ----
    def meta(self) -> dict:
        return self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()

    def tab_names(self) -> list[str]:
        return [s["properties"]["title"] for s in self.meta().get("sheets", [])]

    def read(self, a1_range: str) -> list[list]:
        resp = (
            self.service.spreadsheets().values()
            .get(spreadsheetId=self.spreadsheet_id, range=a1_range)
            .execute()
        )
        return resp.get("values", [])

    # ---- write (additive: append / update; never deletes) ----
    def append_row(self, tab: str, row: list) -> dict:
        return (
            self.service.spreadsheets().values()
            .append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{tab}!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            )
            .execute()
        )

    def update_range(self, a1_range: str, rows: list[list]) -> dict:
        return (
            self.service.spreadsheets().values()
            .update(
                spreadsheetId=self.spreadsheet_id,
                range=a1_range,
                valueInputOption="USER_ENTERED",
                body={"values": rows},
            )
            .execute()
        )

    # ---- structure (additive: create/format tabs; never deletes) ----
    def _batch(self, requests: list[dict]) -> dict:
        return (
            self.service.spreadsheets()
            .batchUpdate(spreadsheetId=self.spreadsheet_id, body={"requests": requests})
            .execute()
        )

    def sheet_ids(self) -> dict[str, int]:
        """Map of tab title -> numeric sheetId."""
        return {
            s["properties"]["title"]: s["properties"]["sheetId"]
            for s in self.meta().get("sheets", [])
        }

    def ensure_tab(self, title: str) -> int:
        """Create the tab if missing (idempotent). Returns its numeric sheetId."""
        ids = self.sheet_ids()
        if title in ids:
            return ids[title]
        resp = self._batch([{"addSheet": {"properties": {"title": title}}}])
        return resp["replies"][0]["addSheet"]["properties"]["sheetId"]

    def format_header(self, sheet_id: int, n_cols: int, rgb=(0.20, 0.33, 0.51),
                      freeze: bool = True) -> dict:
        """Bold white header on a colored band across row 1; freeze it."""
        r, g, b = rgb
        reqs = [
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                              "startColumnIndex": 0, "endColumnIndex": n_cols},
                    "cell": {"userEnteredFormat": {
                        "backgroundColor": {"red": r, "green": g, "blue": b},
                        "horizontalAlignment": "LEFT",
                        "textFormat": {"bold": True,
                                       "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                    }},
                    "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)",
                }
            }
        ]
        if freeze:
            reqs.append({
                "updateSheetProperties": {
                    "properties": {"sheetId": sheet_id,
                                   "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            })
        return self._batch(reqs)

    def color_columns(self, sheet_id: int, col_start: int, col_end: int, rgb,
                      row_start: int = 0, row_end: int = 1) -> dict:
        """Tint a header sub-range (e.g. mark the human-owned column block)."""
        r, g, b = rgb
        return self._batch([{
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_start, "endRowIndex": row_end,
                          "startColumnIndex": col_start, "endColumnIndex": col_end},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": r, "green": g, "blue": b}}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        }])

    def add_dropdown(self, sheet_id: int, col_index: int, values: list[str],
                     start_row: int = 1, end_row: int = 2000) -> dict:
        """Attach a one-of-list validation (dropdown) to a column below the header."""
        return self._batch([{
            "setDataValidation": {
                "range": {"sheetId": sheet_id, "startRowIndex": start_row, "endRowIndex": end_row,
                          "startColumnIndex": col_index, "endColumnIndex": col_index + 1},
                "rule": {
                    "condition": {"type": "ONE_OF_LIST",
                                  "values": [{"userEnteredValue": v} for v in values]},
                    "showCustomUi": True, "strict": False,
                },
            }
        }])

    def auto_resize(self, sheet_id: int, n_cols: int) -> dict:
        return self._batch([{
            "autoResizeDimensions": {
                "dimensions": {"sheetId": sheet_id, "dimension": "COLUMNS",
                               "startIndex": 0, "endIndex": n_cols}
            }
        }])

    # ---- richer formatting (idempotent via clear_visual_rules first) ----
    def clear_visual_rules(self, sheet_id: int) -> None:
        """Remove existing conditional-format rules and bandings so a re-run won't stack them."""
        sheet = next((s for s in self.meta().get("sheets", [])
                      if s["properties"]["sheetId"] == sheet_id), None)
        if not sheet:
            return
        reqs: list[dict] = []
        for i in range(len(sheet.get("conditionalFormats", [])) - 1, -1, -1):
            reqs.append({"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": i}})
        for br in sheet.get("bandedRanges", []):
            reqs.append({"deleteBanding": {"bandedRangeId": br["bandedRangeId"]}})
        if reqs:
            self._batch(reqs)

    def add_banding(self, sheet_id: int, n_cols: int,
                    header_rgb=(0.20, 0.33, 0.51), band_rgb=(0.95, 0.96, 0.98)) -> dict:
        """Alternating white / tinted data rows for readability."""
        hr, hg, hb = header_rgb
        br, bg, bb = band_rgb
        return self._batch([{
            "addBanding": {"bandedRange": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0,
                          "startColumnIndex": 0, "endColumnIndex": n_cols},
                "rowProperties": {
                    "headerColor": {"red": hr, "green": hg, "blue": hb},
                    "firstBandColor": {"red": 1, "green": 1, "blue": 1},
                    "secondBandColor": {"red": br, "green": bg, "blue": bb},
                },
            }}
        }])

    def add_conditional_rule(self, sheet_id: int, n_cols: int, formula: str, rgb) -> dict:
        """Tint whole data rows (row 2+) where a CUSTOM_FORMULA is true (e.g. '=$H2=\"Needs Review\"')."""
        r, g, b = rgb
        return self._batch([{
            "addConditionalFormatRule": {
                "index": 0,
                "rule": {
                    "ranges": [{"sheetId": sheet_id, "startRowIndex": 1,
                                "startColumnIndex": 0, "endColumnIndex": n_cols}],
                    "booleanRule": {
                        "condition": {"type": "CUSTOM_FORMULA",
                                      "values": [{"userEnteredValue": formula}]},
                        "format": {"backgroundColor": {"red": r, "green": g, "blue": b}},
                    },
                },
            }
        }])

    def set_number_format(self, sheet_id: int, col_index: int, pattern: str,
                          ntype: str = "NUMBER") -> dict:
        return self._batch([{
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1,
                          "startColumnIndex": col_index, "endColumnIndex": col_index + 1},
                "cell": {"userEnteredFormat": {"numberFormat": {"type": ntype, "pattern": pattern}}},
                "fields": "userEnteredFormat.numberFormat",
            }
        }])

    def hide_columns(self, sheet_id: int, indices: list[int], hidden: bool = True) -> None:
        reqs = [{
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                          "startIndex": i, "endIndex": i + 1},
                "properties": {"hiddenByUser": hidden},
                "fields": "hiddenByUser",
            }
        } for i in indices]
        if reqs:
            self._batch(reqs)

    def set_basic_filter(self, sheet_id: int, n_cols: int) -> dict:
        """Enable the header filter so anyone can filter by salesperson / status."""
        return self._batch([{
            "setBasicFilter": {"filter": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0,
                          "startColumnIndex": 0, "endColumnIndex": n_cols}
            }}
        }])
