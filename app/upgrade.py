"""
Minecraft Resource Pack Upgrade Action

Inspired by:
RiceChen_
https://github.com/BrilliantTeam/Minecraft-ResourcePack-Migrator/blob/main/converter.py

"""

import json
import os
import sys
import glob
import shutil
import zipfile
import platform
import urllib.request
from typing import Dict, Set

MINECRAFT_VERSION = "1.21.11"

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
        # Process oversized_in_gui property
        add_oversized_in_gui(input_dir)
        
        # Migrate blockstate textures to blocks/ folder
        modified_blocks = migrate_blockstate_textures(input_dir)

        # Migrate item textures to item/ folder
        modified_items = migrate_item_textures(input_dir)

        # Print list of modified files
        if modified_blocks:
            print("\nModified Block Model Files:")
            for mod_file in modified_blocks:
                print(f"  - {mod_file}")
        if modified_items:
            print("\nModified Item Model Files:")
            for mod_file in modified_items:
                print(f"  - {mod_file}")
        
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

def add_oversized_in_gui(input_dir):
    """Process all .json files in assets\minecraft\items and add oversized_in_gui property where needed."""
    items_dir = os.path.join(input_dir, "assets", "minecraft", "items")
    
    if not os.path.exists(items_dir):
        print(f"Items directory not found: {items_dir}")
        return
    
    json_files = glob.glob(os.path.join(items_dir, "*.json"))
    
    modified_count = 0
    
    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
                # Add oversized_in_gui property if it doesn't already exist
                if 'oversized_in_gui' not in data:
                    data['oversized_in_gui'] = True
                    
                    # Write back to file with proper formatting
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent='\t', ensure_ascii=False)
                    
                    modified_count += 1
                    print(f"Modified: {file_path}")
    
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error processing {file_path}: {e}")
    
    print(f"\nProcessed {len(json_files)} files in items directory, modified {modified_count} files.")

def migrate_blockstate_textures(input_dir: str) -> list:
    """
    Migrate block model textures from outside blocks/ folder to blocks/ folder.
    
    Scans all block model files, checks their textures, and copies textures
    to blocks/ folder while preserving directory structure and updating model references.
    
    Args:
        input_dir: Root directory of the resource pack
        
    Returns:
        list: List of modified model file paths
    """
    modified_models = []
    
    try:
        models_block_dir = os.path.join(input_dir, "assets", "minecraft", "models", "block")
        textures_dir = os.path.join(input_dir, "assets", "minecraft", "textures")
        blocks_texture_dir = os.path.join(textures_dir, "block")
        
        # Create blocks texture directory if it doesn't exist
        os.makedirs(blocks_texture_dir, exist_ok=True)
        
        if not os.path.exists(models_block_dir):
            print(f"Block models directory not found: {models_block_dir}")
            return modified_models  # Return empty list if directory doesn't exist
        
        models_modified = 0
        textures_copied = 0
        
        # Get all block model files recursively
        block_model_files = []
        for root, _, files in os.walk(models_block_dir):
            for file in files:
                if file.lower().endswith('.json'):
                    block_model_files.append(os.path.join(root, file))
        
        for model_path in block_model_files:
            try:
                # Process the model file
                modified, copied = process_block_model(model_path, textures_dir, blocks_texture_dir)
                if modified:
                    models_modified += 1
                    modified_models.append(model_path)
                textures_copied += copied
                    
            except Exception as e:
                print(f"Error processing block model {model_path}: {e}")
                continue
        
        print(f"\nBlock model texture migration complete:")
        print(f"  - Processed {len(block_model_files)} block model files")
        print(f"  - Modified {models_modified} model files")
        print(f"  - Copied {textures_copied} textures to blocks/ folder")
        
        return modified_models
        
    except Exception as e:
        print(f"Error in migrate_blockstate_textures: {e}")
        return modified_models

