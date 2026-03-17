"""
数据准备脚本
1. 读取 data/data.csv（GBK 编码）
2. 去除敏感字段（证件号码、姓名）
3. 映射列名 → DiagnosisInput 字段
4. 70% 作为参考病例库，30% 作为端到端测试集
5. 输出：
   - data/reference_cases.json  （70%，供检索链路使用）
   - data/test_cases.json        （30%，供 E2E 测试使用）
   - data/cleaned_data.csv       （已脱敏的完整数据，方便人工核查）

运行：python scripts/prepare_data.py
"""

import csv
import io
import json
import re
import random
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
RAW_CSV = DATA_DIR / "data.csv"

# ── 敏感字段（直接删除）─────────────────────────────────────────
SENSITIVE_COLS = {"证件号码", "姓名"}

# ── CSV列 → DiagnosisInput 字段映射 ───────────────────────────
# lab 字段
LAB_COL_MAP = {
    "HGB":     "Hb",        # g/L
    "MCV":     "MCV",       # fL
    "MCH":     "MCH",       # pg
    "MCHC":    "MCHC",      # 注意：CSV 可能是 g/L（如 320），需换算为 0~1（÷1000）
    "FERRITIN":"SF",         # μg/L — 等同于血清铁蛋白
    "CRP":     "CRP",       # mg/L
    "RDW-CV":  "RDW",       # %（可选）
}

# patient 字段
PATIENT_COL_MAP = {
    "性别": "sex",   # 男 → male, 女 → female
    "年龄": "age",   # int
}

# 标签字段（用于测试验证，不送入引擎）
LABEL_COLS = {"诊断", "临床诊断"}


def parse_float(val: str) -> float | None:
    """解析数值，支持 '<0.5' / '>100' 前缀，返回 None 表示缺失/无效。"""
    if val is None:
        return None
    v = val.strip()
    if v in ("", "—", "-", "N/A", "nan", "NaN", "NULL"):
        return None
    # Strip leading comparison operators
    v = re.sub(r"^[<>≤≥]\s*", "", v)
    try:
        return float(v)
    except ValueError:
        return None


def parse_age(val: str) -> int | None:
    """Parse Chinese age strings (e.g. '56岁', '3月', '9日') → integer years."""
    if val is None:
        return None
    v = str(val).strip()
    if v in ("", "岁"):
        return None
    # "56岁" or bare "56"
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(岁|年)?$", v)
    if m:
        return max(0, int(float(m.group(1))))
    # months
    m = re.match(r"^(\d+)\s*(月|个月)$", v)
    if m:
        return 0
    # days / 日 / 天
    m = re.match(r"^(\d+)\s*(日|天)$", v)
    if m:
        return 0
    # weeks
    m = re.match(r"^(\d+)\s*(周|w)$", v, re.IGNORECASE)
    if m:
        return 0
    return None


def parse_sex(val: str) -> str | None:
    v = val.strip()
    if v in ("男", "M", "male"):
        return "male"
    if v in ("女", "F", "female"):
        return "female"
    return None


def parse_mchc(raw: float | None) -> float | None:
    """MCHC 单位换算：若 > 1 则认为是 g/L 格式，÷ 1000 转为 0~1。"""
    if raw is None:
        return None
    return raw / 1000 if raw > 1 else raw


def row_to_case(headers: list[str], row: list[str], row_idx: int) -> dict | None:
    """将一行 CSV 数据转换为结构化病例字典。缺少必须字段时返回 None。"""
    h2v = {h: row[i] if i < len(row) else "" for i, h in enumerate(headers)}

    # ── 患者信息 ────────────────────────────────────────────────
    sex = parse_sex(h2v.get("性别", ""))
    age = parse_age(h2v.get("年龄", ""))
    if sex is None or age is None:
        return None   # 性别/年龄缺失，跳过

    # ── 检验指标 ────────────────────────────────────────────────
    hb  = parse_float(h2v.get("HGB", ""))
    mcv = parse_float(h2v.get("MCV", ""))
    mch = parse_float(h2v.get("MCH", ""))
    mchc_raw = parse_float(h2v.get("MCHC", ""))

    # 必须字段：HGB、MCV、MCH、MCHC
    if any(v is None for v in (hb, mcv, mch, mchc_raw)):
        return None

    mchc = parse_mchc(mchc_raw)
    sf   = parse_float(h2v.get("FERRITIN", ""))
    crp  = parse_float(h2v.get("CRP", ""))
    rdw  = parse_float(h2v.get("RDW-CV", ""))

    # ── 标签 ─────────────────────────────────────────────────────
    label_diag    = h2v.get("诊断", "").strip()
    label_clinical = h2v.get("临床诊断", "").strip()

    # ── 保留元数据（脱敏后）────────────────────────────────────
    meta = {
        "row_idx": row_idx,
        "sample_no": h2v.get("样本号", "").strip(),
        "dept": h2v.get("科室", "").strip(),
        "label_diag": label_diag,
        "label_clinical": label_clinical,
    }

    return {
        "meta": meta,
        "input": {
            "patient": {
                "sex": sex,
                "age": age,
                "pregnant": False,   # CSV 无妊娠字段，默认 False
                "precondition": False,
            },
            "lab": {
                "Hb":   hb,
                "MCV":  mcv,
                "MCH":  mch,
                "MCHC": mchc,
                "SF":   sf,
                "CRP":  crp,
                "RDW":  rdw,
                # 以下字段 CSV 中未提供，置 None（引擎会跳过对应条款）
                "serum_iron": None,
                "TIBC":       None,
                "TS":         None,
            },
            "clinical": None,   # CSV 无病因/体征字段
        },
    }


