"""
Reference case database (SQLite).

Tables
------
reference_cases  – 70 % split of cleaned data, one row per case
  Columns: row_idx, sample_no, dept, label_diag, sex, age,
           hb, mcv, mch, mchc, sf, crp, rdw, engine_level, engine_severity

Usage
-----
    from src.data.db import ReferenceDB
    db = ReferenceDB()               # opens data/medic.db (creates if absent)
    similar = db.find_similar(hb=85, mcv=72, sex="female", top_k=5)
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent.parent
DB_PATH = ROOT / "data" / "medic.db"
REF_JSON = ROOT / "data" / "reference_cases.json"


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS reference_cases (
    row_idx       INTEGER PRIMARY KEY,
    sample_no     TEXT,
    dept          TEXT,
    label_diag    TEXT,
    sex           TEXT,
    age           INTEGER,
    hb            REAL,
    mcv           REAL,
    mch           REAL,
    mchc          REAL,
    sf            REAL,
    crp           REAL,
    rdw           REAL,
    engine_level    TEXT,
    engine_severity TEXT
);
"""

_INSERT = """
INSERT OR REPLACE INTO reference_cases
    (row_idx, sample_no, dept, label_diag,
     sex, age, hb, mcv, mch, mchc, sf, crp, rdw,
     engine_level, engine_severity)
VALUES
    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class ReferenceDB:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self._path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()

    # ── population ───────────────────────────────────────────────────────────

    def populate_from_json(self, json_path: Path = REF_JSON) -> int:
        """
        Load reference_cases.json produced by prepare_data.py and run the
        IDA engine on each case to store engine_level / engine_severity.
        Returns the number of rows inserted.
        """
        import sys
        sys.path.insert(0, str(ROOT))
        from src.ida import diagnose as ida_diagnose
        from src.ida.models import DiagnosisInput, PatientInput, LabInput

        cases: list[dict] = json.loads(json_path.read_text(encoding="utf-8"))
        rows: list[tuple] = []

        for c in cases:
            meta = c["meta"]
            inp = c["input"]
            p = inp["patient"]
            lab = inp["lab"]

            try:
                di = DiagnosisInput(
                    patient=PatientInput(
                        sex=p["sex"],
                        age=p["age"],
                        pregnant=p.get("pregnant", False),
                        precondition=p.get("precondition", False),
                    ),
                    lab=LabInput(
                        Hb=lab["Hb"],
                        MCV=lab["MCV"],
                        MCH=lab["MCH"],
                        MCHC=lab["MCHC"],
                        SF=lab.get("SF"),
                        CRP=lab.get("CRP"),
                        RDW=lab.get("RDW"),
                        serum_iron=lab.get("serum_iron"),
                        TIBC=lab.get("TIBC"),
                        TS=lab.get("TS"),
                    ),
                )
                out = ida_diagnose(di)
                level = out.level
                severity = out.severity
            except Exception:
                level = None
                severity = None

            rows.append((
                meta["row_idx"],
                meta.get("sample_no", ""),
                meta.get("dept", ""),
                meta.get("label_diag", ""),
                p["sex"],
                p["age"],
                lab["Hb"],
                lab["MCV"],
                lab["MCH"],
                lab["MCHC"],
                lab.get("SF"),
                lab.get("CRP"),
                lab.get("RDW"),
                level,
                severity,
            ))

        self._conn.executemany(_INSERT, rows)
        self._conn.commit()
        return len(rows)

    # ── queries ──────────────────────────────────────────────────────────────

    def find_similar(
        self,
        hb: float,
        mcv: float,
        sex: str,
        hb_tolerance: float = 15.0,
        mcv_tolerance: float = 10.0,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Return up to top_k reference cases whose HGB and MCV are within
        tolerance bands and whose sex matches.
        Results are sorted by Euclidean distance (HGB, MCV).
        """
        sql = """
            SELECT *,
                   ((hb - ?) * (hb - ?) + (mcv - ?) * (mcv - ?)) AS dist2
            FROM reference_cases
            WHERE sex = ?
              AND hb  BETWEEN ? AND ?
              AND mcv BETWEEN ? AND ?
            ORDER BY dist2
            LIMIT ?
        """
        cur = self._conn.execute(
            sql,
            (
                hb, hb,
                mcv, mcv,
                sex,
                hb  - hb_tolerance,  hb  + hb_tolerance,
                mcv - mcv_tolerance, mcv + mcv_tolerance,
                top_k,
            ),
        )
        return [dict(r) for r in cur.fetchall()]

    def stats(self) -> dict[str, Any]:
        """Return basic statistics about the reference DB."""
        cur = self._conn.execute(
            "SELECT engine_level, COUNT(*) as cnt FROM reference_cases GROUP BY engine_level"
        )
        level_dist = {row["engine_level"]: row["cnt"] for row in cur.fetchall()}
        total = sum(level_dist.values())
        return {"total": total, "by_level": level_dist}

    def close(self) -> None:
        self._conn.close()
