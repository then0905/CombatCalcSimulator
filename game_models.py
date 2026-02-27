import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


# 基本屬性資料結構
@dataclass
class BasalAttributesDataModel:
    HP: int = 0
    MP: int = 0
    HpRecovery: int = 0
    MpRecovery: int = 0
    MeleeATK: int = 0
    MeleeHit: int = 0
    RemoteATK: int = 0
    RemoteHit: int = 0
    MageATK: int = 0
    MageHit: int = 0
    Avoid: int = 0
    DEF: int = 0
    MDEF: int = 0
    DamageReduction: int = 0
    Speed: float = 0
    Crt: float = 0
    CrtDamage: int = 0
    CrtResistance: float = 0
    BlockRate: float = 0
    DisorderResistance: float = 0
    ElementDamageReduction: float = 0
    ElementDamageIncrease: float = 0
    STR: int = 0
    DEX: int = 0
    INT: int = 0
    AGI: int = 0
    VIT: int = 0
    WIS: int = 0

# 技能實際運作所需資料
@dataclass
class SkillOperationData:
    SkillID: str = ""
    SkillComponentID: str = ""
    DependCondition: str = ""
    EffectValue: float = 0.0
    InfluenceStatus: str = ""
    AddType: str = ""
    ConditionOR: List[str] = field(default_factory=list)
    ConditionAND: List[str] = field(default_factory=list)
    EffectDurationTime: float = 0.0
    EffectRecive: int = 0
    TargetCount: int = 0
    Bonus: List[str] = None
# 技能資料結構
@dataclass
class SkillData:
    Job: str = ""
    Name: str = ""
    SkillID: str = ""
    NeedLv: int = 0
    Characteristic: bool = False
    CastMage: int = 0
    CD: float = 0.0
    ChantTime: float = 0.0
    AnimaTrigger: int = 0
    Type: str = ""
    EffectTarget: str = ""
    Distance: float = 0.0
    Width: float = 0.0
    Height: float = 0.0
    CircleDistance: float = 0.0
    Damage: float = 0.0
    AdditionMode: str = ""
    Intro: str = ""
    SkillOperationDataList: List[SkillOperationData] = field(default_factory=list)
    
# 怪物生成資料
@dataclass
class MonsterSpawnDataModel:
    MonsterCodeID: str = ""
    SpawnPosX: float = 0
    SpawnPosY: float = 0
    SpawnPosZ: float = 0
# 怪物技能資料
@dataclass
class MonsterSkillDataModel:
    MonsterCodeID: str = ""
    SkillEffect: str = ""
    SkilTypeID: str = ""
    Countdown: int = 0
    SkillVolume: float = 0
    SklillCD: float = 0
    CostMana: int = 0
    AddType: str = ""
    EffectTarget: str = ""
    AdditionalEffect: str = ""
    AdditionalEffectValue: int = 0
    AdditionalEffectTime: float = 0
    InfluenceStatus: str = ""
    EffectRecive: int = 0
    Distance: float = 0
    Width: float = 0
    Height: float = 0
    CircleDistance: float = 0
    Condition: str = ""
# 怪物資料
@dataclass
class MonsterDataModel(BasalAttributesDataModel):
    MonsterCodeID: str = ""
    Name: str = ""
    AreaID: str = ""
    Area: str = ""
    Lv: int = 0
    Class: str = ""
    ClassID: str = ""
    Type: str = ""
    TypeID: str = ""
    SpawnAmount: int = 0
    SpawnPos: str = ""
    RebirthCD: int = 0
    EXP: int = 0
    ExpSplit: bool = False
    DropItemLockSetting: int = 0
    AttackMode: str = ""
    Habit: bool = False
    ActivityScope: float = 0
    DetectionScope: float = 0
    UseSkill: bool = False
    ATK: int = 0
    Hit: int = 0
    AtkSpeed: float = 0.0
    AttackRange: int = 0
    PursueRange: int = 0
    WalkSpeed: int = 0
    RunSpeed: int = 0
    MonsterSpawnPosList: List[MonsterSpawnDataModel ] = field(default_factory=list)
    MonsterSkillList: List[MonsterSkillDataModel] = field(default_factory=list)

    # 掉落物詳情資料