def load_csv() -> tuple[list[str], list[dict]]:
    """加载并解析 CSV，返回 (headers_without_sensitive, cases)。"""
    with open(RAW_CSV, encoding="gbk", errors="replace", newline="") as f:
        content = f.read()

    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    rows = [r for r in reader if any(v.strip() for v in r)]

    print(f"CSV 原始：{len(headers)} 列，{len(rows)} 数据行")

    # 检查敏感列
    sensitive_found = [h for h in headers if h in SENSITIVE_COLS]
    print(f"发现敏感字段：{sensitive_found}（已移除）")

    cases = []
    skipped = 0
    for idx, row in enumerate(rows):
        case = row_to_case(headers, row, idx)
        if case is None:
            skipped += 1
        else:
            cases.append(case)

    print(f"有效病例：{len(cases)}，跳过（缺必须字段）：{skipped}")
    return headers, cases


def save_cleaned_csv(headers: list[str]) -> None:
    """Re-read raw CSV and save a cleaned copy with sensitive columns removed."""
    clean_headers = [h for h in headers if h not in SENSITIVE_COLS]
    sensitive_indices = {i for i, h in enumerate(headers) if h in SENSITIVE_COLS}
    out_path = DATA_DIR / "cleaned_data.csv"

    with open(RAW_CSV, encoding="gbk", errors="replace", newline="") as fin, \
         open(out_path, "w", encoding="utf-8-sig", newline="") as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout)
        next(reader)  # skip original header
        writer.writerow(clean_headers)
        for row in reader:
            clean_row = [v for i, v in enumerate(row) if i not in sensitive_indices]
            writer.writerow(clean_row)

    print(f"脱敏 CSV 已保存：{out_path}")


def split_and_save(cases: list[dict]) -> None:
    """70/30 分割，保存参考病例库和测试集。"""
    if not cases:
        print("⚠️  数据集为空（CSV 无数据行），输出空文件作为占位。")
        (DATA_DIR / "reference_cases.json").write_text("[]", encoding="utf-8")
        (DATA_DIR / "test_cases.json").write_text("[]", encoding="utf-8")
        return

    random.seed(42)   # 固定随机种子，保证可复现
    shuffled = cases.copy()
    random.shuffle(shuffled)

    split = int(len(shuffled) * 0.7)
    reference = shuffled[:split]
    test_set   = shuffled[split:]

    (DATA_DIR / "reference_cases.json").write_text(
        json.dumps(reference, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (DATA_DIR / "test_cases.json").write_text(
        json.dumps(test_set, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"参考病例库：{len(reference)} 条 → data/reference_cases.json")
    print(f"测试集：    {len(test_set)} 条  → data/test_cases.json")


def prepare_db() -> None:
    """Populate SQLite reference DB from reference_cases.json."""
    sys.path.insert(0, str(ROOT))
    from src.data.db import ReferenceDB
    db_path = DATA_DIR / "medic.db"
    db = ReferenceDB(db_path)
    n = db.populate_from_json(DATA_DIR / "reference_cases.json")
    db.close()
    stats_db = ReferenceDB(db_path)
    s = stats_db.stats()
    stats_db.close()
    print(f"SQLite DB：{n} 条参考病例 → {db_path}")
    print(f"  诊断等级分布：{s['by_level']}")


def main():
    if not RAW_CSV.exists():
        print(f"错误：找不到 {RAW_CSV}")
        sys.exit(1)

    headers, cases = load_csv()
    save_cleaned_csv(headers)
    split_and_save(cases)
    prepare_db()
    print("✅ 数据准备完成")


if __name__ == "__main__":
    main()
