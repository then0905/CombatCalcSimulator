from game_models import ItemDataModel, SkillData, SkillOperationData, ItemEffectData,GameData
from commonfunction import get_text, battlelog_text_processor
from typing import Tuple, Optional
import copy
import random

def execute_skill_operation(skillData: SkillData, attacker, defender)-> Optional[Tuple[str, int, float]]:
    """實現技能效果執行入口"""
    returnResult = []

    # 普通攻擊特殊處理
    if skillData.Name == "普通攻擊":
        #模擬技能端的資料儲存方式 參考Damage組件
        attackerResult = attacker.HitCalculator(skillData, defender)
        for result in attackerResult:
            returnResult.append(result)

        return returnResult

    # 執行效果
    skillResult = _execute_component(skillData, attacker, defender)
    returnResult.append(skillResult)

    return returnResult

def _check_dependency(op: SkillOperationData, history: dict) -> bool:
    """
    檢查依賴條件是否滿足

    Args:
        op: 當前技能操作
        history: 執行歷史 {index: {"componentID": str, "success": bool}}

    Returns:
        是否可以執行
    """
    depend = op.DependCondition

    # 規則 1: 空字串 = 無依賴
    if not depend or depend == "" or depend == "None":
        return True

    # 規則 2: "All" = 依賴所有前面的效果成功
    if depend == "All":
        return all(item["success"] for item in history.values())

    # 規則 3: "Prev" = 依賴上一個效果
    if depend == "Prev":
        if not history:
            return True  # 第一個效果
        last_index = max(history.keys())
        return history[last_index]["success"]

    # 規則 4: "!ComponentID" = 反向依賴（失敗才執行）
    if depend.startswith("!"):
        target_component = depend[1:]
        for item in history.values():
            if item["componentID"] == target_component:
                return not item["success"]  # 失敗才執行
        return True  # 找不到目標組件，預設可執行

    # 規則 5: "ComponentID" 或 "Comp1,Comp2" = 依賴特定組件成功
    target_components = [c.strip() for c in depend.split(",")]
    for item in history.values():
        if item["componentID"] in target_components and item["success"]:
            return True  # 任一匹配成功即可

    return False  # 找不到成功的依賴