# 掉落物詳細資料(機率 物品ID 掉落數量等等)
@dataclass
class DropItemData:
    CodeID: str = ""
    DropItemID: str = ""
    Probability: float = 0
    DropCountMax: int = 0
    DropCountMin: int = 0
# 怪物掉落物資料
@dataclass
class MonsterDropItemDataModel:
    AreaID: str = ""
    MonsterCodeID: str = ""
    MinCoin: int = 0
    MaxCoin: int = 0
    DropItemList: List[DropItemData] = field(default_factory=list)


# 裝備強化屬性資料
@dataclass
class ForgeData(BasalAttributesDataModel):
    CodeID: str = ""
    ForgeLv: int = 0
    SuccessProbability: float = 0
    SuperiorSuccessProbability: float = 0
    DestroyedProbability: float = 0
    Redeem: int = 0
# 道具使用後的效果資料
@dataclass
class ItemEffectData:
    CodeID: str = ""
    ItemComponentID: str = ""
    EffectValue: float = 0
    InfluenceStatus: str = ""
    AddType: str = ""
    ConditionOR: List[str] = field(default_factory=list)
    ConditionAND: List[str] = field(default_factory=list)
    EffectDurationTime: float = 0
    EffectRecive: int = 0
    TargetCount: int = 0
    Bonus: Any = None
# 防具資料結構
@dataclass
class ArmorDataModel(BasalAttributesDataModel):
    NeedLv: int = 0
    Name: str = ""
    CodeID: str = ""
    Path: str = ""
    FileName: str = ""
    Classification: str = ""
    ClassificationID: str = ""
    WearPart: str = ""
    WearPartID: str = ""
    Type: str = ""
    TypeID: str = ""
    Intro: str = ""
    Stackability: bool = False
    Redeem: int = 0
    Price: int = 0
    ForgeConfigList: List[ForgeData] = field(default_factory=list)
# 武器資料結構
@dataclass
class WeaponDataModel(BasalAttributesDataModel):
    Lv: int = 0
    Name: str = ""
    CodeID: str = ""
    Path: str = ""
    FileName: str = ""
    Classification: str = ""
    ClassificationID: str = ""
    TakeHand: str = ""
    TakeHandID: str = ""
    Type: str = ""
    TypeID: str = ""
    Intro: str = ""
    Stackability: bool = False
    AS: str = ""
    ASID: str = ""
    Redeem: int = 0
    Price: int = 0
    ForgeConfigList: List[ForgeData] = field(default_factory=list)

# 道具資料結構
@dataclass
class ItemDataModel(BasalAttributesDataModel):
    Lv: int = 0
    Name: str = ""
    CodeID: str = ""
    Path: str = ""
    FileName: str = ""
    Classification: str = ""
    ClassificationID: str = ""
    TakeHand: str = ""
    TakeHandID: str = ""
    Type: str = ""
    TypeID: str = ""
    Intro: str = ""
    Stackability: bool = False
    ItemEffectDataList: List[ItemEffectData] = field(default_factory=list)
    CD: float = 0
    Price: int = 0
    Redeem: int = 0

# 職業能力值加成
@dataclass
class JobBonusDataModel:
    Job: int = 0
    STR: int = 0
    DEX: int = 0
    INT: int = 0
    AGI: int = 0
    WIS: int = 0
    VIT: int = 0
    HP: float = 0.0
    MP: float = 0.0
# 種族能力值加成
@dataclass
class StatusFormulaDataModel:
    TargetStatus: str = ""
    Race: str = ""
    STR: float = 0
    DEX: float = 0
    INT: float = 0
    AGI: float = 0
    WIS: float = 0
    VIT: float = 0
    LvCondition: float = 0

