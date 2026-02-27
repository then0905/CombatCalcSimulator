# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Python-based battle simulation tool** for the MMORPG "HolyLandOnline" (聖域Online). It simulates combat between players and monsters using game data exported as JSON, and trains AI combat behavior using **PPO (Proximal Policy Optimization)** reinforcement learning. The GUI is built with **tkinter**.

The tool is designed to mirror the game's combat formulas so balance tuning and AI training can happen outside the Unity game client.

## Running the Application

```bash
# Activate venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the simulator (this is the entry point)
python simulator_gui.py
```

Python 3.13 is used. The project uses a Visual Studio Python project (.pyproj/.sln) but can be run directly.

## CI/CD

On push to `master`, a GitHub Action (`SIMULATION_GITACTION.yml`) builds a standalone EXE via PyInstaller and pushes it to the Unity repo (`HLO_new`) at `Assets/Tools/SimulationTool.exe`.

## Architecture

### Data Flow
`JSON files (data/) → GameData singleton → Battle simulation → AI training → PPO model (.pth)`

### Key Modules

- **`simulator_gui.py`** — Entry point. Tkinter GUI (`BattleSimulatorGUI`) for configuring player/enemy, launching battles, and viewing results. Contains all UI widget definitions including HP/MP bars, buff/debuff bars, character overview panels.

- **`game_models.py`** — All game data structures as `@dataclass` classes (skills, monsters, weapons, armor, items, etc.) and the `GameData` singleton that loads everything from `data/*.json` into dictionaries keyed by ID.

- **`battle_simulator.py`** — Core battle engine. Contains:
  - `BattleCharacter`: Represents a combatant with stats split into three layers: `basal` (base), `equip` (equipment), `effect` (buff/debuff). Stats are recalculated by summing all three layers via `_recalculate_stats()`.
  - `BattleSimulator`: Manages the real-time battle loop using `tkinter.after()` timers. `battle_tick()` handles passive timers (cooldowns, buff durations, HP/MP regen). `attack_loop()` drives AI decision-making each turn.

- **`AICombatAction.py`** — PPO reinforcement learning agent (`ai_action` class with `ActorCritic` neural network). Handles state observation, action masking (prevents illegal actions like using skills on cooldown), action selection, reward calculation, and model training. Models saved per job/role in `ppo_models/ppo_{role_id}.pth`.

- **`skill_processor.py`** — `SkillProcessor` (all static methods) executes skill effects by dispatching on `SkillComponentID` (Damage, ContinuanceBuff, CrowdControl, Debuff, PassiveBuff, AdditiveBuff, Utility, Health, EnhanceSkill, UpgradeSkill, etc.). Also handles skill conditions (OR/AND) and dependency chains between skill components.

- **`status_operation.py`** — `StatusValues` dataclass (composed via multiple inheritance from `CharacterStatus_Core`, `CharacterStatus_Secret`, `CharacterStatus_Debuff`, `CharacterStatus_Element`, `MonsterStatus_Core`). `CharacterStatusCalculator` computes final stats from base attributes + race formulas + job bonuses + equipment.

- **`character_status.py`** — Defines the individual status dataclass fragments that compose `StatusValues`.

- **`commonfunction.py`** — Utility class: text lookup from `GameTextDataDic`, resource path resolution (supports PyInstaller `_MEIPASS`), battle log formatting with HTML-like markup (`<color>`, `<size>` tags), image loading, `clamp()`.

- **`commontool.py`** — C#-style `Event` class (supports `+=`/`-=` for subscribe/unsubscribe pattern).

- **`user_config_controller.py` / `user_config_model.py`** — MVC pattern for persisting user configuration to `%APPDATA%/MySimulator/user_config.json`.

### Combat System Design

The combat system uses **real-time tick-based simulation** (0.1s intervals for timers, variable intervals for attack loops). Each combatant has independent attack timers. The damage pipeline is: **Hit check → Block check → Critical check → Damage calculation → Bonus damage → Lifesteal**.

