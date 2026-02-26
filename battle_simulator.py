import random
import heapq
from typing import Dict, Optional, List
from dataclasses import dataclass, field,fields
from game_models import GameData, ItemsDic, SkillData, SkillOperationData, MonsterDataModel, MonsterDropItemDataModel, \
    ArmorDataModel, WeaponDataModel, ItemDataModel, JobBonusDataModel, StatusFormulaDataModel, GameText, \
    GameSettingDataModel, AreaData, LvAndExpDataModel,ItemEffectData
from formula_parser import FormulaParser
from typing import Tuple
from commonfunction import clamp, battlelog_text_processor, get_text, get_time_stap
from skill_processor import (execute_skill_operation, execute_item_operation,
                             status_skill_effect_end, skill_all_condition_process, skill_condition_process,
                             skill_continuancebuff_bonus_processor, event_trigger_condition_process)
from status_operation import StatusValues
from AICombatAction import ai_action
from commontool import Event
import os


@dataclass
class BattleCharacter:
    #基本資料
    name: str
    jobBonusData: JobBonusDataModel
    ai_id: str
    level: int
    stats: Dict[str, int]
    basal: StatusValues  #基本屬性數值
    equip: StatusValues  #裝備數值
    effect: StatusValues  #效果影響數值
    equipped_weapon: Optional[WeaponDataModel]
    equipped_armor: Optional[ArmorDataModel]
    skills: List[SkillData]
    items: List[Tuple[ItemDataModel, int]]
    characterType: bool  #當前攻擊者類型 True:人物 False:怪物
    attackTimer: float = 0.0  #普通攻擊計時器
    skill_usage: Dict = field(default_factory=dict)  # ✅ 修正

    #UI物件
    buff_bar: Optional[object] = None  #buff效果提示欄
    debuff_bar: Optional[object] = None  #負面狀態效果提示欄
    passive_bar: Optional[object] = None  #被動效果提示欄
    battle_log = None  #戰鬥日誌
    item_manager: Optional[object] = None  #道具管理器
    ai: "ai_action" = field(init=False)  # Q learning AI
    character_overview: Optional[object] = None  # 角色能力值總覽

    #動態資料
    skill_cooldowns: Dict[str, float] = field(default_factory=dict)  # skill_id -> remaining_cooldown_time
    item_cooldowns: Dict[str, float] = field(default_factory=dict)  # item_id -> remaining_cooldown_time
    buff_skill: Dict[str, Tuple[SkillData, float]] = field(default_factory=dict)  #運行中的buff效果
    buff_item: Dict[str, Tuple[ItemDataModel, float]] = field(default_factory=dict)  #運行中的buff效果
    debuff_skill: Dict[str, Tuple[SkillOperationData, float]] = field(default_factory=dict)  #運行中的負面狀態
    controlled_for_attack: float = 0.0  #受到控制不得使用普通攻擊類型
    controlled_for_skill: float = 0.0  #受到控制不得使用技能類型
    attackTimerFunc = None  #儲存普攻計時任務
    hp_recovery_time: float = 0.0  #血量自然恢復間隔計時
    mp_recovery_time: float = 0.0  #魔力自然恢復間隔計時
    update_hp_mp = None  #用來儲存更新雙方血量魔力的匿名方法
    additive_buff_event: Event = field(default_factory=Event, init=False, repr=False)  #滿足條件的Buff持續疊加的事件
    additive_buff_time = 0  #滿足條件的Buff 作用的間隔時間
    additive_debuff_event: Event = field(default_factory=Event, init=False, repr=False)  #滿足條件的DeBuff持續疊加的事件
    additive_debuff_time = 0  #滿足條件的DeBuff 作用的間隔時間
    subscription_skill_event:Event = field(default_factory=Event, init=False, repr=False)     #需要訂閱的技能 訂閱後將每固定時間檢查是否達成條件而執行
    subscription_skill_time = 0  #紀錄訂閱技能的呼叫間隔時間(區間一到就呼叫一次技能)
    temp_dict: Dict[str, object] = field(default_factory=dict)  #暫存動態資料 有需要再寫入 (例如:怒氣,疊層值)
    upgrade_skill_dict:Dict[str,SkillData] = field(default_factory=dict)    #存放所選職業的技能內有升級技能的字典
    enhance_skill_dict:Dict[str,SkillData] = field(default_factory=dict)    #存放所選職業的技能內有強化技能的字典
    inherit_damage_skill_dict:Dict[str,SkillData] = field(default_factory=dict)    #存放所選職業的技能內有繼承技能傷害的字典
    event_trigger_dict:Dict[str,list] = field(default_factory=dict)    #事件觸發字典 {"Block": [(trigger_skill, probability), ...]}

    def __post_init__(self):
        # 在物件建立後，才初始化 AI
        self.ai = ai_action(self.ai_id, self)

    def action_check(self, skill: SkillData) -> bool:
        """
        攻擊指令許可確定
        """
        if (skill.Name == "普通攻擊"):
            return self.stats["HP"] > 0 and self.controlled_for_attack <= 0
        else:
            return self.stats["HP"] > 0 and self.controlled_for_skill <= 0

    def is_alive(self) -> bool:
        return self.stats["HP"] > 0

    def pass_time(self, dt: float):
        """
        獨立計時器
        """

        # 技能冷卻遞減
        for skill_id in list(self.skill_cooldowns):
            if self.skill_cooldowns[skill_id] > 0:
                self.skill_cooldowns[skill_id] = max(0, self.skill_cooldowns[skill_id] - dt)
                if self.skill_cooldowns[skill_id] == 0:
                    del self.skill_cooldowns[skill_id]
        for item_id in list(self.item_cooldowns):
            if self.item_cooldowns[item_id] > 0:
                self.item_cooldowns[item_id] = max(0, self.item_cooldowns[item_id] - dt)
                if self.item_cooldowns[item_id] == 0:
                    del self.item_cooldowns[item_id]

        #技能Buff時間遞減
        for buff_skill_id in list(self.buff_skill):
            skillData, skillDuration = self.buff_skill[buff_skill_id]
            skillDuration = max(0, skillDuration - dt)
            self.buff_skill[buff_skill_id] = (skillData, skillDuration)
            if (skillDuration == 0):
                stack = clamp(self.buff_bar.get_effect_stack(buff_skill_id),1,self.buff_bar.get_effect_stack(buff_skill_id))
                for op in skillData.SkillOperationDataList:
                    self.SkillEffectStatusOperation(op.InfluenceStatus, (op.AddType == "Rate"),
                                                    -1 * op.EffectValue * stack)
                self.buff_skill.pop(buff_skill_id, None)
                self.buff_bar.remove_effect(buff_skill_id)
        for buff_item_id in list(self.buff_item):
            itemData, itemDuration = self.buff_item[buff_item_id]
            itemDuration = max(0, itemDuration - dt)
            self.buff_item[buff_item_id] = (itemData, itemDuration)
            if (itemDuration == 0):
                stack = self.buff_bar.get_effect_stack(buff_item_id)
                for op in itemData.ItemEffectDataList:
                    self.SkillEffectStatusOperation(op.InfluenceStatus, (op.AddType == "Rate"),
                                                    -1 * op.EffectValue * stack)
                self.buff_item.pop(buff_item_id, None)
                self.buff_bar.remove_effect(buff_item_id)
        #負面狀態遞減
        for debuff_id in list(self.debuff_skill):
            op, debuffDuration = self.debuff_skill[debuff_id]
            debuffDuration = max(0, debuffDuration - dt)
            self.debuff_skill[debuff_id] = (op, debuffDuration)
            if (debuffDuration == 0):
                log, dmg, cd = status_skill_effect_end(op, self)
                self.battle_log.append(log)
                del self.debuff_skill[debuff_id]
                self.debuff_bar.remove_effect(debuff_id)

        # 血量自然恢復計時
        if ("HP_Recovery" in self.stats):
            if (self.hp_recovery_time < GameData.Instance.GameSettingDic["HpRecoverySec"].GameSettingValue):
                self.hp_recovery_time += dt
            else:
                self.hp_recovery_time = 0
                self.stats["HP"] = clamp(self.stats["HP"] + self.stats["HP_Recovery"], 0,
                                                        self.stats["MaxHP"])
                self.update_hp_mp()
                self.battle_log.append(battlelog_text_processor({
                    "caster_text": self.name,
                    "caster_color": "#00ffdc",
                    "descript_text": self.stats["HP_Recovery"],
                    "descript_color": "#ff0000",
                }, "naturalHpRecovery"))

        # 魔力自然恢復計時
        if ("MP_Recovery" in self.stats):
            if (self.mp_recovery_time < GameData.Instance.GameSettingDic["MpRecoverySec"].GameSettingValue):
                self.mp_recovery_time += dt
            else:
                self.mp_recovery_time = 0
                self.stats["MP"] = clamp(self.stats["MP"] + self.stats["MP_Recovery"], 0,
                                                        self.stats["MaxMP"])
                self.update_hp_mp()
                self.battle_log.append(battlelog_text_processor({
                    "caster_text": self.name,
                    "caster_color": "#00ffdc",
                    "descript_text": self.stats["MP_Recovery"],
                    "descript_color": "#ff0000",
                }, "naturalMpRecovery"))

        #持續疊加的Buff
        if (self.additive_buff_time < 0.25):
            self.additive_buff_time += dt
        else:
            self.additive_buff_time = 0
            self.additive_buff_event()


        #持續疊加的Debuff
        if (self.additive_debuff_time < 0.25):
            self.additive_debuff_time += dt
        else:
            self.additive_debuff_time = 0
            self.additive_debuff_event()


        #技能訂閱的呼叫計時器
        if(self.subscription_skill_time < 1):
            self.subscription_skill_time += dt
        else:
            self.subscription_skill_time = 0
            self.subscription_skill_event()

    def use_item_id(self, itemid) -> Tuple[str, int, float]:
        for idx, (item, count) in enumerate(self.items):
            if count > 0 and item.CodeID not in self.item_cooldowns and itemid == item.CodeID:
                # 執行道具效果，只傳 item
                for temp in execute_item_operation(item, self, self):
                    #道具進入CD
                    self.item_cooldowns[item.CodeID] = item.CD
                    log_msg, damage, attack_timer = temp

                    # 使用後扣除數量
                    count -= 1
                    self.item_manager.consume_item(itemid)
                    if count <= 0:
                        # 數量為0，刪除這個道具
                        self.items.pop(idx)
                    else:
                        # 更新數量
                        self.items[idx] = (item, count)

                    return log_msg, damage, attack_timer  # 回傳執行結果

    def run_passive_skill(self):
        """
        運行被動技能
        """
        for s in self.skills:
            characteristic = s.Characteristic
            condition_ok = skill_all_condition_process(self, s)
            if not characteristic and condition_ok:
                for retult in execute_skill_operation(s, self, self):
                    for temp in retult:
                        log = temp[0]
                        self.battle_log.append(log)

    def fire_event_trigger(self, event_type: str, opponent):
        """觸發事件訂閱 - 執行訂閱到指定事件類型的所有技能"""

        log_results = []

        for trigger_skill, trigger_op in self.temp_dict.get(event_type, []):
            if event_trigger_condition_process(trigger_op, self):
                # 啟用 log
                log_results.append(battlelog_text_processor({
                    "caster_text": self.name,
                    "descript_text": get_text(trigger_skill.Name),
                    "descript_color": "#00c8ff",
                }, "eventTriggerActivate", get_text(f"TM_{event_type}")))

                skill_results = execute_skill_operation(trigger_skill, self, opponent)
                for result_list in skill_results:
                    if result_list is None:
                        continue
                    if isinstance(result_list, list):
                        for r in result_list:
                            if r is not None:
                                log_results.append(r[0])
                    else:
                        log_results.append(result_list[0])

        return log_results

    def add_skill_buff_effect(self, skillData: SkillData, op) -> int:
        """
        增加技能buff效果
        """

        #PPO獎勵
        reward = 0

        #檢查Bonus資料

        if(op.Bonus is not None):
            temp = skill_continuancebuff_bonus_processor(self,op)
            match(temp):
                case int():
                    temp_id = get_time_stap(skillData.SkillID)
                    self.SkillEffectStatusOperation(op.InfluenceStatus, (op.AddType == "Rate"), op.EffectValue*temp)
                    #疊層最大值
                    max = int(next(
                            (x for x in GameData.Instance.SkillDataDic[op.Bonus[1]].SkillOperationDataList
                                if x.SkillComponentID == "AdditiveBuff"), None
                            ).Bonus[0])
                    #疊層獎勵處理
                    if (temp/max) >= 0.85:
                        reward = 20.0  # 接近滿層釋放，大獎勵
                    if (temp/max) >= 0.6:
                        reward = 10.0  # 高層釋放，大獎勵
                    elif (temp/max) >= 0.3:
                        reward = 5.0  # 普通層數，小獎勵
                    else:
                        reward  = -10.0  # 低層數浪費，懲罰

                #訂閱技能
                case "Subscription":

                    def SubscriptionSkillEffect(subscriptionSkillOp,temp_id):

                        #先做條件檢查
                        if(skill_condition_process(self,subscriptionSkillOp)):
                            #檢查buff技能是否再做用中
                            subscriptionSkillId = next((x for x in self.buff_skill.keys() if x == temp_id), None)
                            #若正再做用 刷新時間
                            if subscriptionSkillId is not None:
                                self.buff_skill[subscriptionSkillId] = (skillData, subscriptionSkillOp.EffectDurationTime)
                            #若未再做用 開始作用
                            else:
                                self.SkillEffectStatusOperation(subscriptionSkillOp.InfluenceStatus, (subscriptionSkillOp.AddType == "Rate"), subscriptionSkillOp.EffectValue)
                                self.buff_bar.add_skill_effect(temp_id, skillData)
                                self.buff_skill[temp_id] = (skillData, subscriptionSkillOp.EffectDurationTime)

                    temp_id = get_time_stap(skillData.SkillID)
                    self.subscription_skill_event += lambda: SubscriptionSkillEffect(op,temp_id)

                    return 0

                case _:
                    temp_id = get_time_stap(skillData.SkillID)
                    self.SkillEffectStatusOperation(op.InfluenceStatus, (op.AddType == "Rate"), op.EffectValue)

            self.buff_bar.add_skill_effect(temp_id, skillData,temp)
            self.buff_skill[temp_id] = (skillData, op.EffectDurationTime)
        else:
            self.buff_bar.add_skill_effect(skillData.SkillID, skillData)
            self.buff_skill[skillData.SkillID] = (skillData, op.EffectDurationTime)
            self.SkillEffectStatusOperation(op.InfluenceStatus, (op.AddType == "Rate"), op.EffectValue)
            #一般常駐buff 獎勵為5
            if(skillData.CD == 1):
                reward = 5
        return reward

    def add_skill_passive_effect(self, skillData: SkillData, op):
        """
        增加被動技能效果
        """
        temp_id = get_time_stap(skillData.SkillID)
        self.SkillEffectStatusOperation(op.InfluenceStatus, (op.AddType == "Rate"), op.EffectValue)
        # 效果欄增加資料
        self.passive_bar.add_skill_effect(temp_id, skillData)

    def add_skill_addtive_effect(self, skillData: SkillData, op, stackCount: int):
        """
        增加疊加型效果
        """
        skill_id = skillData.SkillID
        duration = skillData.SkillOperationDataList[0].EffectDurationTime
        effect_value = op.EffectValue
        is_rate = (op.AddType == "Rate")

        # 找出目前所有同技能 ID 的 buff
        existing_keys = [k for k in self.buff_skill if k.startswith(skill_id)]

        # 如果已存在同技能效果
        if existing_keys:
            # 更新 buff 時間（假設你要延長或覆蓋時間）
            for key in existing_keys:
                # 取得疊層(若沒有為0)
                tempStack = self.passive_bar.get_effect_stack(key)
                # 先移除舊疊層的效果
                if tempStack > 0:
                    self.SkillEffectStatusOperation(op.InfluenceStatus, is_rate, effect_value * tempStack * -1)

                self.buff_skill[key] = (skillData, duration)
                self.passive_bar.add_skill_effect(key, skillData, stackCount)

        else:
            # 新的 buff 加入 buff bar 並生成唯一 key
            key = get_time_stap(skill_id)
            self.buff_skill[key] = (skillData, duration)
            self.passive_bar.add_skill_effect(key, skillData, stackCount)

        # 套用新的疊層效果
        new_stack = self.passive_bar.get_effect_stack(skill_id)
        self.SkillEffectStatusOperation(op.InfluenceStatus, is_rate, effect_value * new_stack)

    def set_skill_addtive_effect(self, targetSkillData: SkillData, op, stackCount: int):
        """
        設定疊加型效果

        Args:
            stackCount: 設定的目標疊層
        """
        skill_id = targetSkillData.SkillID
        duration = targetSkillData.SkillOperationDataList[0].EffectDurationTime
        effect_value = op.EffectValue
        is_rate = (op.AddType == "Rate")

        # 找出目前所有同技能 ID 的 buff
        existing_keys = [k for k in self.buff_skill if k.startswith(skill_id)]

        # 如果已存在同技能效果
        if existing_keys:
            # 更新 buff 時間（假設你要延長或覆蓋時間）
            for key in existing_keys:
                # 取得疊層(若沒有為0)
                tempStack = self.passive_bar.get_effect_stack(key)
                # 設定疊層值
                self.passive_bar.set_effect_stack(key, stackCount)
                # 舊疊層與新疊層值的相差值
                phase_difference = tempStack - stackCount
                # 移除舊疊層的效果
                if tempStack > 0:
                    self.SkillEffectStatusOperation(op.InfluenceStatus, is_rate, effect_value * phase_difference * -1)

                self.buff_skill[key] = (targetSkillData, duration)
        else:
            print(f"沒有存在相同的效果{skill_id}")

    def add_item_buff_effect(self, op, itemData: ItemDataModel):
        """
        增加道具buff效果
        """
        temp_id = get_time_stap(itemData.CodeID)
        self.SkillEffectStatusOperation(op.InfluenceStatus, (op.AddType == "Rate"), op.EffectValue)

        self.buff_bar.add_item_effect(temp_id, itemData)
        self.buff_item[temp_id] = (itemData, itemData.ItemEffectDataList[0].EffectDurationTime)

    def add_debuff_effect(self, op: SkillOperationData):
        """
        增加負面效果(含 控制狀態)
        """
        temp_id = get_time_stap(op.InfluenceStatus)
        self.debuff_bar.add_debuff(temp_id, op.InfluenceStatus)
        duration = op.EffectDurationTime - self.stats["DisorderResistance"]
        # ReduceCCTime 只對控制狀態生效（首次CC不受影響，後續才減少）
        if op.SkillComponentID == "CrowdControl" and self.stats["ReduceCCTime"] > 0:
            duration *= self.stats["ReduceCCTime"]
        self.debuff_skill[temp_id] = op, max(0, duration)


    def CrowdControlCalculator(self, op: SkillOperationData, value: int):
        """
        控制效果計算
        """
        match (op.InfluenceStatus):
            case "Stun":
                self.controlled_for_skill += value
                self.controlled_for_attack += value
            case "Taunt":
                self.controlled_for_attack += value
            case "Inhibit":
                self.controlled_for_skill += value
                self.controlled_for_attack += value

    def processRecovery(self, op,effectName:str, caster, target) -> Tuple[str, int, float]:
        """
        處理任何恢復效果 
        """
        maxValue = ""
        logRecoveryText = ""
        match (op):
            case SkillOperationData():
                maxValue = "MaxMP" if op.Bonus[0] == "MP" else "MaxHP"
                if op.Bonus[0] in target.stats:
                    target.stats[op.Bonus[0]] = clamp(
                        target.stats[op.Bonus[0]] + round(op.EffectValue * target.stats[op.InfluenceStatus]),
                        target.stats[op.Bonus[0]],
                        target.stats[maxValue])
                    logRecoveryText= round(op.EffectValue * target.stats[op.InfluenceStatus])

            case ItemEffectData():
                maxValue = "MaxMP" if op.InfluenceStatus == "MP" else "MaxHP"
                if op.InfluenceStatus in target.stats:
                    logRecoveryText =  op.EffectValue
                    target.stats[op.InfluenceStatus] = clamp(
                        target.stats[op.InfluenceStatus] + op.EffectValue,
                        target.stats[op.InfluenceStatus],
                        target.stats[maxValue])



        self.update_hp_mp()
        color_code = "#2945FF" if op.InfluenceStatus == "MP" else "#ff0000";
        recovery_type = "魔力" if op.InfluenceStatus == "MP" else "血量";
        return battlelog_text_processor({
            "caster_text": caster.name,
            "caster_color": "#00ffdc",
            "descript_text": get_text(effectName),
            "descript_color": "#ff9300",
            "target_text": target.name,
            "target_color": "#83ff00",
        }, "effectRecovery", f"<color={color_code}>{logRecoveryText} {recovery_type} </color>"), op.EffectValue, 0

    #region 戰鬥數值 計算

    def HitCalculator(self, skill: SkillData, target):
        """
        命中計算
        """
        selfHit = 0;
        if self.characterType:
            if (skill.Name != "普通攻擊"):
                match skill.AdditionMode:
                    case "MeleeATK":
                        selfHit = self.stats["MeleeHit"];
                    case "RemoteATK":
                        selfHit = self.stats["RemoteHit"];
                    case "MageATK":
                        selfHit = self.stats["MageHit"];
                    case _:
                        print("未知屬性")
            else:
                selfHit = self.stats["MeleeHit"];
        else:
            selfHit = self.stats["Hit"];

        # 命中率 四捨五入取整數
        hit_value = round(selfHit * 100 / max(1, selfHit + target.stats["Avoid"]))
        # 命中判定  0～100 隨機
        is_hit = random.randint(0, 100)

        if is_hit <= hit_value:
            return self.BlockCalculator(skill, target)
        else:
            missResult = battlelog_text_processor({
                "caster_text": self.name,
                "caster_color": "#636363",
                "caster_size": 12,
                "descript_text": get_text(skill.Name),
                "descript_color": "#ff9300",
            }, "miss"), 0, self.attackTimer
            return [missResult]

    def BlockCalculator(self, skill: SkillData, target):
        """
        格檔計算
        """
        is_block = random.randint(0, 100)
        if (is_block <= target.stats["BlockRate"]):
            blockResult = battlelog_text_processor({
                "caster_text": self.name,
                "caster_color": "#636363",
                "caster_size": 12,
                "descript_text": get_text(skill.Name),
                "descript_color": "#ff9300",
            }, "block"), 0, self.attackTimer
            results = [blockResult]

            # 事件觸發檢查 - Block
            for trigger_skill, trigger_op in target.temp_dict.get("Block", []):
                if event_trigger_condition_process(trigger_op, target):
                    counter_results = execute_skill_operation(trigger_skill, target, self)
                    for result_list in counter_results:
                        if result_list is None:
                            continue
                        if isinstance(result_list, list):
                            for r in result_list:
                                if r is not None:
                                    results.append(r)
                        else:
                            results.append(result_list)

            return results
        else:
            return self.CrtCalculator(skill, target)

    def CrtCalculator(self, skill: SkillData, target):
        """
        暴擊計算
        """
        #暴擊率 
        crt_value = self.stats["Crt"]*(self.stats["Crt"] / max(1, self.stats["Crt"] + target.stats["CrtResistance"]))
        #print(f'>>暴擊率:{self.stats["Crt"] } 暴擊抵抗:{target.stats["CrtResistance"]}')

        is_Crt = random.randint(0, 100)
        #print(f'暴擊率:{crt_value} 暴擊隨機值:{is_Crt}')

        #暴擊判定
        return self.AttackCalculator(skill, target, (is_Crt <= crt_value));

    def AttackCalculator(self, skill: SkillData, target, is_Crt: bool):
        """
        攻擊計算
        """
        selfATK = 0;
        targetDEF = 0;
        if self.characterType:
            if skill.Name != "普通攻擊":
                match skill.AdditionMode:
                    case "MeleeATK":
                        selfATK = self.stats["MeleeATK"];
                        targetDEF = target.stats["DEF"];
                    case "RemoteATK":
                        selfATK = self.stats["RemoteATK"];
                        targetDEF = target.stats["DEF"];
                    case "MageATK":
                        selfATK = self.stats["MageATK"];
                        targetDEF = target.stats["MDEF"];
                    case _:
                        print("未知屬性")
            else:
                selfATK = self.stats["MeleeATK"];
                targetDEF = target.stats["DEF"];
        else:
            selfATK = self.stats["ATK"];
            match self.stats["AttackMode"]:
                case "MeleeATK":
                    targetDEF = target.stats["DEF"];
                case "RemoteATK":
                    targetDEF = target.stats["DEF"];
                case "MageATK":
                    targetDEF = target.stats["MDEF"];
                case _:
                    print("未知屬性")

        #暫存結果
        returnResult = []

        # 實現技能效果
        parser = FormulaParser()
        variables = {
            "attacker_attack": selfATK,  #攻擊者的攻擊力
            "target_defense": targetDEF,  #受攻擊者防禦
            "skill_power": skill.Damage,  #傷害倍率
            "attacker_level": self.level,  #攻擊者等級
            "target_level": target.level,  #受攻擊者等級
            "random_factor": random.uniform(0.85, 1.15),
            "base_damage": skill.Damage
        }
        parser.set_variables(variables)

        #計算防禦減免
        defenseRatio = clamp(variables["target_defense"] / (variables["target_defense"] + 9), 0.1, 0.75)
        # print(f"技能傷害倍率:{skill.Damage}")
        #計算傷害
        if is_Crt:
            damage = round(variables["attacker_attack"] * skill.Damage * 1.5) + self.stats["CrtDamage"]
        else:
            damage = round(variables["attacker_attack"] * skill.Damage)

        finalDamage = clamp(round(damage * (1 - defenseRatio)) - target.stats["DamageReduction"], 0,
                                           round(damage * (1 - defenseRatio)) - target.stats["DamageReduction"])
        #print(f"看看 {skill.SkillID} 技能倍率{skill.Damage}")
        #print(f"攻擊對象:{self.characterType}，攻擊者傷害:{damage}，防禦減免{defenseRatio}，最後傷害{finalDamage}")

        #處理額外傷害
        finalDamage = self.BonusDamageCalulator(finalDamage, target)
        target.stats["HP"] -= finalDamage

        color_code = f'<color=#ffd600><size=13><b>{finalDamage}</size></color></b>' if is_Crt else f'<color=#ff0000><size=11>{finalDamage}</size></color>'

        returnResult.append((battlelog_text_processor({
            "caster_text": self.name,
            "caster_color": "#636363",
            "caster_size": 12,
            "descript_text": get_text(skill.Name),
            "descript_color": "#ff0000",
            "target_text": target.name,
            "target_color": "#363636"
        }, "damage", color_code), finalDamage, self.attackTimer))

        #處理吸血
        if (self.stats["RecoveryDmg"] != 0 and damage != 0):
            returnResult.append(self.RecoveryDmgProcessor(finalDamage))

        return returnResult

    def ElementAttackCalulator(self, skill:SkillData,op: SkillOperationData, target)-> Tuple[str, int, float]:
        """
            屬性攻擊計算
        """
        #   攻擊方魔法傷害值 * 屬性傷害增幅 * (1 - 被剋屬性減免)

        attackerElementDamage = 0
        targetElementDefense = 0
        colorCode = ""

        match (op.InfluenceStatus):
            case "FireDamage":
                attackerElementDamage = self.stats["FireDamage"]
                targetElementDefense = self.stats["FireDefense"]
                colorCode = "#FF4000"

            case "WaterDamage":
                attackerElementDamage = self.stats["WaterDamage"]
                targetElementDefense = self.stats["WaterDefense"]
                colorCode = "#0084FF"
            case "EarthDamage":
                attackerElementDamage = self.stats["EarthDamage"]
                targetElementDefense = self.stats["EarthDefense"]
                colorCode = "#A36000"
            case "WindDamage":
                attackerElementDamage = self.stats["WindDamage"]
                targetElementDefense = self.stats["WindDefense"]
                colorCode = "#26FF99"
            case "HolyDamage":
                attackerElementDamage = self.stats["HolyDamage"]
                targetElementDefense = self.stats["HolyDefense"]
                colorCode = "#FFF800"
            case "DarkDamage":
                attackerElementDamage = self.stats["DarkDamage"]
                targetElementDefense = self.stats["DarkDefense"]
                colorCode = "#242424"

        calulatordmg = (attackerElementDamage*op.EffectValue*self.stats["ElementDamageIncrease"])-(targetElementDefense*target.stats["ElementDamageReduction"])
        calulatordmg =  clamp(calulatordmg, 0, calulatordmg)
        calulatordmg = round(self.BonusDamageCalulator(calulatordmg, target))

        return battlelog_text_processor({
            "caster_text": self.name,
            "caster_color": "#636363",
            "caster_size": 12,
            "descript_text": get_text(skill.Name),
            "descript_color": "#910000",
            "target_text": target.name,
            "target_color": "#363636"
        }, "elementDamage", f"<color={colorCode}>{calulatordmg}</color>"), calulatordmg, 0

    def BonusDamageCalulator(self,damage,target) -> int:
        """
        額外傷害計算
        """

        #攻擊方取得 傷害增加參數
        increaseDamagerate = clamp(self.stats["IncreaseDmgRate"],1,self.stats["IncreaseDmgRate"])
        increaseDamage = self.stats["IncreaseDmgValue"]
        Damage = clamp(self.stats["Damage"],1,self.stats["Damage"])

        newDamage = (damage*increaseDamagerate+increaseDamage)*Damage

        #防守方取得 傷害減免倍率
        finalDamageReductionRate = clamp((1-target.stats["FinalDamageReductionRate"]), 0, 1)

        newDamage = newDamage*finalDamageReductionRate
        return newDamage

    def RecoveryDmgProcessor(self,damage):
        """
        吸血效果處理
        """

        recoveryValue = round(damage*self.stats["RecoveryDmg"]/100)
        self.stats["HP"] = clamp(self.stats["HP"] + recoveryValue,self.stats["HP"],self.stats["MaxHP"])

        return battlelog_text_processor({
            "caster_text": self.name,
            "caster_color": "#00ffdc",
            "descript_text": recoveryValue,
            "descript_color": "#ff9300",
        }, "recoveryDmg"), 0, 0

    #endregion

    #region 效果影響能力值的計算

    def SkillEffectStatusOperation(self, stateType: str, isRate: bool, value: float):
        """
        技能效果運算
        """
        self.tempHp = 0
        self.tempMp = 0

        # 特殊例外處理
        match stateType:
            case "MaxHP":
                self.tempHp = self._apply_effect("MaxHP", isRate, value)
            case "MaxMP":
                self.tempMp = self._apply_effect("MaxMP", isRate, value)
            # 三種攻擊一起加
            case "ATK":
                for a in ("MeleeATK", "RemoteATK", "MageATK"):
                    self._apply_effect(a, isRate, value)
            case "ReduceTargetDmg" | "TransferDmg":
                self._apply_effect("FinalDamageReductionRate", isRate, value)
            case "SpeedSlow":
                self._apply_effect("SpeedSlowRate" if(isRate is True) else "SpeedSlow", isRate, value)
            case "ReduceCCTime":
                # EffectValue 直接作為倍率儲存（基礎值為0，Rate*0=0 無意義）
                self._apply_effect("ReduceCCTime", False, value)
            # 一般數值
            case _:
                if hasattr(self.effect, stateType):
                    self._apply_effect(stateType, isRate, value)
                #else:
                    #print("未定義的參數:", stateType)
        #print(f"屬性: {stateType} 增加值:{value} 增加方式: {isRate}")
        # 套完 Effect 重算 stats
        self._recalculate_stats()
        self.character_overview.update_state(self.stats)

    def _apply_effect(self, attr: str, isRate: bool, value: float):
        """
        效果影響的參數加成處理
        """
        base_val = getattr(self.basal, attr)

        if isRate:
            add_val = base_val * value
        else:
            add_val = value

        # 只有在 base_val 是 int 才 round
        if isinstance(base_val, int):
            add_val = round(add_val)

        current = getattr(self.effect, attr)
        setattr(self.effect, attr, current + add_val)
        return add_val

    def _recalculate_stats(self):
        """
        能力值運算計算
        """

        for f in fields(StatusValues):
            name = f.name
            if name != 'HP' and name != 'MP':
                self.stats[name] = getattr(self.basal, name) + getattr(self.equip, name) + getattr(self.effect, name)
                #if name == "BlockRate":
                    #print(f"名稱: {name} 基礎值:{getattr(self.basal, name)} 裝備值: {getattr(self.equip, name)} 效果值: {getattr(self.effect, name)} 總值: {self.stats[name]}")
        # 套 buff 增加的當前 HP/MP
        self.stats["HP"] += self.tempHp
        self.stats["MP"] += self.tempMp
    #endregion

