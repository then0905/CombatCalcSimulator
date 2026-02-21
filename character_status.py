from dataclasses import dataclass

@dataclass
class CharacterStatus_Core:
    """
    主要能力值
    """
    MeleeATK: int = 0  # 近戰攻擊力
    RemoteATK: int = 0  # 遠程攻擊力
    MageATK: int = 0  # 魔法攻擊力
    MaxHP: int = 0  # 最大生命值
    HP: int = 0  # 當前生命值
    MaxMP: int = 0  # 最大魔法值
    MP: int = 0  # 當前魔法值
    DEF: int = 0  # 物理防禦力
    Avoid: int = 0  # 迴避率
    MeleeHit: int = 0  # 近戰命中率
    RemoteHit: int = 0  # 遠程命中率
    MageHit: int = 0  # 魔法命中率
    MDEF: int = 0  # 魔法防禦力
    Speed: float = 0.0  # 移動速度
    AS: int = 0  # 攻擊速度 (Attack Speed)
    DamageReduction: int = 0  # 傷害減免
    ElementDamageIncrease: int = 0  # 元素傷害增加
    ElementDamageReduction: int = 0  # 元素傷害減免
    HP_Recovery: int = 0  # 生命值回復
    MP_Recovery: int = 0  # 魔法值回復
    Crt: int = 0  # 暴擊
    CrtResistance: int = 0  # 暴擊抵抗
    CrtDamage: int = 0  # 暴擊附加傷害
    BlockRate: int = 0  # 格檔率
    DisorderResistance: int = 0  # 異常狀態抗性

@dataclass
class CharacterStatus_Secret:
    """
    隱密能力值
    """
    IncreaseDmgRate:float = 0.0 #傷害增加(倍率)
    IncreaseDmgValue:int = 0 #傷害增加(值)
    FinalDamageReductionRate:float = 0   #總傷害減免(傷害公式計算完後乘上)
    RecoveryDmg:float = 0.0 #吸收傷害回血  (小數點)
    Damage:float = 0.0 #總傷害(傷害公式計算完成後乘上)
    IncreaseMeleeRange:float = 0.0 #近距離攻擊範圍增強
    ReduceCCTime:float = 0.0 #控制狀態持續時間倍率（0.75=減少25%）
    
@dataclass
class CharacterStatus_Debuff:
    """
    負面影響能力值
    """
    SpeedSlowRate: float = 0.0  # 移動速度
    
@dataclass
class CharacterStatus_Element:
    """
    屬性方面能力值
    """
    FireDamage: int = 0  # 火屬性傷害
    FireDefense: int = 0  # 火屬性防禦
    WaterDamage: int = 0  # 水屬性傷害
    WaterDefense: int = 0  # 水屬性防禦
    EarthDamage: int = 0  # 地屬性傷害
    EarthDefense: int = 0  # 地屬性防禦
    WindDamage: int = 0  # 風屬性傷害
    WindDefense: int = 0  # 風屬性防禦
    HolyDamage: int = 0  # 神聖屬性傷害
    HolyDefense: int = 0  # 神聖屬性防禦
    DarkDamage: int = 0  # 黑暗屬性傷害
    DarkDefense: int = 0  # 黑暗屬性防禦

@dataclass
class MonsterStatus_Core:
    """
    怪物所屬的屬性能力值
    """
    ATK: int = 0  # 攻擊力
    Hit: int = 0  # 命中
    AtkSpeed: int = 0  # 攻擊速度 (Attack Speed)
    AttackMode: str = ""  # 攻擊模式(近距離、遠距離、魔法)

@dataclass
class MonsterStatus_Debuff:
    """
    怪物所屬的負面影響能力值
    """
    SpeedSlowRate: float = 0.0  # 移動速度