def extract_model_references(blockstate_data: Dict) -> Set[str]:
    """
    Extract all model references from a blockstate definition.
    
    Args:
        blockstate_data: Parsed blockstate JSON data
        
    Returns:
        Set of model reference strings
    """
    models = set()
    
    # Handle "variants" format
    if "variants" in blockstate_data:
        for variant_key, variant_value in blockstate_data["variants"].items():
            # Variant can be a dict or a list of dicts
            if isinstance(variant_value, dict):
                if "model" in variant_value:
                    models.add(variant_value["model"])
            elif isinstance(variant_value, list):
                for option in variant_value:
                    if isinstance(option, dict) and "model" in option:
                        models.add(option["model"])
    
    # Handle "multipart" format
    if "multipart" in blockstate_data:
        for part in blockstate_data["multipart"]:
            if isinstance(part, dict) and "apply" in part:
                apply_value = part["apply"]
                # Apply can be a dict or a list of dicts
                if isinstance(apply_value, dict):
                    if "model" in apply_value:
                        models.add(apply_value["model"])
                elif isinstance(apply_value, list):
                    for option in apply_value:
                        if isinstance(option, dict) and "model" in option:
                            models.add(option["model"])
    
    return models

def resolve_model_path(models_dir: str, model_ref: str) -> str:
    """
    Resolve a model reference to an absolute file path.
    
    Args:
        models_dir: Base models directory
        model_ref: Model reference (e.g., "minecraft:block/stone" or "block/stone")
        
    Returns:
        Absolute path to model file, or empty string if invalid
    """
    # Remove namespace if present
    if ":" in model_ref:
        model_ref = model_ref.split(":", 1)[1]
    
    # Construct path
    model_path = os.path.join(models_dir, f"{model_ref}.json")
    
    return model_path

def process_block_model(model_path: str, textures_dir: str, blocks_texture_dir: str) -> tuple[bool, int]:
    """
    Process a block model file, copying textures to blocks/ and updating references.
    Preserves directory structure when copying textures.
    
    Args:
        model_path: Path to the model JSON file
        textures_dir: Base textures directory
        blocks_texture_dir: Target blocks texture directory
        
    Returns:
        Tuple of (was_modified, textures_copied_count)
    """
    try:
        with open(model_path, 'r', encoding='utf-8') as f:
            model_data = json.load(f)
        
        if "textures" not in model_data:
            return False, 0
        
        modified = False
        textures_copied = 0
        
        # Process each texture in the model
        for texture_key, texture_value in list(model_data["textures"].items()):
            if not isinstance(texture_value, str):
                continue
            
            # Check if texture is outside blocks/ folder
            # Remove namespace if present
            texture_path = texture_value
            if ":" in texture_path:
                namespace, texture_path = texture_path.split(":", 1)
            else:
                namespace = "minecraft"
            
            # Skip if already in blocks/ or block/ folder
            if texture_path.startswith("block/") or texture_path.startswith("blocks/"):
                continue
            
            # Try to find the texture file
            source_texture_path = find_texture_file(textures_dir, texture_path)
            
            if source_texture_path and os.path.exists(source_texture_path):
                # Preserve directory structure relative to textures_dir
                # Get the relative path from textures_dir to the source texture
                rel_texture_path = os.path.relpath(source_texture_path, textures_dir)
                
                # Strip item/ from the start if present
                if rel_texture_path.replace("\\", "/").startswith("item/"):
                    rel_texture_path = rel_texture_path[5:]

                # Construct target path preserving subdirectories
                target_texture_path = os.path.join(blocks_texture_dir, rel_texture_path)
                
                # Create subdirectories if needed
                target_dir = os.path.dirname(target_texture_path)
                os.makedirs(target_dir, exist_ok=True)
                
                # Copy texture if it doesn't already exist
                if not os.path.exists(target_texture_path):
                    shutil.copy2(source_texture_path, target_texture_path)
                    textures_copied += 1
                    print(f"  Copied texture: {texture_path} -> block/{rel_texture_path}")
                
                # Update model reference - preserve subdirectories in the new path
                # Remove .png extension from rel_texture_path
                rel_path_no_ext = os.path.splitext(rel_texture_path)[0]
                # Convert backslashes to forward slashes for consistency
                rel_path_no_ext = rel_path_no_ext.replace("\\", "/")
                new_texture_ref = f"{namespace}:block/{rel_path_no_ext}"
                model_data["textures"][texture_key] = new_texture_ref
                modified = True
        
        # Write back modified model
        if modified:
            with open(model_path, 'w', encoding='utf-8') as f:
                json.dump(model_data, f, indent=2)
            print(f"  Updated model: {model_path}")
        
        return modified, textures_copied
        
    except Exception as e:
        print(f"Error processing model {model_path}: {e}")
        return False, 0
    
