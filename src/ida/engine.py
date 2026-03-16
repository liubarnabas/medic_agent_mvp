"""
缺铁性贫血（IDA）诊断规则引擎
计算链路：纯规则，无 LLM，JSON 输入 → JSON 输出
"""

from __future__ import annotations
from typing import Optional
from .models import DiagnosisInput, DiagnosisOutput, DifferentialDiagnosis
from . import reference as REF


def diagnose(data: DiagnosisInput) -> DiagnosisOutput:
    """主诊断入口。"""
    lab = data.lab
    patient = data.patient
    clinical = data.clinical

    evidence: dict[str, str] = {}
    remarks: list[str] = []
    supplementary: list[str] = []
    differentials: list[DifferentialDiagnosis] = []

    # ── 前置条件判断 ──────────────────────────────────────────
    if patient.precondition:
        return DiagnosisOutput(
            conclusion="不适用后续流程",
            level="不适用",
            remarks=[
                "存在血容量变化等前置条件（妊娠、肝硬化、低蛋白血症、"
                "充血性心力衰竭、脱水、大剂量利尿剂、急性大出血等），"
                "建议去医院找专业医生判断"
            ],
        )

    # ── 条款 0：贫血判定 ──────────────────────────────────────
    hb_ref = _hb_lower(patient)
    c0 = lab.Hb < hb_ref
    evidence["0"] = f"Hb={lab.Hb} g/L，参考下限={hb_ref} g/L（{REF.REF_STANDARD}）"

    if not c0:
        return DiagnosisOutput(
            conclusion="不满足贫血诊断",
            level="阴性",
            evidence_detail={"0": evidence["0"]},
            remarks=[
                "当前不满足贫血诊断，提示医生排除以下干扰因素后重新人工评估：",
                "· 高海拔地区长期居住（≥ 6～12 个月）",
                "· 长期慢性呼吸道疾病（慢阻肺、长期吸烟、呼吸睡眠暂停等）",
                "· 影响 Hb 检测结果的其他因素",
            ],
        )

    # 贫血程度分级
    severity = _severity(lab.Hb, hb_ref)

    # ── 条款 1：小细胞低色素 ──────────────────────────────────
    c1 = (
        lab.MCV < REF.MCV_LOWER
        and lab.MCH < REF.MCH_LOWER
        and lab.MCHC < REF.MCHC_LOWER
    )
    evidence["1"] = (
        f"MCV={lab.MCV} fL（参考下限={REF.MCV_LOWER}），"
        f"MCH={lab.MCH} pg（参考下限={REF.MCH_LOWER}），"
        f"MCHC={lab.MCHC}（参考下限={REF.MCHC_LOWER}）"
    )

    # ── 条款 2~9 评分 ─────────────────────────────────────────
    c2, ev2 = _clause2(clinical)
    c3, ev3 = _clause3(lab)
    c4, ev4 = _clause4(lab)
    c5, ev5 = _clause5(lab)
    c6, ev6 = _clause6(lab)
    c7, ev7 = _clause7(lab)
    c8, ev8 = _clause8(lab)
    c9, ev9 = _clause9(lab)

    clauses = [c2, c3, c4, c5, c6, c7, c8, c9]
    evidence_map = {
        "2": ev2, "3": ev3, "4": ev4, "5": ev5,
        "6": ev6, "7": ev7, "8": ev8, "9": ev9,
    }
    positive_count = sum(1 for c in clauses if c is True)

    # ── 主判断逻辑 ────────────────────────────────────────────

    if c1 and positive_count >= 2:
        # 确诊路径
        active_keys = ["0", "1"] + [
            str(i + 2) for i, c in enumerate(clauses) if c is True
        ]
        active_evidence = {k: evidence_map.get(k, evidence.get(k, "")) for k in active_keys}
        active_evidence["0"] = evidence["0"]
        active_evidence["1"] = evidence["1"]

        stage = _ida_stage(lab)
        differentials = _differentials(lab, c1)
        supplementary = _supplementary_tests(lab, patient, clinical)

        output = DiagnosisOutput(
            conclusion="可诊断为缺铁性贫血（IDA）",
            level="确诊",
            severity=severity,
            stage=stage,
            evidence_detail=active_evidence,
            differential_diagnosis=differentials,
            supplementary_tests=supplementary,
            remarks=remarks,
        )
    else:
        # 特别提示路径（条款 7 单独判断）
        if c7 is True:
            active_evidence = {"0": evidence["0"], "7": ev7}
            if c1:
                active_evidence["1"] = evidence["1"]
            differentials = _differentials(lab, c1)
            output = DiagnosisOutput(
                conclusion="高度提示缺铁性贫血，尚不满足确诊标准",
                level="提示",
                severity=severity,
                evidence_detail=active_evidence,
                differential_diagnosis=differentials,
                supplementary_tests=_supplementary_tests(lab, patient, clinical),
                remarks=["SF < 14 μg/L 敏感度/特异度较高，请结合其他检查进一步确认"],
            )
        else:
            # 证据不足，收集所有已检查证据
            all_evidence = {"0": evidence["0"]}
            if c1 is not None:
                all_evidence["1"] = evidence["1"]
            for k, ev in evidence_map.items():
                if ev and "未检查" not in ev and "未开展" not in ev and "未实施" not in ev:
                    all_evidence[k] = ev

            output = DiagnosisOutput(
                conclusion="证据不足，不能诊断缺铁性贫血",
                level="阴性",
                severity=severity,
                evidence_detail=all_evidence,
                supplementary_tests=["建议补充检查铁代谢全套（SF、血清铁、TIBC、TS）"],
                remarks=["建议补充检查 / 随访 / 试验性铁剂治疗后评估"],
            )

    # ── 冲突检测（附加到 remarks）─────────────────────────────
    conflicts = _detect_conflicts(lab, c0, c1)
    output.remarks.extend(conflicts)

    # ── LLM Prompt 构建 ───────────────────────────────────────
    output.llm_prompt = _build_llm_prompt(output)

    return output