Stats have three layers: `basal` (from level/race/job), `equip` (from gear), `effect` (from buffs/debuffs). When any effect changes, `_recalculate_stats()` re-sums all three layers.

### Data Directory (`data/`)

All game data is in JSON format, exported from the game's data tables. Text content is separated into `*Text.json` files and referenced by `TextID`. Use `CommonFunction.get_text(text_id)` to look up display text.

## Skill System Architecture

### Component Pipeline
Each skill has a `SkillOperationDataList`. `execute_skill_operation()` iterates the list and dispatches each op to `_execute_component()` via `match/case` on `SkillComponentID`. Results are `(log_str, damage, timer)` tuples collected into `returnResult`.

### EventTrigger & Subscription Pattern
`EventTrigger` splits the op list at its position: ops after it become a `trigger_skill` stored in `attacker.temp_dict[event_type]`. The trigger fires later via:
- **`fire_event_trigger(event_type, opponent)`** — for event-driven triggers (Block, InCrowdControl, InCombatStatus). Returns `[log_str, ...]` only; damage/timer values are discarded. Used when results are consumed directly into `battle_log`.
- **`BlockCalculator`** — calls `execute_skill_operation()` directly and bubbles up `(log, damage, timer)` tuples so `ai_choose_result` can use damage for PPO reward and timer for attack timing.

**`RefreshInterval` field** on EventTrigger op: if `> 0`, the trigger is also registered in `temp_dict["_periodic_triggers"]` and re-evaluated every N seconds by `pass_time`. This allows buffs applied by InCombatStatus triggers to persist throughout combat without hardcoding any event type name. The interval is set in JSON data only.

### Condition System
`ConditionOR`/`ConditionAND` on each op are evaluated by `skill_condition_process()`. `DependCondition: "Prev"` means the op only executes if the previous op succeeded. `DependCondition: "All"` requires all prior ops to have succeeded.

### Buff Layers
`buff_skill` (keyed by unique timestamp ID or SkillID) tracks active timed buffs. `pass_time()` decrements durations and reverses all ops in `skillData.SkillOperationDataList` on expiry. `fire_event_trigger` detects active buffs by SkillID prefix and refreshes duration instead of re-applying stats, preventing double-stacking.

## Conventions

- Code comments and UI text are in **Traditional Chinese (繁體中文)**.
- The codebase follows patterns from Unity/C# (e.g., the `Event` class, PascalCase for data model fields, `match/case` for dispatching).
- Battle log messages use Unity-style rich text markup (`<color=#hex>`, `<size=N>`).
- Skill effects are data-driven: the `SkillComponentID` field determines which processing branch runs in `SkillProcessor._execute_component()`.

## Design Principles

**資料驅動、不做客製化程式碼。** 新功能或新職業應設計為通用機制，透過 JSON 資料帶入參數即可運作，不需修改程式碼。

具體原則：
- 不在程式碼中寫死事件名稱、技能 ID、職業名稱等具體資料。任何「只對某個技能/事件有效」的邏輯都應改成「讀取資料欄位來決定行為」。
- 新增技能組件行為時，應擴充 `SkillOperationData` 的欄位（在 `game_models.py`），並在 `_execute_component()` 的對應 case 中讀取，讓 JSON 資料控制行為。
- **反例**：在 `pass_time` 中寫 `if "InCombatStatus" in self.temp_dict` → 改為在 EventTrigger op 設定 `RefreshInterval` 欄位，`pass_time` 只讀取 `_periodic_triggers` 通用結構。
- **正例**：`RefreshInterval: 1.0` 寫在 JSON，程式碼讀值驅動行為；未來任何事件類型的定期重評估只需在 JSON 加這個欄位，無需改程式碼。

**`data/` 目錄下的 JSON 檔案不可直接修改。** 這些檔案由外部 Excel 表格轉換匯入，Claude 不應直接編輯它們。若實作新功能需要新增或修改資料欄位（例如新增 `RefreshInterval`），應向使用者說明需要在 Excel 中補充哪個欄位、填什麼值，由使用者自行處理 Excel → JSON 的匯出流程。
