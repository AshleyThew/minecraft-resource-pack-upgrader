# Minecraft Resource Pack Upgrader

[![GitHub release](https://img.shields.io/github/v/release/AshleyThew/minecraft-resource-pack-upgrader)](https://github.com/AshleyThew/minecraft-resource-pack-upgrader/releases)
[![License](https://img.shields.io/github/license/AshleyThew/minecraft-resource-pack-upgrader)](LICENSE)

A GitHub Action to automatically upgrade Minecraft resource packs to the new Minecraft 1.21.4+ format.

Modifies the input folder, converts and migrates items to the items folder.

## Features

✨ Upgrades resource pack JSON files with:

- Custom Model Data predicates
- Bow animations and states
- Crossbow animations and loading states
- Durability-based model variations

## Wanted/Potential Features

We are looking to add the following features in future releases:

- Support for additional Minecraft versions
- Automatic backup of original resource packs
- Enhanced error reporting and logging
- Integration with other Minecraft modding tools
- User-friendly configuration options

Feel free to suggest more features by opening an issue or submitting a pull request.

## Installation

1. Add this action to your GitHub workflow
2. Configure the source and destination paths
3. Run the workflow manually or on triggers

## Usage

Add to your GitHub Actions workflow:

```yaml
- name: Upgrade resource pack
  uses: AshleyThew/minecraft-resource-pack-upgrader@v.1.0.8
  with:
    input_path: 'path/to/source/resourcepack'
```

## Inputs

- `input_path`: The path to the source resource pack directory.

## Local Usage

Clone the git repo

```bash
git clone https://github.com/AshleyThew/minecraft-resource-pack-upgrader.git
```

or download the zip file directly:

[Download Zip](https://github.com/AshleyThew/minecraft-resource-pack-upgrader/archive/refs/heads/main.zip)

Run the following command:

```bash
python app/upgrade.py path/to/source/resourcepack
```

## Example

```yaml
name: Upgrade Resource Pack

on: [push]

jobs:
  upgrade:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v2

      - name: Upgrade resource pack
        uses: AshleyThew/minecraft-resource-pack-upgrader@1.0.0
        with:
          input_path: './'

      - name: Archive Release
        uses: thedoctor0/zip-release@master
        with:
          filename: 'upgraded_resourcepack.zip'
          exclusions: '*.git* README.md *.zip'

      - name: Upload artifact
        uses: actions/upload-artifact@v2
        with:
          name: upgraded-resource-pack
          path: upgraded_resource_pack.zip
```

## Troubleshooting

- Ensure your resource pack follows Minecraft's format
- Check file permissions on directories
- Verify JSON syntax in model files

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Credits

This project was inspired by and builds upon the work done in the [Minecraft-ResourcePack-Migrator](https://github.com/BrilliantTeam/Minecraft-ResourcePack-Migrator) repository. Special thanks to the contributors of that project for their foundational work.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