def _execute_component(skillData: SkillData,
                       attacker, defender) -> Optional[Tuple[str, int, float]]:
    """執行單個技能組件"""
    returnResult = []
    execution_history = {}  # 記錄每個效果的執行結果

    for index, op in enumerate(skillData.SkillOperationDataList):
        # 依賴判斷（核心邏輯）
        if not _check_dependency(op, execution_history):
            execution_history[index] = {
                "componentID": op.SkillComponentID, "success": False}
            continue

        # 取得施放對象
        target = attacker if op.EffectRecive in [0, -2, -3] else defender

        # 先找出是否有升級技能資料
        upgradeDataList = attacker.upgrade_skill_dict.get(skillData.SkillID)

        if (upgradeDataList is not None):
            lastUpgradeData = upgradeDataList[-1]
            tempSkillData = upgrade_skill_processor(lastUpgradeData, skillData)
        else:
            tempSkillData = skillData

        # 先找出是否有強化技能資料
        enhanceDataList = attacker.enhance_skill_dict.get(skillData.SkillID)

        if (enhanceDataList is not None):
            tempSkillData = enhance_skill_processor(enhanceDataList, tempSkillData)

        # 記錄執行結果
        success = True

        match op.SkillComponentID:
            case "Damage":
                attackerResult = attacker.HitCalculator(tempSkillData, target)
                for result in attackerResult:
                    returnResult.append(result)
                # 判斷是否成功：damage > 0 或有效果觸發
                temp = attackerResult[0]
                success = temp[1] > 0
            case "ElementDamage":
                temp = attacker.ElementAttackCalulator(tempSkillData,op, target)
                returnResult.append(temp)
                # 判斷是否成功：damage > 0 或有效果觸發
                success = temp[1] > 0 if len(temp) > 1 else True

            case "CrowdControl":
                returnResult.append(status_skill_effect_start(op, attacker, target))

            case "MultipleDamage":
                attackerResult = attacker.HitCalculator(tempSkillData, target)
                for result in attackerResult:
                    returnResult.append(result)
                temp = attackerResult[0]
                # 判斷是否成功：damage > 0 或有效果觸發
                success = temp[1] > 0 if len(temp) > 1 else True

            case "ContinuanceBuff":
                reward = target.add_skill_buff_effect(tempSkillData, op)
                temp = f"{get_text('TM_' + op.InfluenceStatus)}: {get_text('TM_' + op.AddType).format(op.EffectValue)}"
                returnResult.append((battlelog_text_processor({
                    "caster_text": attacker.name,
                    "descript_text": temp,
                    "target_text": target.name,
                }, "continuanceBuff", op.EffectDurationTime), reward , 0.5))

            case "AdditiveBuff":
                target.additive_buff_event += lambda: skill_additive_effect_event(
                    tempSkillData, op, target)
                temp = f"{get_text('TM_' + op.InfluenceStatus)}: {get_text('TM_' + op.AddType).format(op.EffectValue)}"
                returnResult.append((battlelog_text_processor({
                    "caster_text": attacker.name,
                    "descript_text": temp,
                    "target_text": target.name,
                }, "additiveBuff", op.EffectDurationTime), 0, 0.5))

            case "Debuff":
                returnResult.append(status_skill_effect_start(op, attacker, target))

            case "PassiveBuff":
                target.add_skill_passive_effect(tempSkillData, op)
                # target.SkillEffectStatusOperation(
                # op.InfluenceStatus, (op.AddType == "Rate"), op.EffectValue)
                temp = f"{get_text('TM_' + op.InfluenceStatus)}: {get_text('TM_' + op.AddType).format(op.EffectValue)}"
                returnResult.append((battlelog_text_processor({
                    "caster_text": attacker.name,
                    "descript_text": temp,
                    "target_text": target.name,
                }, "passiveBuff",get_text(f"TM_{tempSkillData.SkillID}_Name")), 0, 0))

            case "Utility":
                utilityResult = skill_utility_processor(target, op)
                for result in utilityResult:
                    returnResult.append(result)

            case "Health":
                returnResult.append(target.processRecovery(op,skillData.Name, attacker, target))

            case "EnhanceSkill":
                # 強化指定技能 在角色開一個新字典<BonusId,下個component資料>
                attacker.passive_bar.add_skill_effect(tempSkillData.SkillID, tempSkillData)
                # 掃描此被動技能內所有 EnhanceSkill ops，全部註冊
                for enhance_op in tempSkillData.SkillOperationDataList:
                    if enhance_op.SkillComponentID == "EnhanceSkill":
                        key = enhance_op.Bonus[0]
                        if key not in attacker.enhance_skill_dict:
                            attacker.enhance_skill_dict[key] = []
                        attacker.enhance_skill_dict[key].append(tempSkillData)
                        returnResult.append((battlelog_text_processor({
                            "caster_text": attacker.name,
                            "target_text": get_text(GameData.Instance.SkillDataDic[key].Name),
                            "descript_text": get_text(tempSkillData.Name),
                        }, "enhanceSkill"), 0, 0))
                break

            case "UpgradeSkill":
                # 升級指定技能 在角色開一個新字典<BonusId,下個component資料>
                attacker.passive_bar.add_skill_effect(tempSkillData.SkillID, tempSkillData)
                key = op.Bonus[0]

                if key not in attacker.upgrade_skill_dict:
                    attacker.upgrade_skill_dict[key] = []

                attacker.upgrade_skill_dict[key].append(tempSkillData)
                returnResult.append((battlelog_text_processor({
                    "caster_text": attacker.name,
                    "target_text": get_text(GameData.Instance.SkillDataDic[key].Name),
                    "descript_text": get_text(tempSkillData.Name) ,
                }, "upgradeSkill"), 0, 0))

            case "Charge":
                # 衝鋒/位移 - 模擬器無位置系統，標記成功即可
                returnResult.append((battlelog_text_processor({
                    "caster_text": attacker.name,
                    "descript_text": get_text(tempSkillData.Name),
                }, "charge"), 0, 0))
                success = True

            case "InheritDamage":
                inherit_skill_id = op.Bonus[0]
                inherit_skill = GameData.Instance.SkillDataDic[inherit_skill_id]
                inheritResult = execute_skill_operation(inherit_skill, attacker, target)
                for result in inheritResult:
                    if isinstance(result, list):
                        returnResult.extend(result)
                    else:
                        returnResult.append(result)

            case "EventTrigger":
                # 事件觸發器 - 訂閱事件，條件達成時執行後續的技能組件效果

                # 空值檢查
                event_type = parse_event_trigger(op)
                if event_type is None:
                    break

                # 儲存 EventTrigger組件 後續的技能組件(當事件條件達成後須執行的效果)
                remaining_ops = tempSkillData.SkillOperationDataList[index + 1:]

                trigger_skill = copy.deepcopy(tempSkillData)
                trigger_skill.SkillOperationDataList = remaining_ops

                if event_type not in attacker.temp_dict:
                    attacker.temp_dict[event_type] = []

                # 將後續效果與原始條件儲存進暫存（條件在觸發時才判定）
                attacker.temp_dict[event_type].append((trigger_skill, op))
                break  # 後續 的技能組件效果會由訂閱觸發

            case "DotDamage":
                # 持續傷害 - 使用訂閱事件模式
                base_damage = _calculate_dot_tick_damage(tempSkillData, op, attacker)

                def SubscriptionDot(damage_val, target_ref, op_ref):
                    target_ref.stats["HP"] -= damage_val
                    target_ref.battle_log.append(battlelog_text_processor({
                        "caster_text": target_ref.name,
                        "descript_text": damage_val,
                        "descript_color": "#ab0000",
                    }, "dotDamageTick"))

                tempfunction = lambda d=base_damage, t=target, o=op: SubscriptionDot(d, t, o)
                target.temp_dict[f"dot_{skillData.SkillID}"] = tempfunction
                target.subscription_skill_event += tempfunction
                target.add_debuff_effect(op)
                returnResult.append((battlelog_text_processor({
                    "caster_text": attacker.name,
                    "descript_text": get_text(tempSkillData.Name),
                    "target_text": target.name,
                }, "dotDamageStart", op.EffectDurationTime), 0, 0.5))

            case _:
                returnResult.append(("",0,0))

        execution_history[index] = {
            "componentID": op.SkillComponentID,
            "success": success
        }

    # 檢查是否有 HitReduceSec CD 減少效果 存至暫存字典 待結算
    if hasattr(tempSkillData, 'hit_reduce_sec') and tempSkillData.hit_reduce_sec > 0:
        hit_count = sum(1 for h in execution_history.values() if h["success"])
        cd_reduction = hit_count * tempSkillData.hit_reduce_sec
        attacker.temp_dict[f"cd_reduction_{skillData.SkillID}"] = cd_reduction

    return returnResult