# ─── 各条款判定函数 ───────────────────────────────────────────

def _hb_lower(patient) -> float:
    if patient.pregnant:
        return REF.HB_LOWER["pregnant"]
    return REF.HB_LOWER[patient.sex]


def _severity(hb: float, hb_ref: float) -> str:
    # 阈值为下界，从低到高依次判断
    if hb < 30:
        return "极重度"
    if hb < 60:
        return "重度"
    if hb < 90:
        return "中度"
    return "轻度"


def _clause2(clinical) -> tuple[Optional[bool], str]:
    if clinical is None:
        return None, "条款2：临床信息未提供，跳过"

    etiology = clinical.etiology
    symptoms = clinical.symptoms

    has_etiology = (
        etiology is not None
        and any(v is True for v in etiology.model_dump().values())
    )
    has_symptom = (
        symptoms is not None
        and any(v is True for v in symptoms.model_dump().values())
    )

    if etiology is None and symptoms is None:
        return None, "条款2：病因/体征均未录入，跳过"

    c2 = has_etiology and has_symptom
    positive_etiology = (
        [k for k, v in etiology.model_dump().items() if v is True]
        if etiology else []
    )
    positive_symptoms = (
        [k for k, v in symptoms.model_dump().items() if v is True]
        if symptoms else []
    )
    ev = f"条款2：病因={positive_etiology}；体征={positive_symptoms}"
    return c2, ev


def _clause3(lab) -> tuple[Optional[bool], str]:
    if lab.serum_iron is None or lab.TIBC is None:
        return None, "条款3：血清铁/总铁结合力未检查，跳过"
    c3 = lab.serum_iron < REF.SERUM_IRON_UPPER and lab.TIBC > REF.TIBC_LOWER
    ev = f"条款3：血清铁={lab.serum_iron} μmol/L（<{REF.SERUM_IRON_UPPER}），TIBC={lab.TIBC} μmol/L（>{REF.TIBC_LOWER}）"
    return c3, ev


def _clause4(lab) -> tuple[Optional[bool], str]:
    if lab.TS is None:
        return None, "条款4：转铁蛋白饱和度未检查，跳过"
    c4 = lab.TS < REF.TS_CUTOFF
    ev = f"条款4：转铁蛋白饱和度={lab.TS:.2%}（参考阈值<{REF.TS_CUTOFF:.0%}）"
    return c4, ev


