"""
Minecraft Resource Pack Upgrade Action

Inspired by:
RiceChen_
https://github.com/BrilliantTeam/Minecraft-ResourcePack-Migrator/blob/main/converter.py

"""

import json
import os
import sys
from typing import Dict

def convert_json_format(input_json: Dict) -> Dict:
    """Convert JSON format with improved bow/crossbow handling"""
    base_texture = input_json.get("textures", {}).get("layer0", "")
    if not base_texture:
        return input_json
    
    # Normalize base texture path
    if base_texture == "item/crossbow_standby":
        base_texture = "item/crossbow"
    if not base_texture.startswith("minecraft:") and ":" not in base_texture:
        base_texture = f"minecraft:item/{base_texture.replace('item/', '')}"

    # Create base format
    fallback_model = {"type": "model", "model": base_texture}
    
    # Add dye tint for leather armor items
    leather_items = ["minecraft:item/leather_boots", "minecraft:item/leather_leggings", 
                    "minecraft:item/leather_chestplate", "minecraft:item/leather_helmet"]
    
    is_leather_item = base_texture in leather_items

    if is_leather_item:
        fallback_model["tints"] = [{"type": "minecraft:dye", "default": -6265536}]
    
    new_format = {
        "model": {
            "type": "range_dispatch",
            "property": "custom_model_data",
            "fallback": fallback_model,
            "entries": []
        }
    }

    if "display" in input_json:
        new_format["display"] = input_json["display"]

    if "overrides" not in input_json:
        return new_format

    is_bow = "bow" in base_texture and "crossbow" not in base_texture
    is_crossbow = "crossbow" in base_texture

    if is_bow or is_crossbow:
        cmd_groups = {}
        for override in input_json["overrides"]:
            if "predicate" not in override or "model" not in override:
                continue

            predicate = override["predicate"]
            cmd = predicate.get("custom_model_data")
            if cmd is None:
                continue

            if cmd not in cmd_groups:
                cmd_groups[cmd] = {"base": None, "pulling_states": [], "arrow": None, "firework": None}

            if is_crossbow:
                if "pulling" in predicate:
                    cmd_groups[cmd]["pulling_states"].append({
                        "pull": predicate.get("pull", 0.0),
                        "model": override["model"]
                    })
                elif "charged" in predicate:
                    if predicate.get("firework", 0):
                        cmd_groups[cmd]["firework"] = override["model"]
                    else:
                        cmd_groups[cmd]["arrow"] = override["model"]
                else:
                    cmd_groups[cmd]["base"] = override["model"]
            else:  # Bow
                if "pulling" in predicate:
                    cmd_groups[cmd]["pulling_states"].append({
                        "pull": predicate.get("pull", 0.0),
                        "model": override["model"]
                    })
                else:
                    cmd_groups[cmd]["base"] = override["model"]

        for cmd, group in cmd_groups.items():
            pulling_states = sorted(group["pulling_states"], key=lambda x: x["pull"])
            base_model = group["base"] or (pulling_states[0]["model"] if pulling_states else base_texture)
            
            entry = {
                "threshold": int(cmd),
                "model": {
                    "type": "minecraft:condition",
                    "property": "minecraft:using_item",
                    "on_false": {
                        "type": "minecraft:model",
                        "model": base_model
                    } if not is_crossbow else {
                        "type": "minecraft:select",
                        "property": "minecraft:charge_type",
                        "fallback": {"type": "minecraft:model", "model": base_model},
                        "cases": []
                    },
                    "on_true": {
                        "type": "minecraft:range_dispatch",
                        "property": "minecraft:use_duration" if is_bow else "minecraft:crossbow/pull",
                        "scale": 0.05 if is_bow else None,
                        "fallback": {"type": "minecraft:model", "model": base_model},
                        "entries": []
                    }
                }
            }

            if is_crossbow and group["arrow"]:
                entry["model"]["on_false"]["cases"].extend([
                    {"model": {"type": "minecraft:model", "model": group["arrow"]}, "when": "arrow"},
                    {"model": {"type": "minecraft:model", "model": group["firework"]}, "when": "rocket"}
                ] if group["firework"] else [
                    {"model": {"type": "minecraft:model", "model": group["arrow"]}, "when": "arrow"}
                ])

            for state in pulling_states:
                if state["model"] != base_model:
                    entry["model"]["on_true"]["entries"].append({
                        "threshold": state["pull"],
                        "model": {"type": "minecraft:model", "model": state["model"]}
                    })

            new_format["model"]["entries"].append(entry)
    else:
        # Handle normal items and damage-based items
        for override in input_json["overrides"]:
            if "predicate" not in override:
                continue

            predicate = override["predicate"]
            if "custom_model_data" in predicate:
                cmd = int(predicate["custom_model_data"])
            elif "damage" in predicate:
                new_format["model"]["property"] = 'damage'
                cmd = predicate["damage"]
            else:
                continue

            entry_model = {"type": "model", "model": override["model"]}
            
            # Add tints to leather armor models in overrides
            if is_leather_item:
                entry_model["tints"] = [{"type": "minecraft:dye", "default": -6265536}]
                
            new_format["model"]["entries"].append({
                "threshold": cmd,
                "model": entry_model
            })

    return new_format

def process_directory(input_dir: str) -> bool:
    """Process directory and convert JSON files"""
    try:
        json_files = []
        models_item_dir = os.path.join(input_dir, "assets", "minecraft", "models", "item")
        out_dir = os.path.join(input_dir, "assets", "minecraft", "items")
        os.makedirs(out_dir, exist_ok=True)
        
        for root, _, files in os.walk(models_item_dir):
            json_files.extend(os.path.join(root, f) for f in files if f.lower().endswith('.json'))

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)

                if "overrides" in json_data and any(
                    "custom_model_data" in o.get("predicate", {}) or 
                    "damage" in o.get("predicate", {})
                    for o in json_data.get("overrides", [])):
                    
                    converted_data = convert_json_format(json_data)
                    
                    out_file = os.path.join(out_dir, os.path.basename(json_file))


                    with open(out_file, 'w', encoding='utf-8') as f:
                        json.dump(converted_data, f, indent=2)
                    
                    os.remove(json_file)
                    
                    print(f"Converted: {json_file}")

            except Exception as e:
                print(f"Error processing {json_file}: {e}")
                continue

        return True

    except Exception as e:
        print(f"Error processing directory: {e}")
        return False

def main():
    # Get inputs from GitHub Actions environment variables
    input_dir = os.environ.get('INPUT_INPUT_PATH') or sys.argv[1]

    print(f"Input directory: {input_dir}")
    
    if not input_dir:
        print("::error::Input paths are required")
        sys.exit(1)

    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_dir}' not found")
        return False

    return process_directory(input_dir)

if __name__ == '__main__':
    success = main()

    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'success={str(success).lower()}\n')

    sys.exit(0 if success else 1)