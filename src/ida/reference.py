"""
参考区间配置 — 依据 WS/T 405-2012
来源：https://www.nhc.gov.cn/wjw/s9492/wsbz.shtml
"""

REF_STANDARD = "WS/T 405-2012"

# 血红蛋白参考下限 (g/L)
HB_LOWER = {
    "male": 120,
    "female": 110,  # 非孕女性；孕妇另行判断
    "pregnant": 110,  # WHO 孕妇标准，WS/T 405 未单独列出
}

# 形态学分类阈值
MCV_LOWER = 80    # fL
MCH_LOWER = 27    # pg
MCHC_LOWER = 0.32  # 或 320 g/L，统一换算为 0~1

# IDA 铁缺乏判定阈值
SF_CUTOFF = 14          # 血清铁蛋白 μg/L
SERUM_IRON_UPPER = 8.95  # 血清铁 μmol/L（50 μg/dL）
TIBC_LOWER = 64.44       # 总铁结合力 μmol/L（360 μg/dL）
TS_CUTOFF = 0.15         # 转铁蛋白饱和度 15%
FEP_CUTOFF = 0.9         # 红细胞游离原卟啉 μmol/L（50 μg/dL）
ZPP_UMOL_CUTOFF = 0.96   # 血液锌原卟啉 μmol/L（60 μg/dL）
ZPP_UG_CUTOFF = 3.0      # 血液锌原卟啉 μg/g Hb
STFR_CUTOFF_DEFAULT = 26.5  # sTfR nmol/L（R&D systems；2.25 mg/L）
HB_IRON_THERAPY_RISE = 15   # 铁剂治疗后 Hb 升高阈值 g/L

# 贫血程度分级 (Hb g/L)
SEVERITY_THRESHOLDS = [
    (30, "极重度"),
    (60, "重度"),
    (90, "中度"),
    (None, "轻度"),
]