def execute_item_operation(itemData: ItemDataModel, attacker, defender, gui=None) -> Tuple[str, int, float]:
    """
    實現道具效果執行入口
    """
    # 儲存回傳的結果
    returnResult = []
    for op in itemData.ItemEffectDataList:
        match op.ItemComponentID:
            case "Restoration":
                returnResult.append(
                    defender.processRecovery(op,itemData.Name, attacker, defender))
            case "Utility":
                pass
            case "Continuance":
                attacker.add_item_buff_effect(op, itemData)
                temp = f"{get_text('TM_'+op.InfluenceStatus)}: {get_text('TM_' + op.AddType).format(op.EffectValue)}"
                returnResult.append((battlelog_text_processor({
                    "caster_text": attacker.name,
                    "descript_text": temp,
                    "target_text": defender.name,
                }, "continuanceBuff", op.EffectDurationTime), 5, 0.5))
    return returnResult

def status_skill_effect_start(op: SkillOperationData, attacker, defender) -> Tuple[str, int, float]:
    """
    狀態效果啟動方法
    """

    match op.SkillComponentID:
        case "CrowdControl":
            defender.CrowdControlCalculator(op, 1)
            defender.add_debuff_effect(op)
            # 觸發 InCrowdControl 事件（被控制時）
            defender.battle_log.extend(defender.fire_event_trigger("InCrowdControl", attacker))
            return (battlelog_text_processor({
                "caster_text": attacker.name,
                "descript_text": get_text("TM_" + op.InfluenceStatus + "_Name"),
                "target_text": defender.name,
            }, "crowdControlStart", op.EffectDurationTime), 0, 0)
        case "Debuff":
            debuff_effect_processor(op,attacker,defender)
            defender.add_debuff_effect(op)
            return (battlelog_text_processor({
                "caster_text": attacker.name,
                "descript_text": get_text("TM_" + op.InfluenceStatus + "_Name"),
                "target_text": defender.name,
            }, "debuffStart", op.EffectDurationTime), 0, 0)

