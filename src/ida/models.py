"""
输入/输出数据模型
"""

from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


# ─── 输入模型 ────────────────────────────────────────────────

class EtiologyInput(BaseModel):
    """缺铁病因（条款 2）"""
    absorption_disorder: Optional[bool] = None      # 吸收不良
    vegetarian_picky_eating: Optional[bool] = None  # 素食/偏食
    adolescent_growth: Optional[bool] = None        # 生长发育期
    pregnancy: Optional[bool] = None               # 妊娠期
    multiparity: Optional[bool] = None             # 多次妊娠（≥3胎）
    chronic_bleeding: Optional[bool] = None        # 慢性出血
    other_evidenced: Optional[bool] = None         # 其他循证病因


class SymptomsInput(BaseModel):
    """临床体征（条款 2）"""
    melena: Optional[bool] = None                      # 黑便
    menorrhagia: Optional[bool] = None                 # 经血过多
    chronic_diarrhea_constipation: Optional[bool] = None  # 慢性腹泻/便秘
    fatigue: Optional[bool] = None                     # 疲劳/乏力
    pallor: Optional[bool] = None                      # 皮肤黏膜苍白
    tachycardia_etc: Optional[bool] = None             # 心动过速/心悸等
    dyspnea_on_exertion: Optional[bool] = None         # 呼吸加深
    koilonychia: Optional[bool] = None                 # 反甲/勺状指
    dry_skin: Optional[bool] = None                    # 皮肤干燥
    angular_cheilitis: Optional[bool] = None           # 口角炎/舌炎
    brittle_hair: Optional[bool] = None                # 头发干枯易断
    pica: Optional[bool] = None                        # 偏食/异食癖


class PatientInput(BaseModel):
    sex: Literal["male", "female"]
    age: int = Field(ge=0, le=150)
    pregnant: bool = False
    precondition: bool = False  # 存在血容量变化等前置条件


class LabInput(BaseModel):
    # 血常规（必须）
    Hb: float = Field(description="血红蛋白 g/L")
    MCV: float = Field(description="平均红细胞体积 fL")
    MCH: float = Field(description="平均红细胞血红蛋白含量 pg")
    MCHC: float = Field(description="平均红细胞血红蛋白浓度 0~1")

    # 铁代谢（建议）
    SF: Optional[float] = None           # 血清铁蛋白 μg/L
    serum_iron: Optional[float] = None   # 血清铁 μmol/L
    TIBC: Optional[float] = None         # 总铁结合力 μmol/L
    TS: Optional[float] = None           # 转铁蛋白饱和度 0~1

    # 炎症（建议）
    CRP: Optional[float] = None          # mg/L
    ESR: Optional[float] = None          # mm/h

    # 扩展指标（可选）
    RDW: Optional[float] = None                  # %
    FEP: Optional[float] = None                  # μmol/L
    ZPP_umol: Optional[float] = None             # μmol/L
    ZPP_ug_per_gHb: Optional[float] = None       # μg/g Hb
    sTfR: Optional[float] = None                 # nmol/L
    sTfR_available: bool = False                  # 本院是否开展
    sTfR_cutoff: float = 26.5                     # 本院界限值 nmol/L
    bone_marrow_iron_stain: Optional[Literal["negative_or_trace", "positive"]] = None
    Hb_after_iron_therapy: Optional[float] = None  # 铁剂治疗后 Hb g/L


class ClinicalInput(BaseModel):
    etiology: Optional[EtiologyInput] = None
    symptoms: Optional[SymptomsInput] = None


class DiagnosisInput(BaseModel):
    patient: PatientInput
    lab: LabInput
    clinical: Optional[ClinicalInput] = None


# ─── 输出模型 ────────────────────────────────────────────────

DiagnosisLevel = Literal["确诊", "提示", "阴性", "不适用"]
SeverityLevel = Literal["轻度", "中度", "重度", "极重度"]
IDAStage = Literal["铁减少期（ID）", "缺铁性红细胞生成期（IDE）", "缺铁性贫血期（IDA）"]


class DifferentialDiagnosis(BaseModel):
    disease: str
    status: str
    suggestion: Optional[str] = None


class DiagnosisOutput(BaseModel):
    conclusion: str                           # 诊断结论文字
    level: DiagnosisLevel                     # 诊断等级
    severity: Optional[SeverityLevel] = None  # 贫血程度（有贫血时）
    stage: Optional[IDAStage] = None          # IDA 分期（确诊时）
    evidence_detail: dict[str, str] = {}      # 条款编号 → 证据描述
    differential_diagnosis: list[DifferentialDiagnosis] = []
    supplementary_tests: list[str] = []
    side_findings: list[str] = []
    remarks: list[str] = []
    llm_prompt: str = ""                      # 供调用方传给 LLM 的 prompt
    reference_guidelines: list[str] = ["WS/T 405-2012", "中华医学会血液学分会《IDA诊治指南》"]