# 地區資料
@dataclass
class AreaData:
    AreaID: str = ""
    AreaName: str =""
    MiniMapPath: str = ""
    UseRecord: bool = 0
    RecordMapTarget: str = ""
    RecordPosX: float = 0
    RecordPosY: float = 0
    RecordPosZ: float = 0

# 文字資料
@dataclass
class GameText:
    TextID: str = ""
    TextContent: str = ""
    
# 遊戲設定資料
@dataclass
class GameSettingDataModel:
    GameSettingID: str = ""
    GameSettingValue: float = 0

# 等級與經驗值的數值
@dataclass
class LvAndExpDataModel:
    Lv: int = 0
    EXP: int = 0

# 遊戲資料字典宣告區
SkillDataDic: Dict[str, SkillData] = {}
MonstersDataDic: Dict[str, MonsterDataModel] = {}
MonsterDropItemDic: Dict[str, MonsterDropItemDataModel] = {}
ArmorsDic: Dict[str, ArmorDataModel] = {}
WeaponsDic: Dict[str, WeaponDataModel] = {}
ItemsDic: Dict[str, ItemDataModel] = {}
JobBonusDic: Dict[str, JobBonusDataModel] = {}
StatusFormulaDic: Dict[str, StatusFormulaDataModel] = {}
GameTextDataDic: Dict[str, GameText] = {}
GameSettingDic: Dict[str, GameSettingDataModel] = {}   #這開始
AreaDataDic: Dict[str, AreaData] = {}
ExpAndLvDic: Dict[int, LvAndExpDataModel] = {}    