def status_skill_effect_end(op: SkillOperationData, character) -> Tuple[str, int, float]:
    """
    狀態效果結束方法
    """
    match op.SkillComponentID:
        case "CrowdControl":
            character.CrowdControlCalculator(op, -1)
            return (battlelog_text_processor({
                "caster_text": character.name,
                "descript_text": get_text("TM_" + op.InfluenceStatus + "_Name"),
            }, "crowdControlEnd", op.EffectDurationTime), 0, 0)
        case "Debuff":
            debuff_effect_processor(op,character,character,True)
            return (battlelog_text_processor({
                "caster_text": character.name,
                "descript_text": get_text("TM_" + op.InfluenceStatus + "_Name"),
            }, "debuffEnd", op.EffectDurationTime), 0, 0)
        case "DotDamage":
            dot_key = f"dot_{op.SkillID}"
            if dot_key in character.temp_dict:
                character.subscription_skill_event -= character.temp_dict[dot_key]
                del character.temp_dict[dot_key]
            return (battlelog_text_processor({
                "caster_text": character.name,
                "descript_text": get_text("TM_Dot_Name"),
            }, "dotDamageEnd"), 0, 0)

def debuff_effect_processor(op: SkillOperationData, attacker, defender,unsubscription = False):
    """
    負面效果處理
    """
    match op.InfluenceStatus:
        case "SpeedSlow":
           defender.SkillEffectStatusOperation(op.InfluenceStatus, (op.AddType == "Rate"), op.EffectValue)
        case "Bleeding":
            def SubscriptionBleeding(op, defender):
                # (每秒扣除EffectValue血量持續EffectDurationTime秒)
                defender.stats["HP"] -= op.EffectValue
                defender.battle_log.append(battlelog_text_processor({
                    "caster_text": defender.name,
                    "descript_text": op.EffectValue,
                    "descript_color": "#ab0000",
                }, op.InfluenceStatus))
            if(unsubscription is False):
                tempfunction = lambda: SubscriptionBleeding(op, defender)
                defender.temp_dict[op.SkillID] = tempfunction
                defender.subscription_skill_event += defender.temp_dict[op.SkillID]
                SubscriptionBleeding(op,defender)
            else:
                defender.subscription_skill_event -=  defender.temp_dict[op.SkillID]
        case "ReduceTargetDmg":
            value = op.EffectValue if unsubscription else -op.EffectValue
            defender.SkillEffectStatusOperation("ReduceTargetDmg", (op.AddType == "Rate"), value)
        case "ArmorBreak":
            value = op.EffectValue if unsubscription else -op.EffectValue
            defender.SkillEffectStatusOperation("DEF", (op.AddType == "Rate"), value)

def skill_condition_process(caster, op: SkillOperationData) -> bool:
    """
    技能條件檢查(Operation版)
    """
    if (not any(op.ConditionOR) and not any(op.ConditionAND)):
        return True
    or_list = []
    if (any(op.ConditionOR)):
        for or_data in op.ConditionOR:
            temp_or_data = or_data.split('_')
            temp_or_data_second = '_'.join(temp_or_data[1:])
            or_list.append(skill_condition_check(
                caster, temp_or_data[0], temp_or_data_second))
    else:
        or_list.append(True)
    and_list = []
    if (any(op.ConditionAND)):
        for and_data in op.ConditionAND:
            temp_and_data = and_data.split('_')
            temp_and_data_second = '_'.join(temp_and_data[1:])
            and_list.append(skill_condition_check(
                caster, temp_and_data[0], temp_and_data_second))
    else:
        and_list.append(True)

    return any(or_list) and all(and_list)

def skill_all_condition_process(caster, skillData: SkillData) -> bool:
    """
    技能條件檢查(Skill版)
    """
    result = []
    for op in skillData.SkillOperationDataList:
        result.append(skill_condition_process(caster, op))
    return all(result)