def _clause5(lab) -> tuple[Optional[bool], str]:
    if lab.bone_marrow_iron_stain is None:
        return None, "条款5：骨髓铁染色未检查，跳过"
    c5 = lab.bone_marrow_iron_stain == "negative_or_trace"
    ev = f"条款5：骨髓铁染色={'外铁-~±，铁粒幼红细胞<15%（阳性）' if c5 else '未达标准（阴性）'}"
    return c5, ev


def _clause6(lab) -> tuple[Optional[bool], str]:
    fep = lab.FEP
    zpp_u = lab.ZPP_umol
    zpp_g = lab.ZPP_ug_per_gHb

    if fep is None and zpp_u is None and zpp_g is None:
        return None, "条款6：FEP/ZPP 均未检查，跳过"

    c6 = (
        (fep is not None and fep > REF.FEP_CUTOFF)
        or (zpp_u is not None and zpp_u > REF.ZPP_UMOL_CUTOFF)
        or (zpp_g is not None and zpp_g > REF.ZPP_UG_CUTOFF)
    )
    ev = (
        f"条款6：FEP={fep or '—'} μmol/L，"
        f"ZPP={zpp_u or '—'} μmol/L / {zpp_g or '—'} μg/gHb"
    )
    return c6, ev


def _clause7(lab) -> tuple[Optional[bool], str]:
    if lab.SF is None:
        return None, "条款7：血清铁蛋白（SF）未检查，跳过"
    c7 = lab.SF < REF.SF_CUTOFF
    ev = f"条款7：SF={lab.SF} μg/L（参考阈值<{REF.SF_CUTOFF} μg/L）"
    return c7, ev


def _clause8(lab) -> tuple[Optional[bool], str]:
    if not lab.sTfR_available or lab.sTfR is None:
        return None, "条款8：sTfR 本院未开展，跳过"
    cutoff = lab.sTfR_cutoff
    c8 = lab.sTfR > cutoff
    ev = f"条款8：sTfR={lab.sTfR} nmol/L（本院界限值={cutoff} nmol/L）"
    return c8, ev


def _clause9(lab) -> tuple[Optional[bool], str]:
    if lab.Hb_after_iron_therapy is None:
        return None, "条款9：铁剂治疗尚未实施或结果未录入，跳过"
    rise = lab.Hb_after_iron_therapy - lab.Hb
    c9 = rise > REF.HB_IRON_THERAPY_RISE
    ev = (
        f"条款9：治疗后Hb={lab.Hb_after_iron_therapy} g/L，"
        f"较基线升高 {rise:.1f} g/L（阈值>{REF.HB_IRON_THERAPY_RISE} g/L）"
    )
    return c9, ev


# ─── 辅助判断 ─────────────────────────────────────────────────

def _ida_stage(lab) -> Optional[str]:
    """
    IDA 分期：
    - 铁减少期（ID）：SF↓，Hb 正常，MCV 正常
    - 缺铁性红细胞生成期（IDE）：SF↓，TS↓，Hb 正常或轻度↓
    - 缺铁性贫血期（IDA）：SF↓，TS↓，Hb↓，MCV↓
    确诊路径下 Hb↓ 已成立，直接判断 MCV
    """
    if lab.MCV is not None and lab.MCV < REF.MCV_LOWER:
        return "缺铁性贫血期（IDA）"
    if lab.TS is not None and lab.TS < REF.TS_CUTOFF:
        return "缺铁性红细胞生成期（IDE）"
    return "铁减少期（ID）"