def migrate_item_textures(input_dir: str) -> list:
    # Migrate item model textures where it starts with "block/"
    modified_models = []
    try:
        item_dir = os.path.join(input_dir, "assets", "minecraft", "items")
        textures_dir = os.path.join(input_dir, "assets", "minecraft", "textures")
        items_texture_dir = os.path.join(textures_dir, "item")

        os.makedirs(items_texture_dir, exist_ok=True)
        items_path = glob.glob(os.path.join(item_dir, "*.json"))

        if not items_path:
            print(f"No item model files found in: {item_dir}")
            return modified_models
        
        models_modified = 0
        textures_copied = 0
        processed_models = set()  # Track already processed models

        items_path = glob.glob(os.path.join(item_dir, "*.json"))
        for item_path in items_path:
            print(f"Processing item model: {item_path}")
            try:
                modified_count, copied, modified_model_files = process_item(item_path, textures_dir, items_texture_dir, processed_models)
                models_modified += modified_count
                textures_copied += copied
                
                # Track which model files were modified
                modified_models.extend(modified_model_files)

            except Exception as e:
                print(f"Error processing item model {item_path}: {e}")
                continue

        print(f"\nItem model texture migration complete:")
        print(f"  - Processed {len(items_path)} item files")
        print(f"  - Modified {len(modified_models)} model files")
        print(f"  - Copied {textures_copied} item textures")

        return modified_models
    except Exception as e:
        print(f"Error in migrate_item_textures: {e}")
        return modified_models
    
def extract_model_refs_from_item(item_data: Dict) -> list:
    """
    Extract all model references from an item definition.
    
    Args:
        item_data: Parsed item JSON data
        
    Returns:
        List of model reference strings
    """
    model_refs = []
    
    # Get fallback model
    if isinstance(item_data.get("model"), dict):
        fallback = item_data["model"].get("fallback", {})
        if isinstance(fallback, dict) and "model" in fallback:
            model_refs.append(fallback["model"])
        
        # Get models from entries
        entries = item_data["model"].get("entries", [])
        for entry in entries:
            if isinstance(entry, dict) and "model" in entry:
                entry_model = entry["model"]
                if isinstance(entry_model, dict) and "model" in entry_model:
                    model_refs.append(entry_model["model"])
    
    return model_refs

def copy_block_model_to_item(model_path_rel: str, namespace: str, base_assets_dir: str) -> tuple[str, str, str]:
    """
    Copy a block model to the item models directory.
    
    Args:
        model_path_rel: Relative model path (e.g., "block/stone")
        namespace: Namespace for the model
        base_assets_dir: Base assets directory
        
    Returns:
        Tuple of (item_model_path, original_ref, new_ref)
    """
    item_model_rel = model_path_rel.replace("block/", "item/", 1)
    item_model_path = os.path.join(base_assets_dir, namespace, "models", f"{item_model_rel}.json")
    block_model_path = os.path.join(base_assets_dir, namespace, "models", f"{model_path_rel}.json")
    
    item_model_dir = os.path.dirname(item_model_path)
    os.makedirs(item_model_dir, exist_ok=True)
    
    # Copy the block model to item model if it doesn't exist
    if not os.path.exists(item_model_path):
        shutil.copy2(block_model_path, item_model_path)
        print(f"  Copied block model to item model: {model_path_rel} -> {item_model_rel}")
    
    # Create reference mappings
    original_ref = f"{namespace}:{model_path_rel}" if namespace != "minecraft" else model_path_rel
    new_ref = f"{namespace}:{item_model_rel}" if namespace != "minecraft" else item_model_rel
    
    return item_model_path, original_ref, new_ref