def skill_condition_check(caster, key: str, value) -> bool:
    """
    技能效果條件檢查
    """
    match(key):
        case "EquipWeapon":
            if (caster.equipped_weapon is None):
                return False
            return any(x[0].TypeID == str(value)
                       for x in caster.equipped_weapon)
        case "EquipLeft":
            if (caster.equipped_weapon is None):
                return False
            return any(x[0].TypeID == str(value)
                       for x in caster.equipped_weapon)
        # 全副武裝
        case "EquipArmor":
            if (caster.equipped_armor is None):
                return False
            return (len(caster.equipped_armor) == 5 and
                    all(x[0].TypeID == str(value)
                    for x in caster.equipped_armor))
        case "Equip":
            # 通用裝備檢查 - 武器或防具中有此類型即可
            weapon_match = False
            armor_match = False
            if caster.equipped_weapon is not None:
                weapon_match = any(x[0].TypeID == str(value) for x in caster.equipped_weapon)
            if caster.equipped_armor is not None:
                armor_match = any(x[0].TypeID == str(value) for x in caster.equipped_armor)
            return weapon_match or armor_match
        case "Block":
            # Block 條件由 InheritDamage 的 _parse_block_probability 處理
            # 這裡回傳 True 讓條件檢查通過，實際機率在 BlockCalculator 判定
            return True
        case "InCombatStatus":
            # 模擬總是在戰鬥中 所以一律回傳true
            return True
        case "InCrowdControl":
            # 事件觸發條件 - 註冊階段放行，實際判定在 event_condition_check
            return True
        case "HpLess":
            return caster.stats["HP"] < (float(value)*caster.stats["MaxHP"])
        #尋找作用中的疊層效果
        case "Stack":
            return 0 < caster.passive_bar.get_effect_stack(value)

def skill_additive_effect_event(skillData: SkillData, op, target):
    """
    疊加型技能效果 事件呼叫
    """
    if (skill_condition_process(target, op)):
        target.add_skill_addtive_effect(skillData, op, 1)

def skill_utility_processor(caster,op):
    """
    功能型技能 處理
    """

    result = []

    match op.InfluenceStatus:
        #清除指定技能所有疊層
        case "RemoveAdditive":
            get_stack = caster.passive_bar.get_effect_stack(str(op.Bonus[0]))
            target_skill = GameData.Instance.SkillDataDic[str(op.Bonus[0])]
            #暫存消耗的層數
            caster.temp_dict[str(op.Bonus[0])] = get_stack
            #重製目標技能疊層
            caster.set_skill_addtive_effect(target_skill,op,0)
            result.append((battlelog_text_processor({
                "caster_text": caster.name,
                "descript_text": get_text(target_skill.Name),
            }, "removeAdditive",get_stack), 0, 0))

        #清除控制技能
        case "RemoveAllCC":
            debuffskills = list(caster.debuff_skill.keys())
            for debuff_id in debuffskills:
                op, debuffDuration = caster.debuff_skill[debuff_id]
                result.append(status_skill_effect_end(op, caster))
                caster.debuff_bar.remove_effect(debuff_id)
                del caster.debuff_skill[debuff_id]
            caster.debuff_skill = {}

            result.append((battlelog_text_processor({
                "caster_text": caster.name,
                "descript_text": get_text(f"TM_{op.SkillID}_Name"),
            }, "removeAllCC"), 0, 0))
    return result

def skill_continuancebuff_bonus_processor(caster,op):
    """持續型buff技能的Bonus資料處理"""
    temp_bonus_data = op.Bonus
    match temp_bonus_data[0]:
        case "Stack":
            key = temp_bonus_data[1]
            stack = caster.temp_dict.get(key, 0)
            caster.temp_dict.pop(temp_bonus_data[1], None)
            return int(stack)
        case _:
            return temp_bonus_data[0]

def upgrade_skill_processor(upgradeSkillData, skillData: SkillData)-> SkillData:
    """
    升級技能處理
    """

    #暫存 技能資料 並修改
    tempSkillData = copy.deepcopy(skillData)
    tempSkillData.Damage = upgradeSkillData.Damage
    tempSkillData.CastMage = upgradeSkillData.CastMage
    tempSkillData.CD = upgradeSkillData.CD
    tempSkillData.Distance = upgradeSkillData.Distance
    tempSkillData.Width = upgradeSkillData.Width
    tempSkillData.Height = upgradeSkillData.Height
    tempSkillData.CircleDistance = upgradeSkillData.CircleDistance
    tempSkillData.Name = upgradeSkillData.Name
    tempSkillData.Intro = upgradeSkillData.Intro

    for tempOp in upgradeSkillData.SkillOperationDataList:
        if(tempOp.SkillComponentID == "UpgradeSkill"):
            upgradeSkillId = tempOp.Bonus[0]
            upgradeComponentId = tempOp.Bonus[1]
            upgradeComponentIndex = tempOp.Bonus[2]
            sameComponentIds = [s for s in tempSkillData.SkillOperationDataList if s.SkillComponentID == upgradeComponentId]
            targetSkillOpData = sameComponentIds[int(upgradeComponentIndex)]
            #替換Op資料
            targetSkillOpData.DependCondition = tempOp.DependCondition
            targetSkillOpData.EffectValue = tempOp.EffectValue
            targetSkillOpData.InfluenceStatus = tempOp.InfluenceStatus
            targetSkillOpData.AddType = tempOp.AddType
            targetSkillOpData.ConditionOR = tempOp.ConditionOR
            targetSkillOpData.ConditionAND = tempOp.ConditionAND
            targetSkillOpData.EffectDurationTime = tempOp.EffectDurationTime
            targetSkillOpData.EffectRecive = tempOp.EffectRecive
            targetSkillOpData.TargetCount = tempOp.TargetCount

    return tempSkillData