def _differentials(lab, c1: Optional[bool]) -> list[DifferentialDiagnosis]:
    result = []

    # 小细胞低色素 + SF 正常/升高 → 地中海贫血
    if c1 and lab.SF is not None and lab.SF >= REF.SF_CUTOFF:
        result.append(DifferentialDiagnosis(
            disease="地中海贫血",
            status="SF 正常/升高，不支持单纯缺铁",
            suggestion="建议血红蛋白电泳进一步排除",
        ))
    elif c1 and lab.SF is None:
        result.append(DifferentialDiagnosis(
            disease="地中海贫血",
            status="SF 未检查，无法排除",
            suggestion="建议检查 SF 及血红蛋白电泳",
        ))

    # 小细胞低色素 + CRP 升高 → 慢性病贫血
    if c1 and lab.CRP is not None and lab.CRP > 10:
        result.append(DifferentialDiagnosis(
            disease="慢性病贫血",
            status=f"CRP={lab.CRP} mg/L 升高，需鉴别",
            suggestion="结合 CRP/ESR 综合判断",
        ))

    # 小细胞低色素 + SF 正常 + CRP 正常 → 铁粒幼细胞贫血
    if (
        c1
        and lab.SF is not None and lab.SF >= REF.SF_CUTOFF
        and (lab.CRP is None or lab.CRP <= 10)
    ):
        result.append(DifferentialDiagnosis(
            disease="铁粒幼细胞贫血",
            status="SF 正常且 CRP 正常，需排除",
            suggestion="建议骨髓铁染色",
        ))

    return result


def _supplementary_tests(lab, patient, clinical) -> list[str]:
    tests = []

    if lab.SF is None:
        tests.append("血清铁蛋白（SF）——铁代谢核心指标，强烈建议检查")
    if lab.serum_iron is None or lab.TIBC is None:
        tests.append("血清铁 + 总铁结合力（TIBC）")
    if lab.TS is None:
        tests.append("转铁蛋白饱和度（TS）")

    # 育龄女性
    if patient.sex == "female" and 14 <= patient.age <= 50:
        tests.append("月经量评估（是否存在月经过多）")

    # 老年男性
    if patient.sex == "male" and patient.age >= 60:
        tests.append("便潜血（排除消化道失血）")
        tests.append("胃肠镜评估（老年男性须排除消化道肿瘤）")

    tests.append("网织红细胞计数（评估骨髓代偿）")

    return tests


def _detect_conflicts(lab, c0: bool, c1: Optional[bool]) -> list[str]:
    conflicts = []

    # 冲突1：Hb 正常但 SF < 15 μg/L（铁减少期）
    if not c0 and lab.SF is not None and lab.SF < 15:
        conflicts.append(
            f"⚠️ 冲突提示：Hb 正常但 SF={lab.SF} μg/L（<15），提示铁减少期（ID），尚未发展为贫血"
        )

    # 冲突2：MCV↓ + SF 正常 + CRP 正常
    if (
        c1
        and lab.SF is not None and lab.SF >= REF.SF_CUTOFF
        and (lab.CRP is None or lab.CRP <= 10)
    ):
        conflicts.append(
            "⚠️ 冲突提示：小细胞低色素但 SF 正常、CRP 正常，建议补查 Hb 电泳或地贫相关基因"
        )

    # 冲突3：SF↓ + MCV 正常/升高（混合性贫血可能）
    if lab.SF is not None and lab.SF < REF.SF_CUTOFF and not c1:
        conflicts.append(
            "⚠️ 冲突提示：SF↓ 但 MCV 正常/升高，可能为混合性贫血（同时缺铁 + B12/叶酸缺乏），建议补查 B12、叶酸"
        )

    return conflicts


def _build_llm_prompt(output: DiagnosisOutput) -> str:
    evidence_lines = "\n".join(
        f"  · 条款{k}：{v}" for k, v in output.evidence_detail.items()
    )
    remarks_text = "；".join(output.remarks) if output.remarks else "无"

    return (
        "你是一名经验丰富的血液科医生助手。请根据以下结构化诊断结论，"
        "用简洁、专业的语言撰写一段诊断依据描述，供主治医生参考。\n"
        "要求：\n"
        "1. 先给出诊断结论（一句话）。\n"
        "2. 逐条列出支持该结论的阳性指标及其数值，并注明参考标准。\n"
        "3. 如有未检查项目或需排除的干扰因素，在末尾单独说明。\n"
        "4. 语言简洁，避免重复，不超过 300 字。\n\n"
        f"诊断结论：{output.conclusion}（{output.level}）\n"
        f"阳性/关键证据：\n{evidence_lines}\n"
        f"备注：{remarks_text}"
    )