class GameData:
    Instance = None
    
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.load_data()
        GameData.Instance = self

    def load_data(self):
        # 加載所有JSON數據

        from commonfunction import get_data_path
        # 加載技能資料
        with open(get_data_path("data","SkillData.json"), encoding="utf-8") as f:
            skills_data = json.load(f)

            # 處理 SkillOperationDataList
            for skill in skills_data:
                if "SkillOperationDataList" in skill:
                    skill["SkillOperationDataList"] = [
                        SkillOperationData(**op)
                        for op in skill["SkillOperationDataList"]
                    ]

            # 轉換為 SkillData 物件
            self.SkillDataDic = {s["SkillID"]: SkillData(**s) for s in skills_data}

        # 加載怪物資料
        with open(get_data_path("data","Monster.json"), encoding="utf-8") as f:
            monsters_data = json.load(f)

            # 處理 MonsterSkillList
            for monserData in monsters_data:
                if "MonsterSkillList" in monserData:
                    monserData["MonsterSkillList"] = [
                        MonsterSkillDataModel(**op)
                        for op in monserData["MonsterSkillList"]
                    ]  
             # 處理 MonsterSpawnPosList
            for monserData in monsters_data:
                if "MonsterSpawnPosList" in monserData:
                    monserData["MonsterSpawnPosList"] = [
                        MonsterSpawnDataModel(**op)
                        for op in monserData["MonsterSpawnPosList"]
                    ]

            # 轉換為 MonstersDataDic 物件
            self.MonstersDataDic = {s["MonsterCodeID"]: MonsterDataModel(**s) for s in monsters_data}
            
        # 加載掉落物資料
        with open(get_data_path("data","DropItem.json"), encoding="utf-8") as f:
            dropItems_data = json.load(f)
            
            # 處理 DropItemList
            for dropItemData in dropItems_data:
                if "DropItemList" in dropItemData:
                    dropItemData["DropItemList"] = [
                        DropItemData(**op)
                        for op in dropItemData["DropItemList"]
                    ]

            # 轉換為 MonsterDropItemDic 物件
            self.MonsterDropItemDic = {s["MonsterCodeID"]: MonsterDropItemDataModel(**s) for s in dropItems_data}

        # 加載防具資料
        with open(get_data_path("data","Armor.json"), encoding="utf-8") as f:
            armors_data = json.load(f)
            
            # 處理 ForgeConfigList
            for armorData in armors_data:
                if "ForgeConfigList" in armorData:
                    armorData["ForgeConfigList"] = [
                        ForgeData(**op)
                        for op in armorData["ForgeConfigList"]
                    ]            
                    
            self.ArmorsDic = {a["CodeID"]: ArmorDataModel(**a) for a in armors_data}
            
        # 加載武器資料
        with open(get_data_path("data","Weapon.json"), encoding="utf-8") as f:
            weapons_data = json.load(f)
            
            # 處理 ForgeConfigList
            for weaponData in weapons_data:
                if "ForgeConfigList" in weaponData:
                    weaponData["ForgeConfigList"] = [
                        ForgeData(**op)
                        for op in weaponData["ForgeConfigList"]
                    ]            
                    
            self.WeaponsDic = {a["CodeID"]: WeaponDataModel(**a) for a in weapons_data}
            
        # 加載道具資料
        with open(get_data_path("data","Item.json"), encoding="utf-8") as f:
            items_data = json.load(f)
            
            # 處理 ItemEffectDataList
            for itemData in items_data:
                if "ItemEffectDataList" in itemData:
                    itemData["ItemEffectDataList"] = [
                        ItemEffectData(**op)
                        for op in itemData["ItemEffectDataList"]
                    ]            
                    
            self.ItemsDic = {a["CodeID"]: ItemDataModel(**a) for a in items_data}
            
        # 加載職業加成資料
        with open(get_data_path("data","JobBonus.json"), encoding="utf-8") as f:
            classes_data = json.load(f)
            self.JobBonusDic = {c["Job"]: JobBonusDataModel(**c) for c in classes_data}
            
        # 加載種族能力值資料
        with open(get_data_path("data","StatusFormula.json"), encoding="utf-8") as f:
            statusFormulas_data = json.load(f)
            self.StatusFormulaDic = {f"{c['TargetStatus']}_{c['Race']}": StatusFormulaDataModel(**c) for c in statusFormulas_data}            
            
        # 加載文字資料
        # 要讀取的檔案列表 (假設這些檔案結構都相同)
        TextJsonFile = [
                "GameText.json",
                "StatusText.json",
                "CommonText.json",
                "EffectText.json",
                "QuestText.json",
                "TutorialText.json",
                "JobText.json",
                "MonsterText.json",
                "AreaText.json",
                "NpcText.json",
                "ItemText.json",
                "WeaponText.json",
                "ArmorText.json",
                "SkillText.json",
        ]
        self.GameTextDataDic = {}
        for file in TextJsonFile:
                try:
                    with open(get_data_path("data",file) ,encoding="utf-8") as f:
                        data = json.load(f)
                        self.GameTextDataDic.update({
                            item["TextID"]: GameText(**item)
                            for item in data
                        })
                except FileNotFoundError:
                    print(f"找不到檔案: {file}")
                except Exception as e:
                    print(f"讀取 {file} 時發生錯誤: {e}")          
                    
        # 加載遊戲設定資料
        with open(get_data_path("data","GameSetting.json"), encoding="utf-8") as f:
            gameSetting_data = json.load(f)
            self.GameSettingDic = {
                c["GameSettingID"]: GameSettingDataModel(
                    GameSettingID=c["GameSettingID"],
                    GameSettingValue=float(c["GameSettingValue"])
                ) for c in gameSetting_data
            }
            
        # 加載地區資料
        with open(get_data_path("data","Area.json"), encoding="utf-8") as f:
            areas_data = json.load(f)
            self.AreaDataDic = {c["AreaID"]: AreaData(**c) for c in areas_data}   
            
        # 加載地區資料
        with open(get_data_path("data","LvAndExp.json"), encoding="utf-8") as f:
            lvAndExp_data = json.load(f)
            self.ExpAndLvDic = {c["Lv"]: LvAndExpDataModel(**c) for c in lvAndExp_data}   