def enhance_skill_processor(enhanceSkillDataList, skillData: SkillData):
    """
    強化技能處理 - 解析被動技能中 EnhanceSkill 之後的 PassiveBuff 等 ops
    """
    tempSkillData = copy.deepcopy(skillData)

    for enhanceSkill in enhanceSkillDataList:
        ops = enhanceSkill.SkillOperationDataList
        processing_for_this_skill = False

        for op in ops:
            if op.SkillComponentID == "EnhanceSkill":
                processing_for_this_skill = (op.Bonus[0] == skillData.SkillID)
            elif processing_for_this_skill:
                if op.SkillComponentID == "PassiveBuff":
                    apply_enhance_passivebuff(tempSkillData, op)
                else:
                    # 其他 ops (如 Charge) 直接附加到強化技能的操作列表
                    tempSkillData.SkillOperationDataList.append(op)

    return tempSkillData

def apply_enhance_passivebuff(skillData: SkillData, op):
    """處理 EnhanceSkill 附帶的 PassiveBuff 特殊參數"""
    match op.InfluenceStatus:
        case "EffectValue":
            for skill_op in skillData.SkillOperationDataList:
                if skill_op.SkillComponentID in ["Damage", "MultipleDamage", "InheritDamage"]:
                    skill_op.EffectValue += op.EffectValue
        case "HitReduceSec":
            if not hasattr(skillData, 'hit_reduce_sec'):
                skillData.hit_reduce_sec = 0
            skillData.hit_reduce_sec += op.EffectValue
        case "Distance":
            skillData.Distance += op.EffectValue
        case _:
            skillData.SkillOperationDataList.append(op)

def parse_event_trigger(op):
    """從 EventTrigger 的 Condition 解析事件類型

    只提取前綴作為事件類型，條件判斷延遲到觸發時執行
    """
    for cond_list in [op.ConditionOR or [], op.ConditionAND or []]:
        for cond in cond_list:
            parts = cond.split('_')
            event_type = parts[0]
            return event_type
    return None

def event_trigger_condition_process(op, caster) -> bool:
    """事件觸發條件檢查 - 模式同 skill_condition_process

    在事件觸發時呼叫，依照 ConditionOR / ConditionAND 判定是否執行
    """
    if (not any(op.ConditionOR) and not any(op.ConditionAND)):
        return True

    #OR條件檢查
    or_list = []
    if any(op.ConditionOR):
        for or_data in op.ConditionOR:
            parts = or_data.split('_')
            key = parts[0]
            value = '_'.join(parts[1:])
            or_list.append(event_condition_check(key, value, caster))
    else:
        or_list.append(True)

    # AND條件檢查
    and_list = []
    if any(op.ConditionAND):
        for and_data in op.ConditionAND:
            parts = and_data.split('_')
            key = parts[0]
            value = '_'.join(parts[1:])
            and_list.append(event_condition_check(key, value, caster))
    else:
        and_list.append(True)

    return any(or_list) and all(and_list)

def event_condition_check(key: str, value: str, caster) -> bool:
    """事件條件檢查 - 模式同 skill_condition_check

    依照前綴拆出後綴門檻，直接跑執行再回傳結果
    """
    match key:
        case "Block":
            # 後綴為觸發機率，跑隨機判定
            return random.random() < float(value)
        case "InCombatStatus":
            # 模擬器始終在戰鬥中
            return True
        case "InCrowdControl":
            # 事件觸發時必然被控制中
            return True
        case "HpLess":
            return caster.stats["HP"] < (float(value) * caster.stats["MaxHP"])
        case _:
            return True

def _calculate_dot_tick_damage(skillData: SkillData, op, attacker) -> int:
    """計算 DotDamage 每秒傷害值"""
    base_atk = attacker.stats.get("MeleeATK", 0)
    effect_value = op.EffectValue if op.EffectValue > 0 else skillData.Damage
    return round(base_atk * effect_value)
