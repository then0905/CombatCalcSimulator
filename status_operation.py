from typing import Dict, List, Optional
from dataclasses import dataclass,fields
from game_models import GameData
from character_status import CharacterStatus_Core, CharacterStatus_Secret, CharacterStatus_Debuff, \
    CharacterStatus_Element, MonsterStatus_Core, MonsterStatus_Debuff


@dataclass
class StatusValues(
CharacterStatus_Element,
CharacterStatus_Debuff,
CharacterStatus_Secret,
CharacterStatus_Core,
MonsterStatus_Core,
MonsterStatus_Debuff
):
    """
    角色屬性值的數據結構
    用於存儲各種屬性的數值，包括攻擊力、防禦力、血量等
    """
    pass


class CharacterStatusCalculator:
    """
    角色屬性計算器主類別
    負責根據角色基礎屬性、裝備、種族等因素計算最終屬性值
    """

    def __init__(self, player_data, weapon_list, armor_list, game_data):
        """
        初始化計算器

        Args:
            player_data: 玩家基礎數據（等級、屬性點等）
            weapon_list: 已裝備的武器列表
            armor_list: 已裝備的防具列表
            game_data: 遊戲配置數據（公式、種族設定等）
        """
        self.player_data = player_data  # 玩家基礎數據
        self.weapon_list = weapon_list  # 武器列表
        self.armor_list = armor_list  # 防具列表
        self.game_data = game_data  # 遊戲配置數據

        # 臨時存儲計算結果的變數
        self.temp_equip_status = StatusValues()  # 裝備提供的屬性加成
        self.temp_basal_status = StatusValues()  # 基礎屬性（等級、種族、屬性點）
        self.temp_effect_status = StatusValues()  # 技能方面影響的效果

    def calculate_all_status(self):
        """
        計算所有屬性值的主方法
        按順序調用各個屬性的計算方法

        Returns:
            dict: 包含裝備加成和基礎屬性的字典
        """
        # 按順序計算各項屬性
        self.melee_atk()  # 近戰攻擊力
        self.remote_atk()  # 遠程攻擊力
        self.mage_atk()  # 魔法攻擊力
        self.max_hp()  # 最大生命值
        self.max_mp()  # 最大魔法值
        self.defense()  # 物理防禦力
        self.avoid()  # 迴避率
        self.melee_hit()  # 近戰命中率
        self.remote_hit()  # 遠程命中率
        self.mage_hit()  # 魔法命中率
        self.mdef()  # 魔法防禦力
        self.speed()  # 移動速度
        self.attack_speed()  # 攻擊速度
        self.damage_reduction()  # 傷害減免
        self.element_damage_increase()  # 元素傷害增加
        self.element_damage_reduction()  # 元素傷害減免
        self.hp_recovery()  # 生命值回復
        self.mp_recovery()  # 魔法值回復
        self.crt()  # 暴擊
        self.crtResistance()  # 暴擊抵抗
        self.crtDamage()  # 暴擊附加傷害
        self.block()  # 格檔率
        self.disorderResistance()  # 異常狀態抗性

        # 返回計算結果
        return {
            "equip": self.temp_equip_status,  # 裝備加成
            "basal": self.temp_basal_status,  # 基礎屬性
            "effect": self.temp_effect_status,  # 效果影響
        }

    def melee_atk(self):
        """
        計算近戰攻擊力
        """
        # 根據玩家種族獲取對應的屬性計算公式
        if not self.player_data:
            print("player_data 是空的或未初始化")
            return  # 或 raise Exception("缺少玩家資料")

        target_status = self.game_data.StatusFormulaDic[
            f"MeleeATK_{self.player_data['race']}"
        ]

        # 計算裝備提供的近戰攻擊力加成
        self.temp_equip_status.MeleeATK = sum(
            weapon.MeleeATK
            + next(
                (
                    forge.MeleeATK
                    for forge in weapon.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for weapon , forgeLv in self.weapon_list
        )

        # 計算基礎近戰攻擊力（根據屬性點和等級）
        self.temp_basal_status.MeleeATK = int(
            round(
                self.player_data["STR"] * target_status.STR
                + self.player_data["level"] * target_status.LvCondition
            )
        )

    def remote_atk(self):
        """
        計算遠程攻擊力
        """

        target_status = self.game_data.StatusFormulaDic[
            f"RemoteATK_{self.player_data["race"]}"
        ]

        self.temp_equip_status.RemoteATK = sum(
            weapon.RemoteATK
            + next(
                (
                    forge.RemoteATK
                    for forge in weapon.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for weapon , forgeLv in self.weapon_list
        )

        self.temp_basal_status.RemoteATK = int(
            round(
                self.player_data["DEX"] * target_status.DEX
                + self.player_data["level"] * target_status.LvCondition
            )
        )

    def mage_atk(self):
        """
        計算魔法攻擊力
        主要基於智力(INT)屬性
        """

        target_status = self.game_data.StatusFormulaDic[
            f"MageATK_{self.player_data["race"]}"
        ]

        self.temp_equip_status.MageATK = sum(
            weapon.MageATK
            + next(
                (
                    forge.MageATK
                    for forge in weapon.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for weapon , forgeLv in self.weapon_list
        )

        self.temp_basal_status.MageATK = int(
            round(
                self.player_data["INT"] * target_status.INT
                + self.player_data["level"] * target_status.LvCondition
            )
        )

    def max_hp(self):
        """
        計算最大生命值
        """

        target_status = self.game_data.StatusFormulaDic[
            f"HP_{self.player_data["race"]}"
        ]

        weapon_hp = sum(
            weapon.HP
            + next(
                (
                    forge.HP
                    for forge in weapon.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for weapon , forgeLv in self.weapon_list
        )

        armor_hp = sum(
            armor.HP + next(
                (
                forge.HP
                for forge in armor.ForgeConfigList
                if forge.ForgeLv == forge_lv
                ),
                0
            )
            for armor, forge_lv in self.armor_list
        )

        self.temp_equip_status.MaxHP = weapon_hp + armor_hp

        # 基礎生命值計算
        self.temp_basal_status.MaxHP = (
            int(
                round(
                    self.player_data["VIT"] * target_status.VIT
                    + self.player_data["STR"] * target_status.STR
                    + self.player_data["level"] * target_status.LvCondition
                )
            )
            + self.player_data["MaxHP"]
        )  # 加上角色初始生命值
        
        #最大HP計算完成後 設定初始HP
        self.temp_basal_status.HP = self.temp_basal_status.MaxHP
        self.temp_equip_status.HP = self.temp_equip_status.MaxHP
        
    def max_mp(self):
        """
        計算最大魔法值
        """
        target_status = self.game_data.StatusFormulaDic[
            f"MP_{self.player_data["race"]}"
        ]

        weapon_mp = sum(
            weapon.MP
            + next(
                (
                    forge.MP
                    for forge in weapon.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for weapon , forgeLv in self.weapon_list
        )

        armor_mp = sum(
            armor.MP
            + next(
                (
                    forge.MP
                    for forge in armor.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for armor , forgeLv in self.armor_list
        )

        self.temp_equip_status.MaxMP = weapon_mp + armor_mp

        self.temp_basal_status.MaxMP = (
            int(
                round(
                    self.player_data["INT"] * target_status.INT
                    + self.player_data["level"] * target_status.LvCondition
                )
            )
            + self.player_data["MaxMP"]
        )
        #最大MP計算完成後 設定初始MP
        self.temp_basal_status.MP = self.temp_basal_status.MaxMP
        self.temp_equip_status.MP = self.temp_equip_status.MaxMP

    def defense(self):
        """
        計算物理防禦力
        """
        target_status = self.game_data.StatusFormulaDic[
            f"DEF_{self.player_data["race"]}"
        ]

        weapon_def = sum(
            weapon.DEF
            + next(
                (
                    forge.DEF
                    for forge in weapon.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for weapon , forgeLv in self.weapon_list
        )

        armor_def = sum(
            armor.DEF
            + next(
                (
                    forge.DEF
                    for forge in armor.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for armor , forgeLv in self.armor_list
        )

        self.temp_equip_status.DEF = weapon_def + armor_def

        self.temp_basal_status.DEF = int(
            round(
                self.player_data["VIT"] * target_status.VIT
                + self.player_data["level"] * target_status.LvCondition
            )
        )

    def avoid(self):
        """
        計算迴避值
        """
        target_status = self.game_data.StatusFormulaDic[
            f"Avoid_{self.player_data["race"]}"
        ]

        # 裝備迴避率加成
        weapon_avoid = sum(
            weapon.Avoid
            + next(
                (
                    forge.Avoid
                    for forge in weapon.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for weapon , forgeLv in self.weapon_list
        )

        armor_avoid = sum(
            armor.Avoid
            + next(
                (
                    forge.Avoid
                    for forge in armor.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for armor , forgeLv in self.armor_list
        )

        self.temp_equip_status.Avoid = weapon_avoid + armor_avoid

        # 基礎迴避率（主要基於敏捷）
        self.temp_basal_status.Avoid = int(
            round(
                self.player_data["DEX"] * target_status.DEX
                + self.player_data["AGI"] * target_status.AGI
            )
        )

    def melee_hit(self):
        """
        計算近戰命中值
        """

        target_status = self.game_data.StatusFormulaDic[
            f"MeleeHit_{self.player_data["race"]}"
        ]

        self.temp_equip_status.MeleeHit = sum(
            weapon.MeleeHit
            + next(
                (
                    forge.MeleeHit
                    for forge in weapon.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for weapon , forgeLv in self.weapon_list
        )

        self.temp_basal_status.MeleeHit = int(
            round(
                self.player_data["STR"] * target_status.STR
                + self.player_data["AGI"] * target_status.AGI
                + self.player_data["level"] * target_status.LvCondition
            )
        )

    def remote_hit(self):
        """
        計算遠程命中值
        """

        target_status = self.game_data.StatusFormulaDic[
            f"RemoteHit_{self.player_data["race"]}"
        ]

        self.temp_equip_status.RemoteHit = sum(
            weapon.RemoteHit
            + next(
                (
                    forge.RemoteHit
                    for forge in weapon.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for weapon , forgeLv in self.weapon_list
        )

        self.temp_basal_status.RemoteHit = int(
            round(
                self.player_data["DEX"] * target_status.DEX
                + self.player_data["AGI"] * target_status.AGI
                + self.player_data["level"] * target_status.LvCondition
            )
        )

    def mage_hit(self):
        """
        計算魔法命中值
        """

        target_status = self.game_data.StatusFormulaDic[
            f"MageHit_{self.player_data["race"]}"
        ]

        self.temp_equip_status.MageHit = sum(
            weapon.MageHit
            + next(
                (
                    forge.MageHit
                    for forge in weapon.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for weapon , forgeLv in self.weapon_list
        )

        self.temp_basal_status.MageHit = int(
            round(
                self.player_data["INT"] * target_status.INT
                + self.player_data["AGI"] * target_status.AGI
                + self.player_data["level"] * target_status.LvCondition
            )
        )

    def mdef(self):
        """
        計算魔法防禦力
        """

        target_status = self.game_data.StatusFormulaDic[
            f"MDEF_{self.player_data["race"]}"
        ]

        weapon_mdef = sum(
            weapon.MDEF
            + next(
                (
                    forge.MDEF
                    for forge in weapon.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for weapon , forgeLv in self.weapon_list
        )

        armor_mdef = sum(
            armor.MDEF
            + next(
                (
                    forge.MDEF
                    for forge in armor.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for armor , forgeLv in self.armor_list
        )

        self.temp_equip_status.MDEF = weapon_mdef + armor_mdef

        self.temp_basal_status.MDEF = int(
            round(
                self.player_data["VIT"] * target_status.VIT
                + self.player_data["WIS"] * target_status.WIS
            )
        )

    def speed(self):
        """計算移動速度"""

        self.temp_equip_status.Speed = sum(
            armor.Speed
            + next(
                (
                    forge.Speed
                    for forge in armor.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for armor , forgeLv in self.armor_list
        )

        self.temp_basal_status.Speed = 1

    def attack_speed(self):
        """計算攻擊速度"""
        self.temp_equip_status.AS = next(
            (
                GameData.Instance.GameSettingDic[weapon.ASID].GameSettingValue
                for weapon , forgeLv in self.weapon_list
            ),
            0,
        )

        self.temp_basal_status.AS = 1

    def damage_reduction(self):
        """計算傷害減免"""
        target_status = self.game_data.StatusFormulaDic[
            f"DamageReduction_{self.player_data["race"]}"
        ]

        # 裝備防禦力加成
        armorDamageReduction = sum(
            armor.DamageReduction
            + next(
                (
                    forge.DamageReduction
                    for forge in armor.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for armor , forgeLv in self.armor_list
        )

        self.temp_equip_status.DamageReduction = armorDamageReduction

        # 基礎傷害減晚（基於VIT）
        self.temp_basal_status.DamageReduction = int(
            round(self.player_data["VIT"] * target_status.VIT)
        )

    def element_damage_increase(self):
        """計算屬性傷害增幅加成 - 主要來自裝備和技能"""
        target_status = self.game_data.StatusFormulaDic[
            f"ElementDamageIncrease_{self.player_data["race"]}"
        ]

        # 武器加成
        weaponElementDamageIncrease = sum(
            weapon.ElementDamageIncrease
            + next(
                (
                    forge.ElementDamageIncrease
                    for forge in weapon.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for weapon , forgeLv in self.weapon_list
        )

        self.temp_equip_status.ElementDamageIncrease = weaponElementDamageIncrease

        # 基礎屬性傷害增幅
        self.temp_basal_status.ElementDamageIncrease = int(
            round(self.player_data["INT"] * target_status.INT)
        )

    def element_damage_reduction(self):
        """計算屬性傷害減免"""
        target_status = self.game_data.StatusFormulaDic[
            f"ElementDamageReduction_{self.player_data["race"]}"
        ]

        # 裝備屬性傷害減免加成
        armorElementDamageReduction = sum(
            armor.ElementDamageReduction
            + next(
                (
                    forge.ElementDamageReduction
                    for forge in armor.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for armor , forgeLv in self.armor_list
        )

        self.temp_equip_status.ElementDamageReduction = armorElementDamageReduction

        # 基礎屬性傷害減免
        self.temp_basal_status.ElementDamageReduction = int(
            round(self.player_data["WIS"] * target_status.WIS)
        )

    def hp_recovery(self):
        """計算生命值回復 - 來自裝備和技能"""
        target_status = self.game_data.StatusFormulaDic[
            f"HP_Recovery_{self.player_data["race"]}"
        ]

        # 裝備屬性傷害減免加成
        armorHP_Recovery = sum(
            armor.HpRecovery
            + next(
                (
                    forge.HpRecovery
                    for forge in armor.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for armor , forgeLv in self.armor_list
        )

        self.temp_equip_status.HP_Recovery = armorHP_Recovery

        # 基礎屬性傷害減免
        self.temp_basal_status.HP_Recovery = int(
            round(self.player_data["VIT"] * target_status.VIT)
        )

    def mp_recovery(self):
        """計算魔法值回復 - 來自裝備和技能"""
        target_status = self.game_data.StatusFormulaDic[
            f"MP_Recovery_{self.player_data["race"]}"
        ]

        # 裝備屬性傷害減免加成
        armorMP_Recovery = sum(
            armor.MpRecovery
            + next(
                (
                    forge.MpRecovery
                    for forge in armor.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for armor , forgeLv in self.armor_list
        )

        self.temp_equip_status.MP_Recovery = armorMP_Recovery

        # 基礎屬性傷害減免
        self.temp_basal_status.MP_Recovery = int(
            round(self.player_data["WIS"] * target_status.WIS)
        )

    def crt(self):
        """
        暴擊計算
        """

        weapon_crt = sum(
            weapon.Crt
            + next(
                (
                    forge.Crt
                    for forge in weapon.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for weapon , forgeLv in self.weapon_list
        )

        self.temp_equip_status.Crt = weapon_crt

    def crtResistance(self):
        """
        暴擊抵抗計算
        """

        armor_crtResistance = sum(
            armor.CrtResistance
            + next(
                (
                    forge.CrtResistance
                    for forge in armor.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for armor , forgeLv in self.armor_list
        )

        self.temp_equip_status.CrtResistance = armor_crtResistance
        
    def crtDamage(self):
        """
        暴擊附加傷害計算
        """

        weapon_crtDamage = sum(
            weapon.CrtDamage
            + next(
                (
                    forge.CrtDamage
                    for forge in weapon.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for weapon , forgeLv in self.weapon_list
        )

        self.temp_equip_status.CrtDamage = weapon_crtDamage
        
    def block(self):
        """
        格檔計算
        """

        weapon_blockRate = sum(
            weapon.BlockRate
            + next(
                (
                    forge.BlockRate
                    for forge in weapon.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for weapon, forgeLv in self.weapon_list
        )

        armor_blockRate = sum(
            armor.BlockRate
            + next(
                (
                    forge.BlockRate
                    for forge in armor.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for armor , forgeLv in self.armor_list
        )

        self.temp_equip_status.BlockRate = armor_blockRate + weapon_blockRate
        
    def disorderResistance(self):
        """
        異常狀態計算
        """

        armor_disorderResistance = sum(
            armor.DisorderResistance
            + next(
                (
                    forge.DisorderResistance
                    for forge in armor.ForgeConfigList
                    if forge.ForgeLv == forgeLv
                ),
                0,
            )
            for armor , forgeLv in self.armor_list
        )

        self.temp_equip_status.DisorderResistance = armor_disorderResistance

    def create_character(self, name: str,race: str, jobBonusData, level: int) -> Dict:
        """
        創建新角色並計算初始屬性

        Args: 
            name: 角色名稱
            race: 角色種族
            char_class: 職業配置資料
            level: 角色等級

        Returns:
            dict: 完整的角色資料
        """
        # 創建臨時玩家數據用於屬性計算
        temp_player_data = self._create_player_data(race,jobBonusData, level)

        # 更新當前實例的玩家數據
        self.player_data = temp_player_data

        # 使用當前實例的裝備進行計算
        stats = self.calculate_all_status()

        # 設定總能力值
        result = {}
        basal = stats["basal"];
        equip = stats["equip"];
        for f in fields(StatusValues):
            tempName = f.name
            value = getattr(basal, tempName) + getattr(equip, tempName)
            result[tempName] = value


        # 返回完整角色數據
        return {
            "name": name,  # 角色名稱
            "char_class": jobBonusData,  # 職業資料
            "level": level,  # 等級
            "stats": result,
            "basal":stats["basal"],
            "equip":stats["equip"],
            "effect":stats["effect"],
            "equipped_weapon": None,  # 裝備的武器（初始為空）
            "equipped_armor": None,  # 裝備的防具（初始為空）
            "skills": self._get_skills_for_class(jobBonusData),  # 職業技能
            "items": [],  # 物品欄（初始為空）
        }

    def _create_player_data(self, race, jobBonusData, level: int) -> Dict:
        """
        根據職業和等級創建玩家基礎數據

        Args:
            race: 角色種族
            jobBonusData: 職業配置
            level: 角色等級

        Returns:
            dict: 玩家基礎數據
        """
        return {
            "race": race ,
            "STR": jobBonusData.STR, 
            "DEX": jobBonusData.DEX, 
            "INT": jobBonusData.INT, 
            "VIT": jobBonusData.VIT, 
            "WIS": jobBonusData.WIS,
            "AGI": jobBonusData.AGI, 
            "level": level,  # 角色等級
            "MaxHP": jobBonusData.HP,  # 職業基礎生命值
            "MaxMP": jobBonusData.MP,  # 職業基礎魔法值
        }

    def _get_skills_for_class(self, char_class: Dict) -> List[Dict]:
        """
        獲取職業可用的技能列表

        Args:
            char_class: 職業配置

        Returns:
            list: 可用技能列表
        """
        #

        return [
            skill
            for skill in self.game_data.SkillDataDic.values()
            if skill.Job in char_class.Job
        ]