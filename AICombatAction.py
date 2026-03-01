import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Categorical
import numpy as np
from game_models import GameData
from skill_processor import skill_all_condition_process


# ----------------------------------------
# 1. 定義神經網路 (Actor-Critic 架構)
# ----------------------------------------
class ActorCritic(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(ActorCritic, self).__init__()
        # Actor: 決定動作的機率
        self.actor = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, output_dim)
        )
        # Critic: 評估當前狀態的好壞 (Value)
        self.critic = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, 1)
        )

    def forward(self, state):
        # 這裡分開呼叫，方便 PPO 計算
        action_logits = self.actor(state)
        state_value = self.critic(state)
        return action_logits, state_value

    def evaluate(self, state, action):
        action_logits, state_value = self.forward(state)
        return action_logits, state_value


# ----------------------------------------
# 2. PPO Agent
# ----------------------------------------
class ai_action:
    SAVE_DIR = "ppo_models"

    def __init__(self, role_id: str, battle_character):
        self.role_id = role_id
        self.battle_character = battle_character
        self.skills = battle_character.skills
        self.item = battle_character.items

        # PPO 超參數
        self.gamma = 0.99
        self.eps_clip = 0.2
        self.K_epochs = 4
        self.lr_actor = 0.0003
        self.lr_critic = 0.001

        # Reward 計算用
        self.old_hp = 0
        self.old_mp = 0
        self.old_debuff_count = 0

        # --- 固定的道具清單（所有有效果的道具，不隨每場攜帶而變）---
        self.all_game_items = [
            item for item in GameData.Instance.ItemsDic.values()
            if len(item.ItemEffectDataList) > 0
        ]

        # --- 動作空間映射 ---
        # 維度固定：普攻 + 所有主動技 + 所有可用道具
        self.action_map = ["NORMAL_ATTACK"]
        for s in self.skills:
            if s.Characteristic:  # 只加入主動技
                self.action_map.append(s.SkillID)
        for item in self.all_game_items:
            self.action_map.append(f"USE_ITEM:{item.CodeID}")

        self.n_actions = len(self.action_map)

        # --- 狀態空間維度計算 ---
        # 為了初始化網路，我們先跑一次 get_state 看看維度
        dummy_target = battle_character  # 暫時用自己當假目標測量維度
        dummy_state = self.get_state(battle_character, dummy_target)
        self.state_dim = len(dummy_state)

        # 初始化網路
        self.policy = ActorCritic(self.state_dim, self.n_actions)
        self.optimizer = optim.Adam([
            {'params': self.policy.actor.parameters(), 'lr': self.lr_actor},
            {'params': self.policy.critic.parameters(), 'lr': self.lr_critic}
        ])

        # 記憶體 (用於存儲一場戰鬥的軌跡)
        self.memory_states = []
        self.memory_actions = []
        self.memory_logprobs = []
        self.memory_rewards = []
        self.memory_masks = []  # 記錄哪些動作當時是合法的
        self.memory_is_terminals = []

        os.makedirs(self.SAVE_DIR, exist_ok=True)

        # 讀取舊的模型
        self.model_path = "ppo_battle_model.pth"
        self.load_model()

    # -----------------------------
    # 儲存與讀取 (PyTorch 格式)
    # -----------------------------
    def _save_path(self):
        print(f"路徑: {self.role_id}")
        return os.path.join(self.SAVE_DIR, f"ppo_{self.role_id}.pth")

    def save_model(self):
        torch.save(self.policy.state_dict(), self._save_path())

    def load_model(self):
        path = self._save_path()
        if os.path.exists(path):
            self.policy.load_state_dict(torch.load(path))
            self.policy.eval()  # 設定為評估模式 (雖然訓練時會切回來)

    # -----------------------------
    # 狀態獲取 (維持原邏輯，但確保轉為 list/np array)
    # -----------------------------
    def get_state(self, attacker, target):
        self.old_hp = attacker.stats["HP"]
        self.old_mp = attacker.stats["MP"]
        self.old_debuff_count = len(attacker.debuff_skill)

        current_active_buff = [s for s in attacker.buff_skill or {}]
        current_cooldown_buff = [s for s in attacker.skill_cooldowns or {}]

        mp_ratio = attacker.stats["MP"] / attacker.stats["MaxMP"] if attacker.stats["MaxMP"] > 0 else 0
        hp_ratio = attacker.stats["HP"] / attacker.stats["MaxHP"] if attacker.stats["MaxHP"] > 0 else 0
        target_hp_ratio = target.stats["HP"] / target.stats["MaxHP"] if target.stats["MaxHP"] > 0 else 0

        # 基礎特徵
        state = [
            round(hp_ratio, 2),
            round(mp_ratio, 2),
            round(target_hp_ratio, 2),
            int(attacker.controlled_for_attack > 0),
            int(attacker.controlled_for_skill > 0),
        ]

        filtered_skills = [s for s in self.skills if s.Characteristic is True]

        # Buff 效果特徵
        for s in filtered_skills:
            if s.SkillID in attacker.buff_skill:
                remaining_time = attacker.buff_skill[s.SkillID][1]
                max_time = attacker.buff_skill[s.SkillID][0].SkillOperationDataList[0].EffectDurationTime
                state.append(remaining_time / max_time if max_time > 0 else 0)
            else:
                state.append(0.0)

        # 技能冷卻特徵
        for s in filtered_skills:
            if s.SkillID in attacker.skill_cooldowns:
                remaining_time = attacker.skill_cooldowns[s.SkillID]
                max_time = GameData.Instance.SkillDataDic[s.SkillID].CD
                state.append(remaining_time / max_time if max_time > 0 else 0)
            else:
                state.append(0.0)  # 0 表示冷卻好或無冷卻

        # 道具 Buff 效果特徵（遍歷所有遊戲道具，維度固定）
        for item in self.all_game_items:
            i_id = item.CodeID
            if i_id in attacker.buff_item:
                remaining_time = attacker.buff_item[i_id][1]
                max_time = attacker.buff_item[i_id][0].EffectDurationTime
                state.append(remaining_time / max_time if max_time > 0 else 0)
            else:
                state.append(0.0)

        # 道具冷卻特徵（遍歷所有遊戲道具，維度固定）
        for item in self.all_game_items:
            i_id = item.CodeID
            if i_id in attacker.item_cooldowns:
                remaining_time = attacker.item_cooldowns[i_id]
                max_time = GameData.Instance.ItemsDic[i_id].CD
                state.append(remaining_time / max_time if max_time > 0 else 0)
            else:
                state.append(0.0)


        return np.array(state, dtype=np.float32)

    # -----------------------------
    # Action Masking (核心：判斷哪些動作現在合法)
    # -----------------------------
    def get_action_mask(self, self_char):
        """
        回傳一個布林陣列 (List[bool])，True 代表該 index 的動作合法，False 代表不可用。
        長度等於 self.action_map
        """
        mask = []
        for action_name in self.action_map:
            if action_name == "NORMAL_ATTACK":
                mask.append(True)  # 普攻通常總是合法 (除非被繳械，這裡簡化)
                continue

            # 判斷技能
            is_skill = False
            for s in self.skills:
                if s.SkillID == action_name:
                    is_skill = True
                    # 檢查魔力
                    mp_ok = (self_char.stats["MP"] - s.CastMage) >= 0
                    # 檢查 CD
                    cd_ok = s.SkillID not in self_char.skill_cooldowns
                    # 檢查條件 (SkillProcessor)
                    condition_ok = skill_all_condition_process(self.battle_character, s)
                    # 檢查 Buff 是否正在運行 (避免重複施放同Buff)
                    skill_not_running = not any(k.startswith(s.SkillID) for k in self_char.buff_skill)

                    if mp_ok and cd_ok and condition_ok and skill_not_running:
                        mask.append(True)
                    else:
                        mask.append(False)
                    break

            if is_skill: continue

            # 判斷道具
            if action_name.startswith("USE_ITEM:"):
                item_code = action_name.split(":")[1]
                item_found = False
                for item_data, count in self_char.items:
                    if item_data.CodeID == item_code:
                        item_found = True
                        item_enough = count > 0
                        item_cd_ok = item_data.CodeID not in self_char.item_cooldowns
                        item_buff_not_running = not any(k.startswith(item_data.CodeID) for k in self_char.buff_item)

                        if item_enough and item_cd_ok and item_buff_not_running:
                            mask.append(True)
                        else:
                            mask.append(False)
                        break
                if not item_found:
                    mask.append(False)

        return mask

    # -----------------------------
    # 選擇動作 (PPO 邏輯)
    # -----------------------------
    def choose_action(self, self_char, enemy):
        state = self.get_state(self_char, enemy)
        action_mask = self.get_action_mask(self_char)

        # 轉為 Tensor
        state_tensor = torch.FloatTensor(state).unsqueeze(0)  # shape: [1, state_dim]

        # 取得網路輸出
        with torch.no_grad():
            action_logits, _ = self.policy(state_tensor)

        # === 應用 Mask ===
        # 將不合法的動作 logits 設為負無限大，這樣 Softmax 後機率會變 0
        mask_tensor = torch.tensor(action_mask, dtype=torch.bool)
        action_logits[0][~mask_tensor] = -1e9

        # 計算機率分佈
        dist = Categorical(logits=action_logits)
        action_index = dist.sample()
        action_logprob = dist.log_prob(action_index)

        # 存入暫存記憶體 (Update 時使用)
        self.memory_states.append(state)
        self.memory_actions.append(action_index.item())
        self.memory_logprobs.append(action_logprob.item())
        self.memory_masks.append(action_mask)  # 存 Mask 為了訓練時也能過濾

        # 轉換回實際動作字串
        real_action = self.action_map[action_index.item()]

        return real_action, state

    # -----------------------------
    # 計算 Reward (保留原邏輯，幾乎沒變)
    # -----------------------------
    def calculate_reward(self, damage, target_dead, self_dead):
        reward = 0.0
        reward += damage * 0.1

        hp_ratio = self.battle_character.stats["HP"] / self.battle_character.stats["MaxHP"]
        if self.battle_character.stats["MaxMP"]  <= 0:
            mp_ratio = 0
        else:
            mp_ratio = self.battle_character.stats["MP"] / self.battle_character.stats["MaxMP"]

        hp_change = self.battle_character.stats["HP"] - self.old_hp
        mp_change = self.battle_character.stats["MP"] - self.old_mp

        if hp_change > 0:
            if hp_ratio < 0.3:
                reward += hp_change * 0.5
            elif hp_ratio > 0.9:
                reward -= 5.0
            else:
                reward += hp_change * 0.1

        if mp_change > 0:
            if mp_ratio < 0.3:
                reward += mp_change * 0.5
            elif mp_ratio > 0.9:
                reward -= 5.0
            else:
                reward += mp_change * 0.1

        if self.old_debuff_count > len(self.battle_character.debuff_skill):
            reward += 20.0

        if target_dead: reward += 100.0
        if self_dead: reward -= 50.0

        return reward

    # -----------------------------
    # PPO 更新流程 (取代 update_q)
    # -----------------------------
    def record_result(self, reward, done):
        """
        每回合結束呼叫這個。存 Reward 和 Done 標記。
        如果 Done = True (戰鬥結束)，則觸發 update_ppo 進行學習。
        """
        self.memory_rewards.append(reward)
        self.memory_is_terminals.append(done)

    def update_ppo(self):
        """
        核心訓練函數
        """
        if len(self.memory_states) == 0:
            return

        # 1. 準備數據
        old_states = torch.tensor(np.array(self.memory_states), dtype=torch.float32)
        old_actions = torch.tensor(self.memory_actions, dtype=torch.long)
        old_logprobs = torch.tensor(self.memory_logprobs, dtype=torch.float32)
        old_masks = torch.tensor(np.array(self.memory_masks), dtype=torch.bool)

        # 2. 計算 Monte Carlo Rewards (折現回報)
        rewards = []
        discounted_reward = 0
        # 反向遍歷計算
        for reward, is_terminal in zip(reversed(self.memory_rewards), reversed(self.memory_is_terminals)):
            if is_terminal:
                discounted_reward = 0
            discounted_reward = reward + (self.gamma * discounted_reward)
            rewards.insert(0, discounted_reward)

        rewards = torch.tensor(rewards, dtype=torch.float32)
        # 正規化 Reward (讓訓練更穩定)
        rewards = (rewards - rewards.mean()) / (rewards.std() + 1e-7)

        # 3. PPO 更新迴圈 (K epochs)
        for _ in range(self.K_epochs):
            # 評估舊的 State 和 Action
            logits, state_values = self.policy.evaluate(old_states, old_actions)

            # 這裡必須重新做 Masking，因為 evaluate 會輸出原始 logits
            logits[~old_masks] = -1e9
            dist = Categorical(logits=logits)

            logprobs = dist.log_prob(old_actions)
            dist_entropy = dist.entropy()
            state_values = torch.squeeze(state_values)

            # 計算 Advantage
            ratios = torch.exp(logprobs - old_logprobs.detach())
            advantages = rewards - state_values.detach()

            # PPO Loss function
            surr1 = ratios * advantages
            surr2 = torch.clamp(ratios, 1 - self.eps_clip, 1 + self.eps_clip) * advantages

            # Loss = -min(surr1, surr2) + 0.5*MSE(value) - 0.01*entropy
            loss = -torch.min(surr1, surr2) + 0.5 * nn.MSELoss()(state_values, rewards) - 0.01 * dist_entropy

            # Backpropagation
            self.optimizer.zero_grad()
            loss.mean().backward()
            self.optimizer.step()

        # 4. 清空記憶體，準備下一場戰鬥
        self.clear_memory()
        self.save_model()
        # print("PPO Updated and Model Saved.")

    def clear_memory(self):
        self.memory_states = []
        self.memory_actions = []
        self.memory_logprobs = []
        self.memory_rewards = []
        self.memory_masks = []
        self.memory_is_terminals = []