def collect_model_parent_chain(model_path: str, base_assets_dir: str, processed_models: Set[str], block_to_item_mappings: Dict[str, str]) -> list:
    """
    Collect all models in the parent chain of a given model.
    
    Args:
        model_path: Path to the starting model file
        base_assets_dir: Base assets directory
        processed_models: Set of already processed model paths
        block_to_item_mappings: Dictionary to track block->item model mappings
        
    Returns:
        List of model paths to process
    """
    models_to_process = []
    current_model_path = model_path
    visited = set()
    
    while current_model_path and current_model_path not in visited:
        if not os.path.exists(current_model_path):
            break
        
        visited.add(current_model_path)
        # Only add to process list if not already processed
        if current_model_path not in processed_models:
            models_to_process.append(current_model_path)
        
        # Check for parent
        with open(current_model_path, 'r', encoding='utf-8') as f:
            current_data = json.load(f)
        
        if "parent" not in current_data:
            break
        
        parent_ref = current_data["parent"]
        # Parse namespace and path from parent reference
        if ":" in parent_ref:
            parent_namespace, parent_path_rel = parent_ref.split(":", 1)
        else:
            parent_namespace = "minecraft"
            parent_path_rel = parent_ref
        
        # Check if parent is a block model that needs to be copied
        if parent_path_rel.startswith("block/"):
            parent_item_rel = parent_path_rel.replace("block/", "item/", 1)
            parent_item_path = os.path.join(base_assets_dir, parent_namespace, "models", f"{parent_item_rel}.json")
            parent_block_path = os.path.join(base_assets_dir, parent_namespace, "models", f"{parent_path_rel}.json")
            
            # Copy parent block model to item if it doesn't exist
            if os.path.exists(parent_block_path):
                parent_item_dir = os.path.dirname(parent_item_path)
                os.makedirs(parent_item_dir, exist_ok=True)
                
                if not os.path.exists(parent_item_path):
                    shutil.copy2(parent_block_path, parent_item_path)
                    print(f"  Copied parent block model to item model: {parent_path_rel} -> {parent_item_rel}")
                
                # Track the mapping
                original_parent_ref = f"{parent_namespace}:{parent_path_rel}" if parent_namespace != "minecraft" else parent_path_rel
                new_parent_ref = f"{parent_namespace}:{parent_item_rel}" if parent_namespace != "minecraft" else parent_item_rel
                block_to_item_mappings[original_parent_ref] = new_parent_ref
                
                # Update current model's parent reference
                current_data["parent"] = new_parent_ref
                with open(current_model_path, 'w', encoding='utf-8') as f:
                    json.dump(current_data, f, indent=2)
                print(f"    Updated parent reference in {current_model_path}")
                
                current_model_path = parent_item_path
            else:
                current_model_path = os.path.join(base_assets_dir, parent_namespace, "models", f"{parent_path_rel}.json")
        else:
            current_model_path = os.path.join(base_assets_dir, parent_namespace, "models", f"{parent_path_rel}.json")
    
    return models_to_process

