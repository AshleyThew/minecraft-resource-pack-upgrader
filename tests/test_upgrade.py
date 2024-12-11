import pytest
import json
from app.upgrade import convert_json_format, process_directory

@pytest.fixture
def damage_item_json():
    return {
        "textures": {
            "layer0": "item/diamond_sword"
        },
        "overrides": [
            {
                "predicate": {"damage": 0.25},
                "model": "item/diamond_sword_damaged_1"
            },
            {
                "predicate": {"damage": 0.50},
                "model": "item/diamond_sword_damaged_2"
            }
        ]
    }

@pytest.fixture
def custom_model_data_json():
    return {
        "textures": {
            "layer0": "item/diamond_sword"
        },
        "overrides": [
            {
                "predicate": {"custom_model_data": 1},
                "model": "item/custom_sword_1"
            },
            {
                "predicate": {"custom_model_data": 2},
                "model": "item/custom_sword_2"
            }
        ]
    }

@pytest.fixture
def bow_json():
    return {
        "textures": {
            "layer0": "item/bow"
        },
        "overrides": [
            {
                "predicate": {"custom_model_data": 1},
                "model": "item/custom_bow"
            },
            {
                "predicate": {
                    "custom_model_data": 1,
                    "pulling": 1,
                    "pull": 0.65
                },
                "model": "item/custom_bow_pulling_0"
            },
            {
                "predicate": {
                    "custom_model_data": 1,
                    "pulling": 1,
                    "pull": 0.9
                },
                "model": "item/custom_bow_pulling_1"
            }
        ]
    }

def test_basic_item_conversion(custom_model_data_json):
    result = convert_json_format(custom_model_data_json)
    assert result["model"]["type"] == "range_dispatch"
    assert result["model"]["property"] == "custom_model_data"
    assert len(result["model"]["entries"]) == 2
    assert result["model"]["entries"][0]["threshold"] == 1
    assert result["model"]["entries"][1]["threshold"] == 2

def test_bow_conversion(bow_json):
    result = convert_json_format(bow_json)
    assert result["model"]["type"] == "range_dispatch"
    assert len(result["model"]["entries"]) == 1
    
    entry = result["model"]["entries"][0]
    assert entry["model"]["type"] == "minecraft:condition"
    assert entry["model"]["property"] == "minecraft:using_item"
    assert len(entry["model"]["on_true"]["entries"]) == 2

def test_damage_based_conversion(damage_item_json):
    result = convert_json_format(damage_item_json)
    assert result["model"]["type"] == "range_dispatch"
    assert result["model"]["property"] == "damage"
    assert len(result["model"]["entries"]) == 2
    assert result["model"]["entries"][0]["threshold"] == 0.25
    assert result["model"]["entries"][0]["model"]["model"] == "item/diamond_sword_damaged_1"
    assert result["model"]["entries"][1]["threshold"] == 0.50
    assert result["model"]["entries"][1]["model"]["model"] == "item/diamond_sword_damaged_2"

def test_process_directory(tmp_path):
    # Create test directory structure
    assets_dir = tmp_path / "assets" / "minecraft" / "models" / "item"
    assets_dir.mkdir(parents=True)

    # Create test json file
    test_file = assets_dir / "diamond_sword.json"
    with open(test_file, "w") as f:
        json.dump({
            "textures": {"layer0": "item/diamond_sword"},
            "overrides": [
                {
                    "predicate": {"custom_model_data": 1},
                    "model": "item/custom_sword"
                }
            ]
        }, f)

    # Process directory
    result = process_directory(str(tmp_path))
    assert result == True

    # Check if output file exists
    output_file = tmp_path / "assets" / "minecraft" / "items" / "diamond_sword.json"
    assert output_file.exists()

    # Check if input file was removed
    assert not test_file.exists()

def test_invalid_json_handling(tmp_path):
    # Create test directory structure
    assets_dir = tmp_path / "assets" / "minecraft" / "models" / "item"
    assets_dir.mkdir(parents=True)

    # Create invalid json file
    test_file = assets_dir / "invalid.json"
    with open(test_file, "w") as f:
        f.write("invalid json content")

    # Process should complete without failing
    result = process_directory(str(tmp_path))
    assert result == True
    assert test_file.exists()  # Invalid file should remain

def test_empty_directory(tmp_path):
    result = process_directory(str(tmp_path))
    assert result == True