class BattleSimulator:
    def __init__(self, game_data, gui):
        self.game_data = game_data
        self.gui = gui
        self.battle_log: List[str] = []
        self.damage_data: List[Dict] = []
        self.skill_usage: Dict[str, int] = {}
        self.update_hp_mp = None  #用來儲存更新雙方血量魔力的匿名方法
        self._after_ids: List = []  # 追蹤所有 tkinter.after 的 ID
        self.is_battling = False  # 戰鬥是否進行中

    def _schedule(self, ms, callback):
        """統一排程 tkinter.after 並追蹤 ID，方便中止時一次取消"""
        after_id = self.gui.root.after(ms, callback)
        self._after_ids.append(after_id)
        return after_id

    def stop_battle(self):
        """中止目前正在進行的即時戰鬥"""
        self.is_battling = False
        for after_id in self._after_ids:
            try:
                self.gui.root.after_cancel(after_id)
            except ValueError:
                pass
        self._after_ids.clear()

    def battle_tick(self, player, enemy):
        """
        啟動各自計時器
        """
        if not self.is_battling:
            return

        dt = 0.1  # 每 0.1 秒刷新一次

        # 暫停不執行並Delay
        if (os.environ.get("PAUSED") == "1"):
            self._schedule(int(dt * 100), lambda: self.battle_tick(player, enemy))
            return

        if player.is_alive() and enemy.is_alive():
            player.pass_time(dt)
            enemy.pass_time(dt)
            self._schedule(int(dt * 1000), lambda: self.battle_tick(player, enemy))

    def attack_loop(self, attacker: BattleCharacter, target):
        """獨立的攻擊計時器迴圈"""
        if not self.is_battling:
            return

        # 暫停不執行並Delay
        if (os.environ.get("PAUSED") == "1"):
            self._schedule(
                100, lambda: self.attack_loop(attacker, target)
            )
            return

        if attacker.is_alive() and target.is_alive():
            action_id, state = attacker.ai.choose_action(attacker, target)
            self.ai_choose_result(attacker.ai, state, attacker, target, action_id)
        else:
            self.check_battle_result(attacker,target)

    def ai_choose_result(self, ai, state, attacker: BattleCharacter, target: BattleCharacter, result: str):
        """
        AI 選擇&結果
        """
        reward = 0
        total_attack_timer = 0
        match (result):
            case "NORMAL_ATTACK":
                normal_attack = SkillData(
                    SkillID="NORMAL_ATTACK",
                    Name="普通攻擊",
                    Damage=1,
                    CastMage=0,
                    # 其他必要參數...
                )
                if attacker.action_check(normal_attack):
                    for log_msg, damage, attack_timer in execute_skill_operation(normal_attack, attacker, target):
                        self.battle_log.append(log_msg)
                        reward += ai.calculate_reward(damage,target.is_alive(),attacker.is_alive())
                        total_attack_timer += attack_timer
                        self.battle_log.append(battlelog_text_processor({
                            "caster_text": attacker.name,
                            "caster_color": "#636363",
                            "caster_size": 12,
                            "descript_text": "普攻",
                            "descript_color": "#ff0000",
                        }, "normalAttckTimer", f"{total_attack_timer:.2f}"))
                        self.damage_data.append({
                            "attacker": attacker.name,
                            "target": target.name,
                            "skill": "NORMAL_ATTACK",
                            "Damage": damage,
                        })
                else:
                    reward = -0.1  # 不可施放技能 懲罰值

                    # 依然要呼叫 record_result，確保 Buffer 長度對齊
                    # 這裡 done 通常是 False，因為戰鬥還沒結束，只是這回合浪費了
                    ai.record_result(reward, False)
                    self._schedule(
                        100, lambda: self.attack_loop(attacker, target)
                    )
                    return
            #道具
            case str() if result.startswith("USE_ITEM:"):
                log_msg, damage, attack_timer = attacker.use_item_id(result.replace("USE_ITEM:", ""))
                self.battle_log.append(log_msg)
                reward += ai.calculate_reward(damage,target.is_alive(),attacker.is_alive())
                total_attack_timer += attack_timer
            #施放技能
            case _:
                skill = next(s for s in attacker.skills if s.SkillID == result)
                attacker.skill_usage[get_text(skill.Name)] += 1
                if attacker.action_check(skill):
                    #print(
                        #f"{attacker.name} 使用 ：{get_text(skill.Name)} ({skill.SkillID}) 原本魔力為：{attacker.stats["MP"]} 消耗魔力為：{skill.CastMage}")
                    attacker.stats["MP"] -= skill.CastMage
                    for resultList in execute_skill_operation(skill, attacker, target):
                        if resultList is None:
                            print(f"資料有錯喔!: {skill.SkillID}  → temp 本身就是 None")
                        elif isinstance(resultList, list) and any(x is None for x in resultList):
                            print(f"資料有錯喔!: {skill.SkillID}  → temp 裡面有 None: {resultList}")
                        for temp in resultList:
                            log_msg, damage, attack_timer = temp
                            self.battle_log.append(log_msg)

                            attacker.skill_cooldowns[skill.SkillID] = skill.CD
                            # 套用 HitReduceSec CD 減少
                            cd_key = f"cd_reduction_{skill.SkillID}"
                            if cd_key in attacker.temp_dict:
                                attacker.skill_cooldowns[skill.SkillID] = max(0,
                                    attacker.skill_cooldowns[skill.SkillID] - attacker.temp_dict.pop(cd_key))
                            reward += ai.calculate_reward(damage,target.is_alive(),attacker.is_alive())
                            total_attack_timer += attack_timer
                            self.damage_data.append({
                                "attacker":attacker.name,
                                "target":target.name,
                                "skill":get_text(skill.Name),
                                "Damage":damage,
                            })
                    self.battle_log.append(battlelog_text_processor({
                        "caster_text": attacker.name,
                        "caster_color": "#636363",
                        "caster_size": 12,
                        "descript_text": get_text(skill.Name),
                        "descript_color": "#ff0000",
                    }, "skillTimer", f"{1 if skill.Type == "Buff" else 1.8}"))
                else:
                    reward = -0.1  # 不可施放技能 懲罰值

                    # 依然要呼叫 record_result，確保 Buffer 長度對齊
                    # 這裡 done 通常是 False，因為戰鬥還沒結束，只是這回合浪費了
                    ai.record_result(reward, False)
                    self._schedule(
                        100, lambda: self.attack_loop(attacker, target)
                    )
                    return

        self.gui.display_battle_log(self.get_battle_log())
        self.update_hp_mp()
        next_state = ai.get_state(attacker, target)
        done =(not attacker.is_alive()) or not (target.is_alive())
        ai.record_result(reward,done)
        attacker.attackTimerFunc = self._schedule(int(total_attack_timer * 1000),
                                                    lambda: self.attack_loop(attacker, target))

    def simulate_battle(self, player: BattleCharacter, enemy: BattleCharacter):
        """開啟戰鬥模擬"""
        self.is_battling = True
        self.battle_log.clear()
        self.damage_data.clear()
        player.skill_usage = {get_text(s.Name):0 for s in player.skills}
        enemy.skill_usage = {get_text(s.Name):0 for s in enemy.skills}

        player.battle_log = self.battle_log
        enemy.battle_log = self.battle_log

        #能力值總覽初始化
        self.gui.player_overview.update_state(player.stats)
        self.gui.enemy_overview.update_state(enemy.stats)

        player.run_passive_skill()
        enemy.run_passive_skill()

        # 觸發 InCombatStatus 事件（進入戰鬥）
        self.battle_log.extend(player.fire_event_trigger("InCombatStatus", enemy))
        self.battle_log.extend(enemy.fire_event_trigger("InCombatStatus", player))

        #匿名方法 更新雙方血量魔力
        def update_hp_mp():
            self.gui.player_hp_bar.set_value(player.stats["HP"], player.stats["MaxHP"])
            self.gui.player_mp_bar.set_value(player.stats["MP"], player.stats["MaxMP"])
            self.gui.enemy_hp_bar.set_value(enemy.stats["HP"], enemy.stats["MaxHP"])
            self.gui.enemy_mp_bar.set_value(enemy.stats["MP"], enemy.stats["MaxMP"])
            self.gui.player_overview.update_state(player.stats)
            self.gui.enemy_overview.update_state(enemy.stats)

        self.update_hp_mp = update_hp_mp

        player.update_hp_mp = update_hp_mp
        enemy.update_hp_mp = update_hp_mp

        #初始化雙方血量魔力
        self.update_hp_mp()

        #雙方獨立計時器啟動
        self.battle_tick(player, enemy)

        #雙方同時運作攻擊計時器
        self.attack_loop(player, enemy)
        self.attack_loop(enemy, player)

    def check_battle_result(self, player: BattleCharacter, enemy: BattleCharacter):
        """
        進行戰鬥結果確認
        """
        self.is_battling = False
        if player.is_alive():
            print(f"{enemy.name} 被擊敗了！{player.name} 獲勝！")
            self.battle_log.append(f"{enemy.name} 被擊敗了！{player.name} 獲勝！")
            self.gui.battle_results.append(True)
        else:
            print(f"{player.name} 被擊敗了！{enemy.name} 獲勝！")
            self.battle_log.append(f"{player.name} 被擊敗了！{enemy.name} 獲勝！")
            self.gui.battle_results.append(False)

        self.gui.display_battle_log(self.get_battle_log())
        # 保存戰鬥數據用於統計
        self.gui.last_battle_data = {
            "damage": self.get_damage_data(),
            "player_skill_usage": player.skill_usage,
            "enemy_skill_usage": enemy.skill_usage,
            "result": player.is_alive()
        }
        #AI訓練資料更新
        player.ai.update_ppo()

        # 通知 GUI 戰鬥結束（恢復按鈕狀態）
        if hasattr(self.gui, '_on_battle_end'):
            self.gui._on_battle_end()

    # ──────────────────────────────────────────
    # 快速略過戰鬥 (Discrete Event Simulation)
    # ──────────────────────────────────────────

    def simulate_battle_fast(self, player: BattleCharacter, enemy: BattleCharacter):
        """以離散事件模擬 (DES) 方式瞬間完成整場戰鬥"""
        self.battle_log.clear()
        self.damage_data.clear()
        player.skill_usage = {get_text(s.Name): 0 for s in player.skills}
        enemy.skill_usage = {get_text(s.Name): 0 for s in enemy.skills}

        player.battle_log = self.battle_log
        enemy.battle_log = self.battle_log

        # 使用 no-op 的 update_hp_mp（快速模式中不即時更新 GUI）
        noop = lambda: None
        self.update_hp_mp = noop
        player.update_hp_mp = noop
        enemy.update_hp_mp = noop

        # 能力值總覽初始化（使用角色自身的 overview，可能是 Dummy）
        player.character_overview.update_state(player.stats)
        enemy.character_overview.update_state(enemy.stats)

        # 執行被動技能
        player.run_passive_skill()
        enemy.run_passive_skill()

        # 觸發 InCombatStatus 事件（進入戰鬥）
        self.battle_log.extend(player.fire_event_trigger("InCombatStatus", enemy))
        self.battle_log.extend(enemy.fire_event_trigger("InCombatStatus", player))

        # ── 建立優先佇列 ──
        # 事件格式: (time, priority, event_type, data)
        #   priority: 0=TICK, 1=PLAYER_ATTACK, 2=ENEMY_ATTACK （同時間時依此順序）
        TICK = 0
        PLAYER_ATTACK = 1
        ENEMY_ATTACK = 2

        event_queue = []
        counter = 0  # 用來打破同 (time, priority) 的 tie

        def push_event(t, priority, etype):
            nonlocal counter
            heapq.heappush(event_queue, (t, priority, counter, etype))
            counter += 1

        dt = 0.1
        push_event(dt, TICK, "TICK")
        push_event(0.0, PLAYER_ATTACK, "PLAYER_ATTACK")
        push_event(0.0, ENEMY_ATTACK, "ENEMY_ATTACK")

        MAX_TIME = 300.0  # 5 分鐘上限，防止無限戰鬥

        while event_queue:
            current_time, priority, _cnt, etype = heapq.heappop(event_queue)

            if current_time > MAX_TIME:
                self.battle_log.append("戰鬥超時！（300秒）")
                break

            if not player.is_alive() or not enemy.is_alive():
                break

            if etype == "TICK":
                player.pass_time(dt)
                enemy.pass_time(dt)
                push_event(current_time + dt, TICK, "TICK")

            elif etype == "PLAYER_ATTACK":
                next_delay = self._process_action_fast(player, enemy)
                if next_delay is not None:
                    push_event(current_time + next_delay, PLAYER_ATTACK, "PLAYER_ATTACK")

            elif etype == "ENEMY_ATTACK":
                next_delay = self._process_action_fast(enemy, player)
                if next_delay is not None:
                    push_event(current_time + next_delay, ENEMY_ATTACK, "ENEMY_ATTACK")

        # 戰鬥結束，處理結果
        self._finalize_battle_fast(player, enemy)

    def _process_action_fast(self, attacker: BattleCharacter, target: BattleCharacter) -> Optional[float]:
        """
        處理一次攻擊動作（快速模式），回傳下次攻擊的延遲秒數。
        若戰鬥已結束則回傳 None。
        """
        if not attacker.is_alive() or not target.is_alive():
            return None

        ai = attacker.ai
        action_id, state = ai.choose_action(attacker, target)

        reward = 0
        total_attack_timer = 0

        match (action_id):
            case "NORMAL_ATTACK":
                normal_attack = SkillData(
                    SkillID="NORMAL_ATTACK",
                    Name="普通攻擊",
                    Damage=1,
                    CastMage=0,
                )
                if attacker.action_check(normal_attack):
                    for log_msg, damage, attack_timer in execute_skill_operation(normal_attack, attacker, target):
                        self.battle_log.append(log_msg)
                        reward += ai.calculate_reward(damage, target.is_alive(), attacker.is_alive())
                        total_attack_timer += attack_timer
                        self.battle_log.append(battlelog_text_processor({
                            "caster_text": attacker.name,
                            "caster_color": "#636363",
                            "caster_size": 12,
                            "descript_text": "普攻",
                            "descript_color": "#ff0000",
                        }, "normalAttckTimer", f"{total_attack_timer:.2f}"))
                        self.damage_data.append({
                            "attacker": attacker.name,
                            "target": target.name,
                            "skill": "NORMAL_ATTACK",
                            "Damage": damage,
                        })
                else:
                    reward = -0.1
                    ai.record_result(reward, False)
                    return 0.1  # 被控制，稍後重試

            case str() if action_id.startswith("USE_ITEM:"):
                log_msg, damage, attack_timer = attacker.use_item_id(action_id.replace("USE_ITEM:", ""))
                self.battle_log.append(log_msg)
                reward += ai.calculate_reward(damage, target.is_alive(), attacker.is_alive())
                total_attack_timer += attack_timer

            case _:
                skill = next(s for s in attacker.skills if s.SkillID == action_id)
                attacker.skill_usage[get_text(skill.Name)] += 1
                if attacker.action_check(skill):
                    attacker.stats["MP"] -= skill.CastMage
                    for resultList in execute_skill_operation(skill, attacker, target):
                        if resultList is None:
                            continue
                        elif isinstance(resultList, list) and any(x is None for x in resultList):
                            continue
                        for temp in resultList:
                            log_msg, damage, attack_timer = temp
                            self.battle_log.append(log_msg)

                            attacker.skill_cooldowns[skill.SkillID] = skill.CD
                            # 套用 HitReduceSec CD 減少
                            cd_key = f"cd_reduction_{skill.SkillID}"
                            if cd_key in attacker.temp_dict:
                                attacker.skill_cooldowns[skill.SkillID] = max(0,
                                    attacker.skill_cooldowns[skill.SkillID] - attacker.temp_dict.pop(cd_key))
                            reward += ai.calculate_reward(damage, target.is_alive(), attacker.is_alive())
                            total_attack_timer += attack_timer
                            self.damage_data.append({
                                "attacker": attacker.name,
                                "target": target.name,
                                "skill": get_text(skill.Name),
                                "Damage": damage,
                            })
                    self.battle_log.append(battlelog_text_processor({
                        "caster_text": attacker.name,
                        "caster_color": "#636363",
                        "caster_size": 12,
                        "descript_text": get_text(skill.Name),
                        "descript_color": "#ff0000",
                    }, "skillTimer", f"{1 if skill.Type == 'Buff' else 1.8}"))
                else:
                    reward = -0.1
                    ai.record_result(reward, False)
                    return 0.1  # 被控制，稍後重試

        # 記錄 AI 結果
        done = (not attacker.is_alive()) or (not target.is_alive())
        ai.record_result(reward, done)

        return total_attack_timer if total_attack_timer > 0 else attacker.attackTimer

    def _finalize_battle_fast(self, player: BattleCharacter, enemy: BattleCharacter):
        """快速戰鬥結束後：記錄結果、更新真實 GUI、觸發 AI 訓練"""
        if player.is_alive():
            self.battle_log.append(f"{enemy.name} 被擊敗了！{player.name} 獲勝！")
            self.gui.battle_results.append(True)
        else:
            self.battle_log.append(f"{player.name} 被擊敗了！{enemy.name} 獲勝！")
            self.gui.battle_results.append(False)

        # 顯示完整戰鬥日誌
        self.gui.display_battle_log(self.get_battle_log())

        # 更新真實 GUI 的 HP/MP bar 為最終狀態
        self.gui.player_hp_bar.set_value(player.stats["HP"], player.stats["MaxHP"])
        self.gui.player_mp_bar.set_value(player.stats["MP"], player.stats["MaxMP"])
        self.gui.enemy_hp_bar.set_value(enemy.stats["HP"], enemy.stats["MaxHP"])
        self.gui.enemy_mp_bar.set_value(enemy.stats["MP"], enemy.stats["MaxMP"])
        self.gui.player_overview.update_state(player.stats)
        self.gui.enemy_overview.update_state(enemy.stats)

        # 保存戰鬥數據
        self.gui.last_battle_data = {
            "damage": self.get_damage_data(),
            "player_skill_usage": player.skill_usage,
            "enemy_skill_usage": enemy.skill_usage,
            "result": player.is_alive()
        }

        # AI 訓練資料更新
        player.ai.update_ppo()

    def get_battle_log(self) -> List[str]:
        return self.battle_log

    def get_damage_data(self) -> List[Dict]:
        return self.damage_data

    def get_skill_usage(self) -> Dict[str, int]:
        return self.skill_usage