def download_client_jar(version: str, output_dir: str) -> str:
    """Download the Minecraft client JAR for a specific version."""
    print(f"Downloading Minecraft {version} client JAR...")
    
    manifest_url = "https://piston-meta.mojang.com/mc/game/version_manifest.json"
    
    try:
        # Fetch version manifest
        with urllib.request.urlopen(manifest_url) as response:
            manifest = json.loads(response.read().decode('utf-8'))
        
        # Find version url
        version_url = None
        for v in manifest["versions"]:
            if v["id"] == version:
                version_url = v["url"]
                break
        
        if not version_url:
            print(f"Version {version} not found in manifest")
            return ""
            
        # Fetch version details
        with urllib.request.urlopen(version_url) as response:
            version_data = json.loads(response.read().decode('utf-8'))
            
        client_jar_url = version_data["downloads"]["client"]["url"]
        
        # Download jar
        output_path = os.path.join(output_dir, f"{version}.jar")
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"Downloading from {client_jar_url} to {output_path}")
        with urllib.request.urlopen(client_jar_url) as response, open(output_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
            
        print("Download complete")
        return output_path
        
    except Exception as e:
        print(f"Error downloading Minecraft JAR: {e}")
        return ""

def get_minecraft_jar_path() -> str:
    """Try to locate the Minecraft client JAR file."""
    # Check environment variable first
    env_path = os.environ.get('MINECRAFT_JAR_PATH')
    if env_path and os.path.exists(env_path):
        return env_path
        
    # Check local cache
    cache_dir = "cache"
    cached_jar = os.path.join(cache_dir, f"{MINECRAFT_VERSION}.jar")
    if os.path.exists(cached_jar):
        return cached_jar
        
    # Download if not found
    return download_client_jar(MINECRAFT_VERSION, cache_dir)

def extract_texture_from_jar(jar_path: str, texture_path: str, output_path: str) -> bool:
    """Extract a texture file from the Minecraft JAR."""
    try:
        # Texture path in jar is typically assets/minecraft/textures/...
        # texture_path input is like "block/stone"
        
        if ":" in texture_path:
            namespace, path = texture_path.split(":", 1)
            if namespace != "minecraft":
                return False
        else:
            path = texture_path
            
        jar_entry = f"assets/minecraft/textures/{path}.png"
        
        with zipfile.ZipFile(jar_path, 'r') as jar:
            try:
                # Check if file exists in jar
                jar.getinfo(jar_entry)
                
                # Create output directory
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Extract
                with jar.open(jar_entry) as source, open(output_path, 'wb') as target:
                    shutil.copyfileobj(source, target)
                return True
            except KeyError:
                return False
                
    except Exception as e:
        print(f"Error extracting from JAR: {e}")
        return False

def process_model_textures(model_data: Dict, textures_dir: str, items_texture_dir: str, block_to_item_mappings: Dict[str, str]) -> tuple[bool, int]:
    """
    Process textures in a model, migrating block/ textures to item/ folder.
    
    Args:
        model_data: Parsed model JSON data
        textures_dir: Base textures directory
        items_texture_dir: Target items texture directory
        block_to_item_mappings: Dictionary of block->item model mappings
        
    Returns:
        Tuple of (was_modified, textures_copied_count)
    """
    model_modified = False
    textures_copied = 0
    
    # Update parent reference if it's a block model
    if "parent" in model_data:
        parent_ref = model_data["parent"]
        # Normalize the parent reference for matching
        normalized_parent = parent_ref
        
        # Check if this parent was remapped
        if normalized_parent in block_to_item_mappings:
            model_data["parent"] = block_to_item_mappings[normalized_parent]
            model_modified = True
            print(f"    Updated parent reference: {parent_ref} -> {model_data['parent']}")
    
    # Check each texture in the model
    if "textures" in model_data:
        for texture_key, texture_value in list(model_data["textures"].items()):
            if not isinstance(texture_value, str):
                continue
            
            # Parse texture reference
            texture_path = texture_value
            if ":" in texture_path:
                tex_namespace, texture_path = texture_path.split(":", 1)
            else:
                tex_namespace = "minecraft"
            
            # Check if texture starts with "block/"
            if not texture_path.startswith("block/"):
                continue
            
            # Remove "block/" prefix to get the relative path
            rel_path = texture_path[6:]  # Remove "block/"
            
            # Find the source texture file
            source_texture_path = find_texture_file(textures_dir, texture_path)
            
            # Copy texture file if it exists in the resource pack
            if source_texture_path and os.path.exists(source_texture_path):
                # Construct target path in items folder, preserving structure
                target_texture_path = os.path.join(items_texture_dir, rel_path + ".png")
                
                # Create subdirectories if needed
                target_dir = os.path.dirname(target_texture_path)
                os.makedirs(target_dir, exist_ok=True)
                
                # Copy texture if it doesn't already exist
                if not os.path.exists(target_texture_path):
                    shutil.copy2(source_texture_path, target_texture_path)
                    textures_copied += 1
                    print(f"    Copied texture: {texture_path} -> item/{rel_path}")
            else:
                # Try to extract from JAR if it's a block texture
                jar_path = get_minecraft_jar_path()
                if jar_path:
                    # Construct target path in items folder
                    target_texture_path = os.path.join(items_texture_dir, rel_path + ".png")
                    
                    if not os.path.exists(target_texture_path):
                        if extract_texture_from_jar(jar_path, texture_path, target_texture_path):
                            textures_copied += 1
                            print(f"    Extracted texture from JAR: {texture_path} -> item/{rel_path}")
            
            # Update model reference to point to item/ folder (even if texture wasn't copied)
            # This handles vanilla textures and textures from other resource pack layers
            new_texture_ref = f"{tex_namespace}:item/{rel_path}"
            model_data["textures"][texture_key] = new_texture_ref
            model_modified = True
    
    return model_modified, textures_copied

def update_item_references(item_data: Dict, block_to_item_mappings: Dict[str, str]) -> bool:
    """
    Update item file references with block->item model mappings.
    
    Args:
        item_data: Parsed item JSON data
        block_to_item_mappings: Dictionary of block->item model mappings
        
    Returns:
        True if item was modified, False otherwise
    """
    item_data_modified = False
    
    if isinstance(item_data.get("model"), dict):
        # Update fallback model
        fallback = item_data["model"].get("fallback", {})
        if isinstance(fallback, dict) and "model" in fallback:
            original_model = fallback["model"]
            normalized_model = original_model
            if normalized_model in block_to_item_mappings:
                fallback["model"] = block_to_item_mappings[normalized_model]
                item_data_modified = True
                print(f"  Updated item fallback reference: {original_model} -> {fallback['model']}")
        
        # Update models in entries
        entries = item_data["model"].get("entries", [])
        for entry in entries:
            if isinstance(entry, dict) and "model" in entry:
                entry_model = entry["model"]
                if isinstance(entry_model, dict) and "model" in entry_model:
                    original_model = entry_model["model"]
                    normalized_model = original_model
                    if normalized_model in block_to_item_mappings:
                        entry_model["model"] = block_to_item_mappings[normalized_model]
                        item_data_modified = True
                        print(f"  Updated item entry reference: {original_model} -> {entry_model['model']}")
    
    return item_data_modified

def process_item(item_path: str, textures_dir: str, items_texture_dir: str, processed_models: Set[str]) -> tuple[int, int, list]:
    """
    Process an item file and migrate any block/ textures referenced in its models.
    
    Args:
        item_path: Path to the item JSON file
        textures_dir: Base textures directory
        items_texture_dir: Target items texture directory
        processed_models: Set of already processed model paths to avoid duplicate processing
        
    Returns:
        Tuple of (models_modified_count, textures_copied, list_of_modified_model_files)
    """
    try:
        with open(item_path, 'r', encoding='utf-8') as f:
            item_data = json.load(f)
        
        if "model" not in item_data:
            return 0, 0, []
        
        models_modified = 0
        textures_copied = 0
        modified_model_files = []
        
        # Extract all model references from the item
        model_refs = extract_model_refs_from_item(item_data)
        
        if not model_refs:
            return 0, 0, []
        
        print(f"  Found {len(model_refs)} model references to process")
        
        # Base directory for models - supports both minecraft and custom namespaces
        # textures_dir is typically: .../assets/minecraft/textures
        # We need to go up to the assets directory
        base_assets_dir = os.path.dirname(os.path.dirname(textures_dir))
        
        # Track block->item model mappings for updating references
        block_to_item_mappings = {}
        
        for model_ref in model_refs:
            # Parse namespace and path from model reference
            if ":" in model_ref:
                namespace, model_path_rel = model_ref.split(":", 1)
            else:
                namespace = "minecraft"
                model_path_rel = model_ref
            
            # Model references are paths like "item/diamond" which map to models/item/diamond.json
            # Construct the full model path: assets/{namespace}/models/{path}.json
            model_path = os.path.join(base_assets_dir, namespace, "models", f"{model_path_rel}.json")
            
            if not os.path.exists(model_path):
                print(f"  Model not found: {model_path}")
                continue
            
            # Check if this is a block model - if so, create a copy in item/models instead
            is_block_model = model_path_rel.startswith("block/")
            if is_block_model:
                model_path, original_ref, new_ref = copy_block_model_to_item(model_path_rel, namespace, base_assets_dir)
                block_to_item_mappings[original_ref] = new_ref
            
            # Process the model file and its parent chain
            try:
                models_to_process = collect_model_parent_chain(model_path, base_assets_dir, processed_models, block_to_item_mappings)
                
                if not models_to_process:
                    continue
                
                # Process each model in the chain
                for process_model_path in models_to_process:
                    # Mark as processed
                    processed_models.add(process_model_path)
                    with open(process_model_path, 'r', encoding='utf-8') as f:
                        model_data = json.load(f)
                    
                    # Process textures and parent references
                    model_modified, copied = process_model_textures(model_data, textures_dir, items_texture_dir, block_to_item_mappings)
                    textures_copied += copied
                    
                    # Write back modified model file
                    if model_modified:
                        with open(process_model_path, 'w', encoding='utf-8') as f:
                            json.dump(model_data, f, indent=2)
                        models_modified += 1
                        modified_model_files.append(process_model_path)
                        print(f"    Updated model: {process_model_path}")
                        
            except Exception as e:
                print(f"  Error processing model chain for {model_path}: {e}")
                continue
        
        # Update item file references if any block models were remapped
        if block_to_item_mappings:
            item_data_modified = update_item_references(item_data, block_to_item_mappings)
            
            # Write back modified item file if needed
            if item_data_modified:
                with open(item_path, 'w', encoding='utf-8') as f:
                    json.dump(item_data, f, indent=2)
                print(f"  Updated item file: {item_path}")
        
        return models_modified, textures_copied, modified_model_files
        
    except Exception as e:
        print(f"Error processing item {item_path}: {e}")
        return 0, 0, []

def find_texture_file(textures_dir: str, texture_path: str) -> str:
    """
    Find a texture file given a relative texture path.
    
    Args:
        textures_dir: Base textures directory
        texture_path: Relative texture path (e.g., "item/diamond" or "entity/creeper")
        
    Returns:
        Absolute path to texture file if found, empty string otherwise
    """
    # Try with .png extension
    possible_path = os.path.join(textures_dir, f"{texture_path}.png")
    if os.path.exists(possible_path):
        return possible_path
    
    # Try without extension (in case it's already there)
    possible_path = os.path.join(textures_dir, texture_path)
    if os.path.exists(possible_path):
        return possible_path
    
    # Try with .png.mcmeta (animated texture)
    possible_path = os.path.join(textures_dir, f"{texture_path}.png.mcmeta")
    if os.path.exists(possible_path.replace(".png.mcmeta", ".png")):
        return possible_path.replace(".png.mcmeta", ".png")
    
    return ""

if __name__ == '__main__':
    success = main()

    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'success={str(success).lower()}\n')

    sys.exit(0 if success else 1)