#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SDM商店转ViScriptShop工具 - GUI 版本
功能:
  1. SDM商店转ViScriptShop工具
"""

import json
import re
import os
import sys
import struct
import zipfile
from io import BytesIO
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ==================== 导入原有功能 ====================

# 导入NBT处理类
class NBTReader:
    """NBT 文件读取器"""
    
    TYPE_NAMES = {
        0: "end", 1: "byte", 2: "short", 3: "int", 4: "long",
        5: "float", 6: "double", 7: "byte_array", 8: "string",
        9: "list", 10: "compound", 11: "int_array", 12: "long_array",
    }

    def __init__(self, data: bytes):
        self.stream = BytesIO(data)

    def read_byte(self) -> int:
        return struct.unpack('>b', self.stream.read(1))[0]

    def read_ubyte(self) -> int:
        return struct.unpack('>B', self.stream.read(1))[0]

    def read_short(self) -> int:
        return struct.unpack('>h', self.stream.read(2))[0]

    def read_int(self) -> int:
        return struct.unpack('>i', self.stream.read(4))[0]

    def read_long(self) -> int:
        return struct.unpack('>q', self.stream.read(8))[0]

    def read_float(self) -> float:
        return struct.unpack('>f', self.stream.read(4))[0]

    def read_double(self) -> float:
        return struct.unpack('>d', self.stream.read(8))[0]

    def read_string(self) -> str:
        length = self.read_ushort()
        if length == 0:
            return ""
        return self.stream.read(length).decode('utf-8', errors='replace')

    def read_ushort(self) -> int:
        return struct.unpack('>H', self.stream.read(2))[0]

    def read_byte_array(self) -> list:
        length = self.read_int()
        return [self.read_byte() for _ in range(length)]

    def read_int_array(self) -> list:
        length = self.read_int()
        return [self.read_int() for _ in range(length)]

    def read_long_array(self) -> list:
        length = self.read_int()
        return [self.read_long() for _ in range(length)]

    def read_list(self) -> dict:
        tag_type = self.read_byte()
        length = self.read_int()
        result = []
        for _ in range(length):
            result.append(self.read_payload(tag_type))
        return {
            "_type": "list",
            "_element_type": self.TYPE_NAMES.get(tag_type, tag_type),
            "_value": result
        }

    def read_compound(self) -> dict:
        result = {"_type": "compound"}
        while True:
            tag_type = self.read_byte()
            if tag_type == 0:
                break
            name = self.read_string()
            result[name] = self.read_payload(tag_type)
        return result

    def read_payload(self, tag_type: int):
        if tag_type == 1:
            return {"_type": "byte", "_value": self.read_byte()}
        elif tag_type == 2:
            return {"_type": "short", "_value": self.read_short()}
        elif tag_type == 3:
            return {"_type": "int", "_value": self.read_int()}
        elif tag_type == 4:
            return {"_type": "long", "_value": self.read_long()}
        elif tag_type == 5:
            return {"_type": "float", "_value": self.read_float()}
        elif tag_type == 6:
            return {"_type": "double", "_value": self.read_double()}
        elif tag_type == 7:
            return {"_type": "byte_array", "_value": self.read_byte_array()}
        elif tag_type == 8:
            return {"_type": "string", "_value": self.read_string()}
        elif tag_type == 9:
            return self.read_list()
        elif tag_type == 10:
            return self.read_compound()
        elif tag_type == 11:
            return {"_type": "int_array", "_value": self.read_int_array()}
        elif tag_type == 12:
            return {"_type": "long_array", "_value": self.read_long_array()}
        else:
            raise ValueError(f"未知的标签类型: {tag_type}")

    def read_root(self):
        tag_type = self.read_byte()
        if tag_type == 0:
            self.stream.seek(0)
            return self._try_parse_raw()

        name = self.read_string()
        data = self.read_payload(tag_type)
        return {"_root_name": name, "_root_type": self.TYPE_NAMES.get(tag_type, tag_type), "data": data}

    def _try_parse_raw(self):
        data = self.stream.read()
        if data[:2] == b'\x1f\x8b':
            import gzip
            try:
                data = gzip.decompress(data)
                self.stream = BytesIO(data)
                return self.read_root()
            except:
                pass

        self.stream = BytesIO(data)
        try:
            tag_type = self.read_byte()
            name = self.read_string()
            payload = self.read_payload(tag_type)
            return {"_root_name": name, "_root_type": self.TYPE_NAMES.get(tag_type, tag_type), "data": payload}
        except:
            return {"_raw_bytes": data.hex(), "_error": "无法解析为 NBT"}


class NBTWriter:
    """NBT 文件写入器"""

    TYPE_IDS = {
        "end": 0, "byte": 1, "short": 2, "int": 3, "long": 4,
        "float": 5, "double": 6, "byte_array": 7, "string": 8,
        "list": 9, "compound": 10, "int_array": 11, "long_array": 12,
    }

    def __init__(self):
        self.stream = BytesIO()

    def write_byte(self, value: int):
        self.stream.write(struct.pack('>b', value))

    def write_ubyte(self, value: int):
        self.stream.write(struct.pack('>B', value))

    def write_short(self, value: int):
        self.stream.write(struct.pack('>h', value))

    def write_int(self, value: int):
        self.stream.write(struct.pack('>i', value))

    def write_long(self, value: int):
        self.stream.write(struct.pack('>q', value))

    def write_float(self, value: float):
        self.stream.write(struct.pack('>f', value))

    def write_double(self, value: float):
        self.stream.write(struct.pack('>d', value))

    def write_string(self, value: str):
        encoded = value.encode('utf-8')
        self.write_ushort(len(encoded))
        self.stream.write(encoded)

    def write_ushort(self, value: int):
        self.stream.write(struct.pack('>H', value))

    def write_byte_array(self, value: list):
        self.write_int(len(value))
        for b in value:
            self.write_byte(b)

    def write_int_array(self, value: list):
        self.write_int(len(value))
        for i in value:
            self.write_int(i)

    def write_long_array(self, value: list):
        self.write_int(len(value))
        for l in value:
            self.write_long(l)

    def write_list(self, value: dict):
        element_type_name = value.get("_element_type", "byte")
        tag_type = self.TYPE_IDS.get(element_type_name, 1)
        items = value.get("_value", [])

        self.write_byte(tag_type)
        self.write_int(len(items))

        for item in items:
            self.write_payload(tag_type, item)

    def write_compound(self, value: dict):
        for name, item_value in value.items():
            if name.startswith('_'):
                continue

            if isinstance(item_value, dict) and "_type" in item_value:
                type_name = item_value["_type"]
                tag_type = self.TYPE_IDS.get(type_name, 8)
                self.write_byte(tag_type)
                self.write_string(name)
                self.write_payload(tag_type, item_value)
            else:
                tag_type = self.infer_tag_type(item_value)
                self.write_byte(tag_type)
                self.write_string(name)
                self.write_payload(tag_type, {"_value": item_value})

        self.write_byte(0)

    def infer_tag_type(self, value):
        if isinstance(value, bool):
            return 1
        elif isinstance(value, int):
            if -128 <= value <= 127:
                return 1
            elif -32768 <= value <= 32767:
                return 2
            elif -2147483648 <= value <= 2147483647:
                return 3
            else:
                return 4
        elif isinstance(value, float):
            return 6
        elif isinstance(value, str):
            return 8
        elif isinstance(value, list):
            return 9
        elif isinstance(value, dict):
            return 10
        else:
            return 8

    def write_payload(self, tag_type: int, value):
        if tag_type == 1:
            val = value["_value"] if isinstance(value, dict) else value
            self.write_byte(int(val))
        elif tag_type == 2:
            val = value["_value"] if isinstance(value, dict) else value
            self.write_short(int(val))
        elif tag_type == 3:
            val = value["_value"] if isinstance(value, dict) else value
            self.write_int(int(val))
        elif tag_type == 4:
            val = value["_value"] if isinstance(value, dict) else value
            self.write_long(int(val))
        elif tag_type == 5:
            val = value["_value"] if isinstance(value, dict) else value
            self.write_float(float(val))
        elif tag_type == 6:
            val = value["_value"] if isinstance(value, dict) else value
            self.write_double(float(val))
        elif tag_type == 7:
            val = value["_value"] if isinstance(value, dict) else value
            self.write_byte_array(val)
        elif tag_type == 8:
            val = value["_value"] if isinstance(value, dict) else value
            self.write_string(str(val))
        elif tag_type == 9:
            if isinstance(value, dict):
                self.write_list(value)
            else:
                self.write_byte(0)
                self.write_int(0)
        elif tag_type == 10:
            if isinstance(value, dict):
                self.write_compound(value)
            else:
                self.write_byte(0)
        elif tag_type == 11:
            val = value["_value"] if isinstance(value, dict) else value
            self.write_int_array(val)
        elif tag_type == 12:
            val = value["_value"] if isinstance(value, dict) else value
            self.write_long_array(val)
        else:
            raise ValueError(f"未知的标签类型: {tag_type}")

    def write_root(self, name: str, data):
        if isinstance(data, dict) and "_type" in data:
            type_name = data["_type"]
            tag_type = self.TYPE_IDS.get(type_name, 10)
        else:
            tag_type = 10

        self.write_byte(tag_type)
        self.write_string(name)
        self.write_payload(tag_type, data)

    def get_bytes(self) -> bytes:
        return self.stream.getvalue()


# 导入功能函数
def nbt_to_json(input_file: str, output_file: str = None):
    """NBT 转 JSON"""
    if output_file is None:
        output_file = input_file + '.json'

    with open(input_file, 'rb') as f:
        data = f.read()

    if data[:2] == b'\x1f\x8b':
        import gzip
        data = gzip.decompress(data)

    reader = NBTReader(data)
    result = reader.read_root()

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return output_file


def json_to_nbt(input_file: str, output_file: str = None, compress: bool = False):
    """JSON 转 NBT"""
    if output_file is None:
        if input_file.endswith('.json'):
            base = input_file[:-5]
            if base.endswith('.shopproj'):
                output_file = base[:-9] + '.converted.shopproj'
            else:
                output_file = base + '.converted'
        else:
            output_file = input_file + '.converted'

    with open(input_file, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    root_name = json_data.get("_root_name", "")
    root_data = json_data.get("data", json_data)

    writer = NBTWriter()
    writer.write_root(root_name, root_data)

    nbt_data = writer.get_bytes()

    if compress:
        import gzip
        nbt_data = gzip.compress(nbt_data)

    with open(output_file, 'wb') as f:
        f.write(nbt_data)

    return output_file


def get_mod_info_from_jar(jar_path):
    """从 jar 文件中读取模组信息 (mod_id, author, version, name)"""
    mod_id = Path(jar_path).stem.split('-')[0].split('_')[0].lower()
    author = "未知"
    version = "未知"
    name = Path(jar_path).stem
    
    try:
        with zipfile.ZipFile(jar_path, 'r') as z:
            # NeoForge / Forge mods.toml
            if 'META-INF/neoforge.mods.toml' in z.namelist():
                content = z.read('META-INF/neoforge.mods.toml').decode('utf-8')
                match = re.search(r'modId\s*=\s*"([^"]+)"', content)
                if match:
                    mod_id = match.group(1).lower()
                # 尝试获取作者
                author_match = re.search(r'authors\s*=\s*"([^"]+)"', content)
                if author_match:
                    author = author_match.group(1)
                # 尝试获取版本
                version_match = re.search(r'version\s*=\s*"([^"]+)"', content)
                if version_match:
                    version = version_match.group(1)
                # 尝试获取显示名称
                display_match = re.search(r'displayName\s*=\s*"([^"]+)"', content)
                if display_match:
                    name = display_match.group(1)
            
            elif 'META-INF/mods.toml' in z.namelist():
                content = z.read('META-INF/mods.toml').decode('utf-8')
                match = re.search(r'modId\s*=\s*"([^"]+)"', content)
                if match:
                    mod_id = match.group(1).lower()
                author_match = re.search(r'authors\s*=\s*"([^"]+)"', content)
                if author_match:
                    author = author_match.group(1)
                version_match = re.search(r'version\s*=\s*"([^"]+)"', content)
                if version_match:
                    version = version_match.group(1)
                display_match = re.search(r'displayName\s*=\s*"([^"]+)"', content)
                if display_match:
                    name = display_match.group(1)
            
            # Fabric
            elif 'fabric.mod.json' in z.namelist():
                content = z.read('fabric.mod.json').decode('utf-8')
                data = json.loads(content)
                if 'id' in data:
                    mod_id = data['id'].lower()
                if 'authors' in data:
                    if isinstance(data['authors'], list):
                        author = ', '.join(str(a) for a in data['authors'])
                    else:
                        author = str(data['authors'])
                if 'version' in data:
                    version = data['version']
                if 'name' in data:
                    name = data['name']
            
            # 旧版 mcmod.info
            elif 'mcmod.info' in z.namelist():
                content = z.read('mcmod.info').decode('utf-8')
                data = json.loads(content)
                mod_info = None
                if isinstance(data, list) and len(data) > 0:
                    mod_info = data[0]
                elif isinstance(data, dict) and 'modList' in data:
                    if len(data['modList']) > 0:
                        mod_info = data['modList'][0]
                
                if mod_info:
                    if 'modid' in mod_info:
                        mod_id = mod_info['modid'].lower()
                    if 'authorList' in mod_info:
                        author = ', '.join(mod_info['authorList'])
                    elif 'authors' in mod_info:
                        author = mod_info['authors']
                    if 'version' in mod_info:
                        version = mod_info['version']
                    if 'name' in mod_info:
                        name = mod_info['name']
    except:
        pass
    
    return {
        "mod_id": mod_id,
        "author": author,
        "version": version,
        "name": name,
        "jar_name": Path(jar_path).name
    }


def get_installed_mods(mods_dir):
    """获取已安装模组的信息字典 {mod_id: {author, version, name, jar_name}}"""
    installed_mods = {
        "minecraft": {"mod_id": "minecraft", "author": "Mojang", "version": "1.21.1", "name": "Minecraft", "jar_name": "minecraft.jar"}
    }
    
    if not os.path.exists(mods_dir):
        return installed_mods
    
    for jar_file in Path(mods_dir).glob("*.jar"):
        mod_info = get_mod_info_from_jar(jar_file)
        mod_id = mod_info["mod_id"]
        # 如果同一个 mod_id 已经存在，保留第一个（通常是最新的）
        if mod_id not in installed_mods:
            installed_mods[mod_id] = mod_info
    
    return installed_mods


def get_items_from_mod_jar(jar_path):
    """从模组 jar 文件中提取所有物品 ID"""
    items = set()
    
    try:
        with zipfile.ZipFile(jar_path, 'r') as z:
            # 扫描所有可能的物品定义位置
            for name in z.namelist():
                # NeoForge/Forge/Fabric 1.21+ 格式
                if name.startswith('data/') and name.endswith('/item/'):
                    # 提取物品 ID
                    parts = name.split('/')
                    if len(parts) >= 4:
                        namespace = parts[1]
                        item_name = Path(name).stem
                        items.add(f"{namespace}:{item_name}")
                
                # 旧版 Forge 格式 (assets/namespace/models/item/)
                elif 'models/item/' in name and name.endswith('.json'):
                    parts = name.split('/')
                    if len(parts) >= 4:
                        namespace = parts[1]
                        item_name = Path(name).stem
                        items.add(f"{namespace}:{item_name}")
                
                # 数据包格式
                elif name.startswith('assets/') and '/models/item/' in name and name.endswith('.json'):
                    parts = name.split('/')
                    if len(parts) >= 5:
                        namespace = parts[1]
                        item_name = Path(name).stem
                        items.add(f"{namespace}:{item_name}")
            
            # 尝试读取注册表文件
            if 'data/forge/registry.json' in z.namelist():
                try:
                    content = z.read('data/forge/registry.json').decode('utf-8')
                    data = json.loads(content)
                    if 'items' in data:
                        for item_id in data['items']:
                            items.add(item_id.lower())
                except:
                    pass
    except:
        pass
    
    return items


def scan_all_items_from_mods(mods_dir, target_mods):
    """扫描所有已安装模组中的物品"""
    all_items = set()
    mod_items_map = {}  # {mod_id: set(items)}
    
    # 添加原版物品（常用）
    vanilla_items = {
        "minecraft:stone", "minecraft:dirt", "minecraft:grass_block",
        "minecraft:cobblestone", "minecraft:oak_planks", "minecraft:spruce_planks",
        "minecraft:birch_planks", "minecraft:jungle_planks", "minecraft:acacia_planks",
        "minecraft:dark_oak_planks", "minecraft:mangrove_planks", "minecraft:cherry_planks",
        "minecraft:oak_sapling", "minecraft:spruce_sapling", "minecraft:birch_sapling",
        "minecraft:sand", "minecraft:gravel", "minecraft:gold_ore", "minecraft:iron_ore",
        "minecraft:coal_ore", "minecraft:oak_log", "minecraft:spruce_log", "minecraft:birch_log",
        "minecraft:jungle_log", "minecraft:acacia_log", "minecraft:dark_oak_log",
        "minecraft:mangrove_log", "minecraft:cherry_log", "minecraft:stripped_oak_log",
        "minecraft:oak_wood", "minecraft:spruce_wood", "minecraft:birch_wood",
        "minecraft:jungle_wood", "minecraft:acacia_wood", "minecraft:dark_oak_wood",
        "minecraft:mangrove_wood", "minecraft:cherry_wood", "minecraft:oak_leaves",
        "minecraft:spruce_leaves", "minecraft:birch_leaves", "minecraft:jungle_leaves",
        "minecraft:acacia_leaves", "minecraft:dark_oak_leaves", "minecraft:mangrove_leaves",
        "minecraft:cherry_leaves", "minecraft:azalea_leaves", "minecraft:flowering_azalea_leaves",
        "minecraft:glass", "minecraft:lapis_ore", "minecraft:lapis_block",
        "minecraft:sandstone", "minecraft:chiseled_sandstone", "minecraft:cut_sandstone",
        "minecraft:note_block", "minecraft:powered_rail", "minecraft:detector_rail",
        "minecraft:sticky_piston", "minecraft:cobweb", "minecraft:grass",
        "minecraft:fern", "minecraft:dead_bush", "minecraft:seagrass", "minecraft:sea_pickle",
        "minecraft:piston", "minecraft:white_wool", "minecraft:orange_wool",
        "minecraft:magenta_wool", "minecraft:light_blue_wool", "minecraft:yellow_wool",
        "minecraft:lime_wool", "minecraft:pink_wool", "minecraft:gray_wool",
        "minecraft:light_gray_wool", "minecraft:cyan_wool", "minecraft:purple_wool",
        "minecraft:blue_wool", "minecraft:brown_wool", "minecraft:green_wool",
        "minecraft:red_wool", "minecraft:black_wool", "minecraft:dandelion",
        "minecraft:poppy", "minecraft:blue_orchid", "minecraft:allium",
        "minecraft:azure_bluet", "minecraft:red_tulip", "minecraft:orange_tulip",
        "minecraft:white_tulip", "minecraft:pink_tulip", "minecraft:oxeye_daisy",
        "minecraft:cornflower", "minecraft:lily_of_the_valley", "minecraft:wither_rose",
        "minecraft:spore_blossom", "minecraft:brown_mushroom", "minecraft:red_mushroom",
        "minecraft:crimson_fungus", "minecraft:warped_fungus", "minecraft:crimson_roots",
        "minecraft:warped_roots", "minecraft:nether_sprouts", "minecraft:weeping_vines",
        "minecraft:twisting_vines", "minecraft:sugar_cane", "minecraft:kelp",
        "minecraft:bamboo", "minecraft:gold_block", "minecraft:iron_block",
        "minecraft:oak_slab", "minecraft:spruce_slab", "minecraft:birch_slab",
        "minecraft:jungle_slab", "minecraft:acacia_slab", "minecraft:dark_oak_slab",
        "minecraft:mangrove_slab", "minecraft:cherry_slab", "minecraft:bamboo_slab",
        "minecraft:stone_slab", "minecraft:smooth_stone_slab", "minecraft:sandstone_slab",
        "minecraft:cut_sandstone_slab", "minecraft:petrified_oak_slab",
        "minecraft:cobblestone_slab", "minecraft:brick_slab", "minecraft:stone_brick_slab",
        "minecraft:mud_brick_slab", "minecraft:nether_brick_slab",
        "minecraft:quartz_slab", "minecraft:red_sandstone_slab",
        "minecraft:cut_red_sandstone_slab", "minecraft:purpur_slab",
        "minecraft:prismarine_slab", "minecraft:prismarine_brick_slab",
        "minecraft:dark_prismarine_slab", "minecraft:smooth_quartz",
        "minecraft:smooth_red_sandstone", "minecraft:smooth_sandstone",
        "minecraft:smooth_stone", "minecraft:bricks", "minecraft:bookshelf",
        "minecraft:mossy_cobblestone", "minecraft:obsidian", "minecraft:torch",
        "minecraft:end_rod", "minecraft:chorus_plant", "minecraft:chorus_flower",
        "minecraft:purpur_block", "minecraft:purpur_pillar", "minecraft:purpur_stairs",
        "minecraft:spawner", "minecraft:chest", "minecraft:crafting_table",
        "minecraft:farmland", "minecraft:furnace", "minecraft:ladder",
        "minecraft:cobblestone_stairs", "minecraft:snow", "minecraft:ice",
        "minecraft:snow_block", "minecraft:cactus", "minecraft:clay",
        "minecraft:jukebox", "minecraft:oak_fence", "minecraft:spruce_fence",
        "minecraft:birch_fence", "minecraft:jungle_fence", "minecraft:acacia_fence",
        "minecraft:dark_oak_fence", "minecraft:mangrove_fence", "minecraft:cherry_fence",
        "minecraft:bamboo_fence", "minecraft:nether_brick_fence",
        "minecraft:oak_stairs", "minecraft:spruce_stairs", "minecraft:birch_stairs",
        "minecraft:jungle_stairs", "minecraft:acacia_stairs", "minecraft:dark_oak_stairs",
        "minecraft:mangrove_stairs", "minecraft:cherry_stairs", "minecraft:bamboo_stairs",
        "minecraft:stone_stairs", "minecraft:mossy_cobblestone_stairs",
        "minecraft:brick_stairs", "minecraft:stone_brick_stairs",
        "minecraft:mud_brick_stairs", "minecraft:nether_brick_stairs",
        "minecraft:sandstone_stairs", "minecraft:smooth_quartz_stairs",
        "minecraft:smooth_red_sandstone_stairs", "minecraft:smooth_sandstone_stairs",
        "minecraft:purpur_stairs", "minecraft:prismarine_stairs",
        "minecraft:prismarine_brick_stairs", "minecraft:dark_prismarine_stairs",
        "minecraft:cobblestone_wall", "minecraft:mossy_cobblestone_wall",
        "minecraft:brick_wall", "minecraft:prismarine_wall",
        "minecraft:red_sandstone_wall", "minecraft:mossy_stone_brick_wall",
        "minecraft:granite_wall", "minecraft:stone_brick_wall",
        "minecraft:mud_brick_wall", "minecraft:nether_brick_wall",
        "minecraft:andesite_wall", "minecraft:red_nether_brick_wall",
        "minecraft:sandstone_wall", "minecraft:end_stone_brick_wall",
        "minecraft:diorite_wall", "minecraft:blackstone_wall",
        "minecraft:polished_blackstone_wall",
        "minecraft:polished_blackstone_brick_wall",
        "minecraft:cobbled_deepslate_wall", "minecraft:polished_deepslate_wall",
        "minecraft:deepslate_brick_wall", "minecraft:deepslate_tile_wall",
        "minecraft:anvil", "minecraft:chipped_anvil", "minecraft:damaged_anvil",
        "minecraft:trapped_chest", "minecraft:light_weighted_pressure_plate",
        "minecraft:heavy_weighted_pressure_plate", "minecraft:daylight_detector",
        "minecraft:redstone_block", "minecraft:nether_quartz_ore",
        "minecraft:hopper", "minecraft:chiseled_quartz_block",
        "minecraft:quartz_block", "minecraft:quartz_bricks",
        "minecraft:quartz_pillar", "minecraft:quartz_stairs",
        "minecraft:activator_rail", "minecraft:dropper", "minecraft:barrier",
        "minecraft:iron_trapdoor", "minecraft:hay_block", "minecraft:white_carpet",
        "minecraft:orange_carpet", "minecraft:magenta_carpet",
        "minecraft:light_blue_carpet", "minecraft:yellow_carpet",
        "minecraft:lime_carpet", "minecraft:pink_carpet", "minecraft:gray_carpet",
        "minecraft:light_gray_carpet", "minecraft:cyan_carpet",
        "minecraft:purple_carpet", "minecraft:blue_carpet", "minecraft:brown_carpet",
        "minecraft:green_carpet", "minecraft:red_carpet", "minecraft:black_carpet",
        "minecraft:terracotta", "minecraft:coal_block", "minecraft:packed_ice",
        "minecraft:acacia_stairs", "minecraft:dark_oak_stairs",
        "minecraft:slime_block", "minecraft:grass_path", "minecraft:sunflower",
        "minecraft:lilac", "minecraft:rose_bush", "minecraft:peony",
        "minecraft:tall_grass", "minecraft:large_fern", "minecraft:white_stained_glass",
        "minecraft:orange_stained_glass", "minecraft:magenta_stained_glass",
        "minecraft:light_blue_stained_glass", "minecraft:yellow_stained_glass",
        "minecraft:lime_stained_glass", "minecraft:pink_stained_glass",
        "minecraft:gray_stained_glass", "minecraft:light_gray_stained_glass",
        "minecraft:cyan_stained_glass", "minecraft:purple_stained_glass",
        "minecraft:blue_stained_glass", "minecraft:brown_stained_glass",
        "minecraft:green_stained_glass", "minecraft:red_stained_glass",
        "minecraft:black_stained_glass", "minecraft:white_stained_glass_pane",
        "minecraft:orange_stained_glass_pane", "minecraft:magenta_stained_glass_pane",
        "minecraft:light_blue_stained_glass_pane", "minecraft:yellow_stained_glass_pane",
        "minecraft:lime_stained_glass_pane", "minecraft:pink_stained_glass_pane",
        "minecraft:gray_stained_glass_pane", "minecraft:light_gray_stained_glass_pane",
        "minecraft:cyan_stained_glass_pane", "minecraft:purple_stained_glass_pane",
        "minecraft:blue_stained_glass_pane", "minecraft:brown_stained_glass_pane",
        "minecraft:green_stained_glass_pane", "minecraft:red_stained_glass_pane",
        "minecraft:black_stained_glass_pane", "minecraft:prismarine",
        "minecraft:prismarine_bricks", "minecraft:dark_prismarine",
        "minecraft:prismarine_stairs", "minecraft:prismarine_brick_stairs",
        "minecraft:dark_prismarine_stairs", "minecraft:sea_lantern",
        "minecraft:red_sandstone", "minecraft:chiseled_red_sandstone",
        "minecraft:cut_red_sandstone", "minecraft:red_sandstone_stairs",
        "minecraft:magma_block", "minecraft:nether_wart_block",
        "minecraft:warped_wart_block", "minecraft:red_nether_bricks",
        "minecraft:bone_block", "minecraft:white_concrete",
        "minecraft:orange_concrete", "minecraft:magenta_concrete",
        "minecraft:light_blue_concrete", "minecraft:yellow_concrete",
        "minecraft:lime_concrete", "minecraft:pink_concrete",
        "minecraft:gray_concrete", "minecraft:light_gray_concrete",
        "minecraft:cyan_concrete", "minecraft:purple_concrete",
        "minecraft:blue_concrete", "minecraft:brown_concrete",
        "minecraft:green_concrete", "minecraft:red_concrete",
        "minecraft:black_concrete", "minecraft:white_concrete_powder",
        "minecraft:orange_concrete_powder", "minecraft:magenta_concrete_powder",
        "minecraft:light_blue_concrete_powder", "minecraft:yellow_concrete_powder",
        "minecraft:lime_concrete_powder", "minecraft:pink_concrete_powder",
        "minecraft:gray_concrete_powder", "minecraft:light_gray_concrete_powder",
        "minecraft:cyan_concrete_powder", "minecraft:purple_concrete_powder",
        "minecraft:blue_concrete_powder", "minecraft:brown_concrete_powder",
        "minecraft:green_concrete_powder", "minecraft:red_concrete_powder",
        "minecraft:black_concrete_powder", "minecraft:turtle_egg",
        "minecraft:dead_tube_coral_block", "minecraft:dead_brain_coral_block",
        "minecraft:dead_bubble_coral_block", "minecraft:dead_fire_coral_block",
        "minecraft:dead_horn_coral_block", "minecraft:tube_coral_block",
        "minecraft:brain_coral_block", "minecraft:bubble_coral_block",
        "minecraft:fire_coral_block", "minecraft:horn_coral_block",
        "minecraft:dead_tube_coral", "minecraft:dead_brain_coral",
        "minecraft:dead_bubble_coral", "minecraft:dead_fire_coral",
        "minecraft:dead_horn_coral", "minecraft:tube_coral",
        "minecraft:brain_coral", "minecraft:bubble_coral",
        "minecraft:fire_coral", "minecraft:horn_coral",
        "minecraft:dead_tube_coral_fan", "minecraft:dead_brain_coral_fan",
        "minecraft:dead_bubble_coral_fan", "minecraft:dead_fire_coral_fan",
        "minecraft:dead_horn_coral_fan", "minecraft:tube_coral_fan",
        "minecraft:brain_coral_fan", "minecraft:bubble_coral_fan",
        "minecraft:fire_coral_fan", "minecraft:horn_coral_fan",
        "minecraft:blue_ice", "minecraft:conduit", "minecraft:polished_granite_stairs",
        "minecraft:smooth_red_sandstone_stairs", "minecraft:mossy_stone_brick_stairs",
        "minecraft:polished_diorite_stairs", "minecraft:mossy_cobblestone_stairs",
        "minecraft:end_stone_brick_stairs", "minecraft:stone_stairs",
        "minecraft:smooth_sandstone_stairs", "minecraft:smooth_quartz_stairs",
        "minecraft:granite_stairs", "minecraft:andesite_stairs",
        "minecraft:red_nether_brick_stairs", "minecraft:polished_andesite_stairs",
        "minecraft:diorite_stairs", "minecraft:cobbled_deepslate_stairs",
        "minecraft:polished_deepslate_stairs", "minecraft:deepslate_brick_stairs",
        "minecraft:deepslate_tile_stairs", "minecraft:polished_granite_slab",
        "minecraft:smooth_red_sandstone_slab", "minecraft:mossy_stone_brick_slab",
        "minecraft:polished_diorite_slab", "minecraft:mossy_cobblestone_slab",
        "minecraft:end_stone_brick_slab", "minecraft:smooth_sandstone_slab",
        "minecraft:smooth_quartz_slab", "minecraft:granite_slab",
        "minecraft:andesite_slab", "minecraft:red_nether_brick_slab",
        "minecraft:polished_andesite_slab", "minecraft:diorite_slab",
        "minecraft:cobbled_deepslate_slab", "minecraft:polished_deepslate_slab",
        "minecraft:deepslate_brick_slab", "minecraft:deepslate_tile_slab",
        "minecraft:scaffolding", "minecraft:redstone", "minecraft:redstone_torch",
        "minecraft:stone_button", "minecraft:oak_button", "minecraft:spruce_button",
        "minecraft:birch_button", "minecraft:jungle_button", "minecraft:acacia_button",
        "minecraft:dark_oak_button", "minecraft:mangrove_button",
        "minecraft:cherry_button", "minecraft:bamboo_button",
        "minecraft:stone_pressure_plate", "minecraft:oak_pressure_plate",
        "minecraft:spruce_pressure_plate", "minecraft:birch_pressure_plate",
        "minecraft:jungle_pressure_plate", "minecraft:acacia_pressure_plate",
        "minecraft:dark_oak_pressure_plate", "minecraft:mangrove_pressure_plate",
        "minecraft:cherry_pressure_plate", "minecraft:bamboo_pressure_plate",
        "minecraft:light_weighted_pressure_plate",
        "minecraft:heavy_weighted_pressure_plate", "minecraft:iron_door",
        "minecraft:oak_door", "minecraft:spruce_door", "minecraft:birch_door",
        "minecraft:jungle_door", "minecraft:acacia_door", "minecraft:dark_oak_door",
        "minecraft:mangrove_door", "minecraft:cherry_door", "minecraft:bamboo_door",
        "minecraft:iron_trapdoor", "minecraft:oak_trapdoor",
        "minecraft:spruce_trapdoor", "minecraft:birch_trapdoor",
        "minecraft:jungle_trapdoor", "minecraft:acacia_trapdoor",
        "minecraft:dark_oak_trapdoor", "minecraft:mangrove_trapdoor",
        "minecraft:cherry_trapdoor", "minecraft:bamboo_trapdoor",
        "minecraft:oak_fence_gate", "minecraft:spruce_fence_gate",
        "minecraft:birch_fence_gate", "minecraft:jungle_fence_gate",
        "minecraft:acacia_fence_gate", "minecraft:dark_oak_fence_gate",
        "minecraft:mangrove_fence_gate", "minecraft:cherry_fence_gate",
        "minecraft:bamboo_fence_gate", "minecraft:iron_bars", "minecraft:chain",
        "minecraft:glass_pane", "minecraft:oak_sign", "minecraft:spruce_sign",
        "minecraft:birch_sign", "minecraft:jungle_sign", "minecraft:acacia_sign",
        "minecraft:dark_oak_sign", "minecraft:mangrove_sign",
        "minecraft:cherry_sign", "minecraft:bamboo_sign",
        "minecraft:crimson_sign", "minecraft:warped_sign",
        "minecraft:oak_hanging_sign", "minecraft:spruce_hanging_sign",
        "minecraft:birch_hanging_sign", "minecraft:jungle_hanging_sign",
        "minecraft:acacia_hanging_sign", "minecraft:dark_oak_hanging_sign",
        "minecraft:mangrove_hanging_sign", "minecraft:cherry_hanging_sign",
        "minecraft:bamboo_hanging_sign", "minecraft:crimson_hanging_sign",
        "minecraft:warped_hanging_sign", "minecraft:lectern",
        "minecraft:stonecutter", "minecraft:bell", "minecraft:lantern",
        "minecraft:soul_lantern", "minecraft:campfire", "minecraft:soul_campfire",
        "minecraft:shroomlight", "minecraft:bee_nest", "minecraft:beehive",
        "minecraft:honeycomb_block", "minecraft:lodestone",
        "minecraft:crying_obsidian", "minecraft:blackstone",
        "minecraft:blackstone_slab", "minecraft:blackstone_stairs",
        "minecraft:gilded_blackstone", "minecraft:polished_blackstone",
        "minecraft:polished_blackstone_slab", "minecraft:polished_blackstone_stairs",
        "minecraft:chiseled_polished_blackstone",
        "minecraft:polished_blackstone_bricks",
        "minecraft:polished_blackstone_brick_slab",
        "minecraft:polished_blackstone_brick_stairs",
        "minecraft:cracked_polished_blackstone_bricks",
        "minecraft:respawn_anchor", "minecraft:candle", "minecraft:white_candle",
        "minecraft:orange_candle", "minecraft:magenta_candle",
        "minecraft:light_blue_candle", "minecraft:yellow_candle",
        "minecraft:lime_candle", "minecraft:pink_candle", "minecraft:gray_candle",
        "minecraft:light_gray_candle", "minecraft:cyan_candle",
        "minecraft:purple_candle", "minecraft:blue_candle", "minecraft:brown_candle",
        "minecraft:green_candle", "minecraft:red_candle", "minecraft:black_candle",
        "minecraft:small_amethyst_bud", "minecraft:medium_amethyst_bud",
        "minecraft:large_amethyst_bud", "minecraft:amethyst_cluster",
        "minecraft:pointed_dripstone", "minecraft:ochre_froglight",
        "minecraft:verdant_froglight", "minecraft:pearlescent_froglight",
        "minecraft:sculk", "minecraft:sculk_vein", "minecraft:sculk_catalyst",
        "minecraft:sculk_shrieker", "minecraft:sculk_sensor",
        "minecraft:calibrated_sculk_sensor", "minecraft:pink_petals",
        "minecraft:cherry_leaves", "minecraft:cherry_log", "minecraft:cherry_wood",
        "minecraft:stripped_cherry_log", "minecraft:stripped_cherry_wood",
        "minecraft:cherry_planks", "minecraft:cherry_stairs",
        "minecraft:cherry_slab", "minecraft:cherry_fence",
        "minecraft:cherry_fence_gate", "minecraft:cherry_door",
        "minecraft:cherry_trapdoor", "minecraft:cherry_pressure_plate",
        "minecraft:cherry_button", "minecraft:cherry_sign",
        "minecraft:cherry_hanging_sign", "minecraft:bamboo_block",
        "minecraft:stripped_bamboo_block", "minecraft:bamboo_planks",
        "minecraft:bamboo_mosaic", "minecraft:bamboo_stairs",
        "minecraft:bamboo_slab", "minecraft:bamboo_fence",
        "minecraft:bamboo_fence_gate", "minecraft:bamboo_door",
        "minecraft:bamboo_trapdoor", "minecraft:bamboo_pressure_plate",
        "minecraft:bamboo_button", "minecraft:bamboo_sign",
        "minecraft:bamboo_hanging_sign", "minecraft:oak_chest_boat",
        "minecraft:spruce_chest_boat", "minecraft:birch_chest_boat",
        "minecraft:jungle_chest_boat", "minecraft:acacia_chest_boat",
        "minecraft:dark_oak_chest_boat", "minecraft:mangrove_chest_boat",
        "minecraft:cherry_chest_boat", "minecraft:bamboo_chest_raft",
        "minecraft:oak_boat", "minecraft:spruce_boat", "minecraft:birch_boat",
        "minecraft:jungle_boat", "minecraft:acacia_boat",
        "minecraft:dark_oak_boat", "minecraft:mangrove_boat",
        "minecraft:cherry_boat", "minecraft:bamboo_raft",
        "minecraft:minecart", "minecraft:chest_minecart",
        "minecraft:furnace_minecart", "minecraft:tnt_minecart",
        "minecraft:hopper_minecart", "minecraft:carrot_on_a_stick",
        "minecraft:warped_fungus_on_a_stick", "minecraft:elytra",
        "minecraft:oak_chest_boat", "minecraft:spruce_chest_boat",
        "minecraft:birch_chest_boat", "minecraft:jungle_chest_boat",
        "minecraft:acacia_chest_boat", "minecraft:dark_oak_chest_boat",
        "minecraft:mangrove_chest_boat", "minecraft:cherry_chest_boat",
        "minecraft:bamboo_chest_raft", "minecraft:turtle_helmet",
        "minecraft:scute", "minecraft:flint_and_steel", "minecraft:apple",
        "minecraft:bow", "minecraft:arrow", "minecraft:coal",
        "minecraft:charcoal", "minecraft:diamond", "minecraft:iron_ingot",
        "minecraft:gold_ingot", "minecraft:netherite_ingot",
        "minecraft:netherite_scrap", "minecraft:wooden_sword",
        "minecraft:wooden_shovel", "minecraft:wooden_pickaxe",
        "minecraft:wooden_axe", "minecraft:wooden_hoe", "minecraft:stone_sword",
        "minecraft:stone_shovel", "minecraft:stone_pickaxe",
        "minecraft:stone_axe", "minecraft:stone_hoe", "minecraft:golden_sword",
        "minecraft:golden_shovel", "minecraft:golden_pickaxe",
        "minecraft:golden_axe", "minecraft:golden_hoe", "minecraft:iron_sword",
        "minecraft:iron_shovel", "minecraft:iron_pickaxe", "minecraft:iron_axe",
        "minecraft:iron_hoe", "minecraft:diamond_sword",
        "minecraft:diamond_shovel", "minecraft:diamond_pickaxe",
        "minecraft:diamond_axe", "minecraft:diamond_hoe",
        "minecraft:netherite_sword", "minecraft:netherite_shovel",
        "minecraft:netherite_pickaxe", "minecraft:netherite_axe",
        "minecraft:netherite_hoe", "minecraft:stick", "minecraft:bowl",
        "minecraft:mushroom_stew", "minecraft:string", "minecraft:feather",
        "minecraft:gunpowder", "minecraft:wheat_seeds", "minecraft:wheat",
        "minecraft:bread", "minecraft:leather_helmet", "minecraft:leather_chestplate",
        "minecraft:leather_leggings", "minecraft:leather_boots",
        "minecraft:chainmail_helmet", "minecraft:chainmail_chestplate",
        "minecraft:chainmail_leggings", "minecraft:chainmail_boots",
        "minecraft:iron_helmet", "minecraft:iron_chestplate",
        "minecraft:iron_leggings", "minecraft:iron_boots",
        "minecraft:diamond_helmet", "minecraft:diamond_chestplate",
        "minecraft:diamond_leggings", "minecraft:diamond_boots",
        "minecraft:golden_helmet", "minecraft:golden_chestplate",
        "minecraft:golden_leggings", "minecraft:golden_boots",
        "minecraft:netherite_helmet", "minecraft:netherite_chestplate",
        "minecraft:netherite_leggings", "minecraft:netherite_boots",
        "minecraft:flint", "minecraft:porkchop", "minecraft:cooked_porkchop",
        "minecraft:painting", "minecraft:golden_apple",
        "minecraft:enchanted_golden_apple", "minecraft:oak_sign",
        "minecraft:spruce_sign", "minecraft:birch_sign", "minecraft:jungle_sign",
        "minecraft:acacia_sign", "minecraft:dark_oak_sign",
        "minecraft:mangrove_sign", "minecraft:cherry_sign",
        "minecraft:bamboo_sign", "minecraft:crimson_sign",
        "minecraft:warped_sign", "minecraft:bucket", "minecraft:water_bucket",
        "minecraft:lava_bucket", "minecraft:powder_snow_bucket",
        "minecraft:snowball", "minecraft:leather", "minecraft:milk_bucket",
        "minecraft:pufferfish_bucket", "minecraft:salmon_bucket",
        "minecraft:cod_bucket", "minecraft:tropical_fish_bucket",
        "minecraft:axolotl_bucket", "minecraft:tclad_bucket",
        "minecraft:brick", "minecraft:clay_ball", "minecraft:dried_kelp_block",
        "minecraft:paper", "minecraft:book", "minecraft:slime_ball",
        "minecraft:chest_minecart", "minecraft:furnace_minecart",
        "minecraft:egg", "minecraft:compass", "minecraft:fishing_rod",
        "minecraft:clock", "minecraft:glowstone_dust", "minecraft:cod",
        "minecraft:salmon", "minecraft:tropical_fish", "minecraft:pufferfish",
        "minecraft:cooked_cod", "minecraft:cooked_salmon", "minecraft:ink_sac",
        "minecraft:glow_ink_sac", "minecraft:cocoa_beans", "minecraft:white_dye",
        "minecraft:orange_dye", "minecraft:magenta_dye", "minecraft:light_blue_dye",
        "minecraft:yellow_dye", "minecraft:lime_dye", "minecraft:pink_dye",
        "minecraft:gray_dye", "minecraft:light_gray_dye", "minecraft:cyan_dye",
        "minecraft:purple_dye", "minecraft:blue_dye", "minecraft:brown_dye",
        "minecraft:green_dye", "minecraft:red_dye", "minecraft:black_dye",
        "minecraft:bone_meal", "minecraft:bone", "minecraft:sugar",
        "minecraft:cake", "minecraft:white_bed", "minecraft:orange_bed",
        "minecraft:magenta_bed", "minecraft:light_blue_bed",
        "minecraft:yellow_bed", "minecraft:lime_bed", "minecraft:pink_bed",
        "minecraft:gray_bed", "minecraft:light_gray_bed", "minecraft:cyan_bed",
        "minecraft:purple_bed", "minecraft:blue_bed", "minecraft:brown_bed",
        "minecraft:green_bed", "minecraft:red_bed", "minecraft:black_bed",
        "minecraft:cookie", "minecraft:filled_map", "minecraft:shears",
        "minecraft:melon_slice", "minecraft:dried_kelp", "minecraft:pumpkin_seeds",
        "minecraft:melon_seeds", "minecraft:beef", "minecraft:cooked_beef",
        "minecraft:chicken", "minecraft:cooked_chicken", "minecraft:rotten_flesh",
        "minecraft:ender_pearl", "minecraft:blaze_rod", "minecraft:ghast_tear",
        "minecraft:gold_nugget", "minecraft:nether_wart", "minecraft:potion",
        "minecraft:glass_bottle", "minecraft:spider_eye",
        "minecraft:fermented_spider_eye", "minecraft:blaze_powder",
        "minecraft:magma_cream", "minecraft:brewing_stand", "minecraft:cauldron",
        "minecraft:ender_eye", "minecraft:glistering_melon_slice",
        "minecraft:axolotl_spawn_egg", "minecraft:bat_spawn_egg",
        "minecraft:bee_spawn_egg", "minecraft:blaze_spawn_egg",
        "minecraft:cat_spawn_egg", "minecraft:cave_spider_spawn_egg",
        "minecraft:chicken_spawn_egg", "minecraft:cod_spawn_egg",
        "minecraft:cow_spawn_egg", "minecraft:creeper_spawn_egg",
        "minecraft:dolphin_spawn_egg", "minecraft:donkey_spawn_egg",
        "minecraft:drowned_spawn_egg", "minecraft:elder_guardian_spawn_egg",
        "minecraft:enderman_spawn_egg", "minecraft:endermite_spawn_egg",
        "minecraft:evoker_spawn_egg", "minecraft:fox_spawn_egg",
        "minecraft:frog_spawn_egg", "minecraft:ghast_spawn_egg",
        "minecraft:glow_squid_spawn_egg", "minecraft:goat_spawn_egg",
        "minecraft:guardian_spawn_egg", "minecraft:hoglin_spawn_egg",
        "minecraft:horse_spawn_egg", "minecraft:husk_spawn_egg",
        "minecraft:llama_spawn_egg", "minecraft:magma_cube_spawn_egg",
        "minecraft:mooshroom_spawn_egg", "minecraft:mule_spawn_egg",
        "minecraft:ocelot_spawn_egg", "minecraft:panda_spawn_egg",
        "minecraft:parrot_spawn_egg", "minecraft:phantom_spawn_egg",
        "minecraft:pig_spawn_egg", "minecraft:piglin_spawn_egg",
        "minecraft:piglin_brute_spawn_egg", "minecraft:pillager_spawn_egg",
        "minecraft:polar_bear_spawn_egg", "minecraft:pufferfish_spawn_egg",
        "minecraft:rabbit_spawn_egg", "minecraft:ravager_spawn_egg",
        "minecraft:salmon_spawn_egg", "minecraft:sheep_spawn_egg",
        "minecraft:shulker_spawn_egg", "minecraft:silverfish_spawn_egg",
        "minecraft:skeleton_spawn_egg", "minecraft:skeleton_horse_spawn_egg",
        "minecraft:slime_spawn_egg", "minecraft:spider_spawn_egg",
        "minecraft:squid_spawn_egg", "minecraft:stray_spawn_egg",
        "minecraft:strider_spawn_egg", "minecraft:tadpole_spawn_egg",
        "minecraft:trader_llama_spawn_egg", "minecraft:tropical_fish_spawn_egg",
        "minecraft:turtle_spawn_egg", "minecraft:vex_spawn_egg",
        "minecraft:villager_spawn_egg", "minecraft:vindicator_spawn_egg",
        "minecraft:wandering_trader_spawn_egg", "minecraft:witch_spawn_egg",
        "minecraft:wither_skeleton_spawn_egg", "minecraft:wolf_spawn_egg",
        "minecraft:zoglin_spawn_egg", "minecraft:zombie_spawn_egg",
        "minecraft:zombie_horse_spawn_egg", "minecraft:zombie_villager_spawn_egg",
        "minecraft:zombified_piglin_spawn_egg", "minecraft:experience_bottle",
        "minecraft:fire_charge", "minecraft:writable_book",
        "minecraft:written_book", "minecraft:emerald", "minecraft:item_frame",
        "minecraft:glow_item_frame", "minecraft:flower_pot", "minecraft:carrot",
        "minecraft:potato", "minecraft:baked_potato", "minecraft:poisonous_potato",
        "minecraft:map", "minecraft:golden_carrot", "minecraft:skeleton_skull",
        "minecraft:wither_skeleton_skull", "minecraft:player_head",
        "minecraft:zombie_head", "minecraft:creeper_head",
        "minecraft:dragon_head", "minecraft:nether_star", "minecraft:pumpkin_pie",
        "minecraft:firework_rocket", "minecraft:firework_star",
        "minecraft:enchanted_book", "minecraft:nether_brick",
        "minecraft:quartz", "minecraft:tnt_minecart", "minecraft:hopper_minecart",
        "minecraft:prismarine_shard", "minecraft:prismarine_crystals",
        "minecraft:rabbit", "minecraft:cooked_rabbit", "minecraft:rabbit_stew",
        "minecraft:rabbit_foot", "minecraft:rabbit_hide", "minecraft:armor_stand",
        "minecraft:iron_horse_armor", "minecraft:golden_horse_armor",
        "minecraft:diamond_horse_armor", "minecraft:leather_horse_armor",
        "minecraft:lead", "minecraft:name_tag", "minecraft:command_block_minecart",
        "minecraft:mutton", "minecraft:cooked_mutton", "minecraft:white_banner",
        "minecraft:orange_banner", "minecraft:magenta_banner",
        "minecraft:light_blue_banner", "minecraft:yellow_banner",
        "minecraft:lime_banner", "minecraft:pink_banner", "minecraft:gray_banner",
        "minecraft:light_gray_banner", "minecraft:cyan_banner",
        "minecraft:purple_banner", "minecraft:blue_banner", "minecraft:brown_banner",
        "minecraft:green_banner", "minecraft:red_banner", "minecraft:black_banner",
        "minecraft:end_crystal", "minecraft:chorus_fruit",
        "minecraft:popped_chorus_fruit", "minecraft:beetroot",
        "minecraft:beetroot_seeds", "minecraft:beetroot_soup",
        "minecraft:dragon_breath", "minecraft:splash_potion", "minecraft:spectral_arrow",
        "minecraft:tipped_arrow", "minecraft:lingering_potion",
        "minecraft:shield", "minecraft:elytra", "minecraft:spruce_boat",
        "minecraft:birch_boat", "minecraft:jungle_boat", "minecraft:acacia_boat",
        "minecraft:dark_oak_boat", "minecraft:mangrove_boat", "minecraft:cherry_boat",
        "minecraft:bamboo_raft", "minecraft:totem_of_undying", "minecraft:shulker_shell",
        "minecraft:iron_nugget", "minecraft:knowledge_book",
        "minecraft:debug_stick", "minecraft:music_disc_13",
        "minecraft:music_disc_cat", "minecraft:music_disc_blocks",
        "minecraft:music_disc_chirp", "minecraft:music_disc_far",
        "minecraft:music_disc_mall", "minecraft:music_disc_mellohi",
        "minecraft:music_disc_stal", "minecraft:music_disc_strad",
        "minecraft:music_disc_ward", "minecraft:music_disc_11",
        "minecraft:music_disc_wait", "minecraft:music_disc_otherside",
        "minecraft:music_disc_5", "minecraft:music_disc_pigstep",
        "minecraft:disc_fragment_5", "minecraft:trident",
        "minecraft:phantom_membrane", "minecraft:nautilus_shell",
        "minecraft:heart_of_the_sea", "minecraft:crossbow", "minecraft:suspicious_stew",
        "minecraft:loom", "minecraft:flower_banner_pattern",
        "minecraft:creeper_banner_pattern", "minecraft:skull_banner_pattern",
        "minecraft:mojang_banner_pattern", "minecraft:globe_banner_pattern",
        "minecraft:piglin_banner_pattern", "minecraft:goat_horn",
        "minecraft:composter", "minecraft:barrel", "minecraft:smoker",
        "minecraft:blast_furnace", "minecraft:cartography_table",
        "minecraft:fletching_table", "minecraft:grindstone",
        "minecraft:smithing_table", "minecraft:stonecutter",
        "minecraft:netherite_upgrade_smithing_template",
        "minecraft:sentry_armor_trim_smithing_template",
        "minecraft:dune_armor_trim_smithing_template",
        "minecraft:coast_armor_trim_smithing_template",
        "minecraft:wild_armor_trim_smithing_template",
        "minecraft:ward_armor_trim_smithing_template",
        "minecraft:eye_armor_trim_smithing_template",
        "minecraft:vex_armor_trim_smithing_template",
        "minecraft:tide_armor_trim_smithing_template",
        "minecraft:snout_armor_trim_smithing_template",
        "minecraft:rib_armor_trim_smithing_template",
        "minecraft:spire_armor_trim_smithing_template",
        "minecraft:wayfinder_armor_trim_smithing_template",
        "minecraft:shaper_armor_trim_smithing_template",
        "minecraft:silence_armor_trim_smithing_template",
        "minecraft:raiser_armor_trim_smithing_template",
        "minecraft:host_armor_trim_smithing_template",
        "minecraft:bolt_armor_trim_smithing_template",
        "minecraft:flow_armor_trim_smithing_template",
        "minecraft:music_disc_relic", "minecraft:brush", "minecraft:pottery_sherd",
        "minecraft:prize_pottery_sherd", "minecraft:arms_up_pottery_sherd",
        "minecraft:skull_pottery_sherd", "minecraft:angler_pottery_sherd",
        "minecraft:shelter_pottery_sherd", "minecraft:snort_pottery_sherd",
        "minecraft:blade_pottery_sherd", "minecraft:brewer_pottery_sherd",
        "minecraft:burn_pottery_sherd", "minecraft:danger_pottery_sherd",
        "minecraft:explorer_pottery_sherd", "minecraft:friend_pottery_sherd",
        "minecraft:heart_pottery_sherd", "minecraft:heartbreak_pottery_sherd",
        "minecraft:howl_pottery_sherd", "minecraft:miner_pottery_sherd",
        "minecraft:mourner_pottery_sherd", "minecraft:plenty_pottery_sherd",
        "minecraft:prize_pottery_sherd", "minecraft:sheaf_pottery_sherd",
        "minecraft:snort_pottery_sherd", "minecraft:netherite_sword",
    }
    all_items.update(vanilla_items)
    mod_items_map["minecraft"] = vanilla_items
    
    if not os.path.exists(mods_dir):
        return all_items, mod_items_map
    
    for jar_file in Path(mods_dir).glob("*.jar"):
        mod_info = get_mod_info_from_jar(jar_file)
        mod_id = mod_info["mod_id"]
        
        # 只扫描目标模组中存在的模组
        if mod_id in target_mods:
            items = get_items_from_mod_jar(jar_file)
            if items:
                mod_items_map[mod_id] = items
                all_items.update(items)
    
    return all_items, mod_items_map


def check_items_existence(mod_items, available_items):
    """检查物品是否存在于目标模组中"""
    existing_items = {}
    missing_items = {}
    
    for mod_id, items in mod_items.items():
        existing_items[mod_id] = []
        missing_items[mod_id] = []
        
        for item in items:
            item_id = item["id"]
            # 检查物品是否存在于扫描到的物品列表中
            if item_id in available_items:
                existing_items[mod_id].append(item)
            else:
                missing_items[mod_id].append(item)
    
    return existing_items, missing_items


def parse_snbt_by_mod(filepath):
    """解析 SNBT，按模组分类所有物品（兼容旧版）"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    entries = re.split(r'\{\s*entryUUID:', content)
    mod_items = {}
    
    for entry in entries[1:]:
        item_match = re.search(r'id:\s*"([a-z_]+):([a-z_]+)"', entry)
        if not item_match:
            continue
        
        mod_id = item_match.group(1)
        item_id = item_match.group(2)
        full_id = f"{mod_id}:{item_id}"
        
        if full_id == "minecraft:barrier":
            continue
        
        count_match = re.search(r'Count:\s*(\d+)b', entry)
        count = int(count_match.group(1)) if count_match else 1
        
        price_match = re.search(r'entryPrice:\s*(\d+)L', entry)
        price = int(price_match.group(1)) if price_match else 1
        
        is_sell_match = re.search(r'isSell:\s*(\d+)b', entry)
        is_sell = int(is_sell_match.group(1)) if is_sell_match else 0
        
        item_data = {
            "id": full_id,
            "count": count,
            "price": price,
            "is_sell": is_sell
        }
        
        if mod_id not in mod_items:
            mod_items[mod_id] = []
        mod_items[mod_id].append(item_data)
    
    return mod_items


def parse_snbt_by_category(filepath):
    """解析 SNBT，按原有分类提取数据"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    categories = []
    
    # 找到所有 tabEntry 块（每个分类）
    pos = 0
    while True:
        # 找到下一个 tabEntry
        tab_entry_pos = content.find('tabEntry:', pos)
        if tab_entry_pos == -1:
            break
        
        # 找到这个分类块的开始（从上一个 { 开始）
        block_start = content.rfind('{', 0, tab_entry_pos)
        if block_start == -1:
            pos = tab_entry_pos + 1
            continue
        
        # 找到这个分类块的结束（匹配的 }）
        brace_count = 1
        block_end = block_start + 1
        while brace_count > 0 and block_end < len(content):
            if content[block_end] == '{':
                brace_count += 1
            elif content[block_end] == '}':
                brace_count -= 1
            block_end += 1
        
        block_content = content[block_start:block_end]
        
        # 提取 title
        title_match = re.search(r'title:\s*"([^"]+)"', block_content)
        if not title_match:
            pos = tab_entry_pos + 1
            continue
        
        title = title_match.group(1)
        
        # 提取 icon（支持多行格式，id 值可能有引号也可能没有）
        # 匹配分类级别的 icon（在 tabEntry 之后，与 title 同级）
        # 使用正则表达式确保找到的是分类级别的 icon，而不是条目级别的 icon
        # 查找 tabEntry 块之后的 icon
        icon_match = re.search(r'tabEntry:\s*\[[\s\S]*?\]\s*icon:\s*\{[\s\S]*?id:\s*([^\s]+)[\s\S]*?\}', block_content)
        if icon_match:
            icon = icon_match.group(1)
            # 移除可能的引号
            if icon.startswith('"') or icon.startswith("'"):
                icon = icon[1:-1]
        else:
            # 如果找不到，使用默认图标
            icon = "minecraft:grass_block"
        
        # 提取 tabEntry 中的物品
        items = []
        
        # 找到 tabEntry: [ ... ]
        tab_entry_match = re.search(r'tabEntry:\s*\[([\s\S]*?)\]\s*(?:icon|title|description|tabCondition|shopTabUUID)', block_content)
        if tab_entry_match:
            tab_entry_content = tab_entry_match.group(1)
            
            # 找到每个条目 { ... }
            entry_pos = 0
            while entry_pos < len(tab_entry_content):
                entry_start = tab_entry_content.find('{', entry_pos)
                if entry_start == -1:
                    break
                
                # 找到匹配的 }
                brace_count = 1
                entry_end = entry_start + 1
                while brace_count > 0 and entry_end < len(tab_entry_content):
                    if tab_entry_content[entry_end] == '{':
                        brace_count += 1
                    elif tab_entry_content[entry_end] == '}':
                        brace_count -= 1
                    entry_end += 1
                
                entry_content = tab_entry_content[entry_start:entry_end]
                
                # 提取物品信息
                id_match = re.search(r'entryType:\s*\{[^}]*itemStack:\s*\{[^}]*id:\s*"([^"]+)"', entry_content)
                if id_match:
                    full_id = id_match.group(1)
                else:
                    id_match = re.search(r'id:\s*"([^"]+)"', entry_content)
                    if id_match:
                        full_id = id_match.group(1)
                    else:
                        entry_pos = entry_end
                        continue
                
                if full_id == "minecraft:barrier":
                    entry_pos = entry_end
                    continue
                
                # 提取 Count
                count_match = re.search(r'Count:\s*(\d+)b', entry_content)
                count = int(count_match.group(1)) if count_match else 1
                
                # 提取 entryPrice
                price_match = re.search(r'entryPrice:\s*(\d+)L?', entry_content)
                price = int(price_match.group(1)) if price_match else 1
                
                # 提取 isSell
                is_sell_match = re.search(r'isSell:\s*(\d+)b', entry_content)
                is_sell = int(is_sell_match.group(1)) if is_sell_match else 0
                
                item_data = {
                    "id": full_id,
                    "count": count,
                    "price": price,
                    "is_sell": is_sell
                }
                items.append(item_data)
                entry_pos = entry_end
        
        if items:
            categories.append({
                'title': title,
                'icon': icon,
                'items': items
            })
        
        pos = block_end
    
    return categories


def save_mod_comparison(source_mods, target_mods, source_dir, target_dir):
    """保存模组对比结果到文件，并检测同名不同作者的情况"""
    filename = os.path.join("3.报告", "模组对比.txt")
    
    # 获取 mod_id 集合
    source_ids = set(source_mods.keys())
    target_ids = set(target_mods.keys())
    
    both_have_ids = source_ids & target_ids
    only_source_ids = source_ids - target_ids
    only_target_ids = target_ids - source_ids
    
    # 检测同名不同作者的模组
    author_mismatches = []
    for mod_id in both_have_ids:
        source_author = source_mods[mod_id].get("author", "未知")
        target_author = target_mods[mod_id].get("author", "未知")
        source_version = source_mods[mod_id].get("version", "未知")
        target_version = target_mods[mod_id].get("version", "未知")
        
        # 作者不同或者版本差异很大时警告
        if source_author != target_author:
            author_mismatches.append({
                "mod_id": mod_id,
                "source_author": source_author,
                "target_author": target_author,
                "source_version": source_version,
                "target_version": target_version,
                "source_name": source_mods[mod_id].get("name", mod_id),
                "target_name": target_mods[mod_id].get("name", mod_id)
            })
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("模组对比\n")
        f.write("-"*50 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"原目录: {source_dir}\n")
        f.write(f"目标目录: {target_dir}\n")
        f.write("-"*50 + "\n\n")
        
        # 关键信息概览
        f.write("【概览】\n")
        f.write(f"✅ 共通模组: {len(both_have_ids)} 个\n")
        f.write(f"⚠️  目标缺少: {len(only_source_ids)} 个\n")
        f.write(f"❓ 目标新增: {len(only_target_ids)} 个\n")
        if author_mismatches:
            f.write(f"🔄 同名异作者: {len(author_mismatches)} 个\n")
        f.write("\n")
        
        # 同名不同作者警告（如果有）
        if author_mismatches:
            f.write("【需要注意的模组】\n")
            f.write("-"*50 + "\n")
            
            # 显示所有同名不同作者的模组
            for idx, mismatch in enumerate(author_mismatches, 1):
                f.write(f"{idx}. {mismatch['mod_id']}\n")
                f.write(f"   原作者: {mismatch['source_author']}\n")
                f.write(f"   目标作者: {mismatch['target_author']}\n")
                f.write(f"   版本: {mismatch['source_version']} → {mismatch['target_version']}\n\n")
            f.write("\n")
        
        # 总结
        f.write("【总结】\n")
        f.write("-"*50 + "\n")
        f.write(f"可正常提取: {len(both_have_ids)} 个模组\n")
        f.write(f"可能需要检查: {len(author_mismatches)} 个模组\n")
        f.write(f"提取后可能缺失: {len(only_source_ids)} 个模组的内容\n")
        f.write("-"*50 + "\n")
    
    return filename, both_have_ids, only_source_ids, only_target_ids, author_mismatches


def save_missing_items(missing_items_by_category, total_missing):
    """保存缺失的物品信息到单独的文件"""
    filename = os.path.join("3.报告", "缺失物品.txt")
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("缺失物品\n")
        f.write("-"*50 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总缺失物品数: {total_missing}\n")
        f.write("-"*50 + "\n\n")
        
        # 按分类显示缺失物品
        for category_name, items in missing_items_by_category.items():
            if items:
                f.write(f"【{category_name}】 ({len(items)}个缺失)\n")
                f.write("-"*40 + "\n")
                
                # 按模组分组
                items_by_mod = {}
                for item in items:
                    mod_id = item['id'].split(':')[0]
                    if mod_id not in items_by_mod:
                        items_by_mod[mod_id] = []
                    items_by_mod[mod_id].append(item)
                
                # 显示每个模组的缺失物品
                for mod_id, mod_items in items_by_mod.items():
                    f.write(f"{mod_id}: {len(mod_items)}个\n")
                    for idx, item in enumerate(mod_items, 1):
                        f.write(f"  {idx}. {item['id']} x{item['count']} (价格: {item['price']})\n")
                
                f.write("\n")
        
        # 总结
        f.write("【总结】\n")
        f.write("-"*50 + "\n")
        f.write(f"缺失物品分类数: {len([c for c in missing_items_by_category.values() if c])}\n")
        f.write(f"总缺失物品数: {total_missing}\n")
        f.write("\n")
        f.write("这些物品在目标模组中不存在，已被排除在提取结果之外。\n")
        f.write("-"*50 + "\n")
    
    return filename


def create_shopproj_item(item):
    """创建 shopproj 格式的商人条目"""
    return {
        "_type": "compound",
        "xp": {"_type": "int", "_value": 0},
        "tradeType": {
            "_type": "string",
            "_value": "viscript_shop.data.merchant.tradeType.sell" if item["is_sell"] else "viscript_shop.data.merchant.tradeType.buy"
        },
        "command": {"_type": "string", "_value": ""},
        "itemResult": {
            "_type": "compound",
            "id": {"_type": "string", "_value": item["id"]},
            "count": {"_type": "int", "_value": item["count"]}
        },
        "itemB": {"_type": "compound"},
        "itemA": {"_type": "compound"},
        "stage": {"_type": "int", "_value": 0},
        "money": {"_type": "int", "_value": item["price"]}
    }


def create_category(name, icon_id, merchants_list):
    """创建一个新的分类"""
    return {
        "_type": "compound",
        "iconItem": {
            "_type": "compound",
            "id": {"_type": "string", "_value": icon_id},
            "count": {"_type": "int", "_value": 1}
        },
        "iconType": {"_type": "string", "_value": "viscript_shop.data.category.iconType.item"},
        "name": {"_type": "string", "_value": name},
        "merchants": {
            "_type": "compound",
            "payload": {
                "_type": "list",
                "_element_type": "compound",
                "_value": merchants_list
            },
            "uid": {"_type": "int", "_value": len(merchants_list)}
        },
        "shopType": {"_type": "string", "_value": "viscript_shop.data.category.shopType.currency"},
        "iconTexture": {"_type": "string", "_value": ""}
    }


def get_process_dir():
    """获取过程文件夹的路径"""
    # 创建1.过程文件夹
    process_dir = "1.过程"
    os.makedirs(process_dir, exist_ok=True)
    
    return process_dir


def ensure_directories():
    """确保必要的文件夹结构存在"""
    # 创建1.过程文件夹
    os.makedirs("1.过程", exist_ok=True)
    # 创建2.输出文件夹
    os.makedirs("2.输出", exist_ok=True)
    # 创建3.报告文件夹
    os.makedirs("3.报告", exist_ok=True)


# ==================== GUI 界面 ====================

class ViScriptShopToolkitGUI:
    """ViScript Shop 工具箱 GUI 界面"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("SDM 商店转 ViScriptShop 工具")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # 确保文件夹结构存在
        ensure_directories()
        
        # 全局缓存变量
        self.DIR_CACHE = {}
        self.MODS_CACHE = {}  # {dir_path: (mods_dict, timestamp)}
        self.ITEMS_CACHE = {}  # {dir_path: (available_items, mod_items_map, timestamp)}
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建 SDM 转 ViScriptShop 界面
        self.create_sdm_interface()
        
    def create_sdm_interface(self):
        """创建 SDM 商店转 ViScriptShop 界面"""
        # 创建原模组目录选择
        source_frame = ttk.LabelFrame(self.main_frame, text="原整合包目录", padding="10")
        source_frame.pack(fill=tk.X, pady=5)
        
        self.source_dir_var = tk.StringVar()
        source_entry = ttk.Entry(source_frame, textvariable=self.source_dir_var, width=60)
        source_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        source_button = ttk.Button(source_frame, text="浏览", command=self.browse_source_dir)
        source_button.pack(side=tk.RIGHT, padx=5)
        
        # 创建目标模组目录选择
        target_frame = ttk.LabelFrame(self.main_frame, text="目标整合包目录", padding="10")
        target_frame.pack(fill=tk.X, pady=5)
        
        self.target_dir_var = tk.StringVar()
        target_entry = ttk.Entry(target_frame, textvariable=self.target_dir_var, width=60)
        target_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        target_button = ttk.Button(target_frame, text="浏览", command=self.browse_target_dir)
        target_button.pack(side=tk.RIGHT, padx=5)
        
        # 创建执行按钮
        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        execute_button = ttk.Button(button_frame, text="开始转换", command=self.execute_sdm_conversion)
        execute_button.pack(side=tk.LEFT, padx=5)
        
        # 创建日志文本框
        log_frame = ttk.LabelFrame(self.main_frame, text="转换日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.sdm_log_text = tk.Text(log_frame, height=15, wrap=tk.WORD)
        self.sdm_log_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.sdm_log_text, command=self.sdm_log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.sdm_log_text.config(yscrollcommand=scrollbar.set)
    
    def browse_source_dir(self):
        """浏览原整合包目录"""
        dir_path = filedialog.askdirectory(
            title="选择原整合包目录 (sdmshop.snbt 来源)"
        )
        if dir_path:
            self.source_dir_var.set(dir_path)
    
    def browse_target_dir(self):
        """浏览目标整合包目录"""
        dir_path = filedialog.askdirectory(
            title="选择目标整合包目录 (要生成 ViScriptShop 商店文件的整合包)"
        )
        if dir_path:
            self.target_dir_var.set(dir_path)
    
    def execute_sdm_conversion(self):
        """执行 SDM 商店转 ViScriptShop 转换"""
        import time
        
        # 获取目录路径
        source_base_dir = self.source_dir_var.get()
        target_base_dir = self.target_dir_var.get()
        
        if not source_base_dir:
            messagebox.showerror("错误", "请选择原整合包目录")
            return
        
        if not target_base_dir:
            messagebox.showerror("错误", "请选择目标整合包目录")
            return
        
        # 自动寻找 mods 文件夹
        def find_mods_folder(base_dir):
            mods_path = os.path.join(base_dir, "mods")
            if os.path.exists(mods_path) and os.path.isdir(mods_path):
                return mods_path
            return base_dir
        
        source_dir = find_mods_folder(source_base_dir)
        target_dir = find_mods_folder(target_base_dir)
        
        # 保存到缓存
        self.DIR_CACHE['source_dir'] = source_dir
        self.DIR_CACHE['target_dir'] = target_dir
        
        try:
            # 清空日志
            self.sdm_log_text.delete(1.0, tk.END)
            
            # 确保 sdmshop.snbt 文件存在
            snbt_file = "sdmshop.snbt"
            if not os.path.exists(snbt_file):
                messagebox.showerror("错误", f"找不到 sdmshop.snbt 文件，请确保该文件在当前目录")
                return
            
            # 开始转换过程
            self.sdm_log_text.insert(tk.END, "开始执行 SDM 商店转 ViScriptShop 转换...\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            self.sdm_log_text.insert(tk.END, f"原模组目录: {source_dir}\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            self.sdm_log_text.insert(tk.END, f"目标模组目录: {target_dir}\n\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            
            # 1. 扫描原模组目录
            self.sdm_log_text.insert(tk.END, "1. 扫描原模组目录...\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            if source_dir in self.MODS_CACHE:
                source_mods = self.MODS_CACHE[source_dir][0]
                self.sdm_log_text.insert(tk.END, f"   使用缓存的扫描结果: {len(source_mods)} 个模组/库\n")
                self.sdm_log_text.see(tk.END)
                self.root.update()
            else:
                source_mods = get_installed_mods(source_dir)
                self.MODS_CACHE[source_dir] = (source_mods, time.time())
                self.sdm_log_text.insert(tk.END, f"   原模组目录发现 {len(source_mods)} 个模组/库\n")
                self.sdm_log_text.see(tk.END)
                self.root.update()
            
            # 2. 扫描目标模组目录
            self.sdm_log_text.insert(tk.END, "\n2. 扫描目标模组目录...\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            if target_dir in self.MODS_CACHE:
                target_mods = self.MODS_CACHE[target_dir][0]
                self.sdm_log_text.insert(tk.END, f"   使用缓存的扫描结果: {len(target_mods)} 个模组/库\n")
                self.sdm_log_text.see(tk.END)
                self.root.update()
            else:
                target_mods = get_installed_mods(target_dir)
                self.MODS_CACHE[target_dir] = (target_mods, time.time())
                self.sdm_log_text.insert(tk.END, f"   目标目录发现 {len(target_mods)} 个模组/库\n")
                self.sdm_log_text.see(tk.END)
                self.root.update()
            
            # 3. 对比模组目录
            self.sdm_log_text.insert(tk.END, "\n3. 对比模组目录...\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            comparison_file, both_have, only_source, only_target, author_mismatches = save_mod_comparison(
                source_mods, target_mods, source_dir, target_dir
            )
            self.sdm_log_text.insert(tk.END, f"   模组对比已保存: {comparison_file}\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            self.sdm_log_text.insert(tk.END, f"   ✅ 两边都有: {len(both_have)} 个\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            self.sdm_log_text.insert(tk.END, f"   ⚠️  只有原模组有: {len(only_source)} 个\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            self.sdm_log_text.insert(tk.END, f"   ❓ 只有目标有: {len(only_target)} 个\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            
            # 4. 扫描目标模组中的物品
            self.sdm_log_text.insert(tk.END, "\n4. 扫描目标模组中的物品...\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            if target_dir in self.ITEMS_CACHE:
                available_items, mod_items_map = self.ITEMS_CACHE[target_dir][0], self.ITEMS_CACHE[target_dir][1]
                self.sdm_log_text.insert(tk.END, f"   使用缓存的扫描结果: {len(available_items)} 个可用物品\n")
                self.sdm_log_text.see(tk.END)
                self.root.update()
            else:
                available_items, mod_items_map = scan_all_items_from_mods(target_dir, target_mods)
                self.ITEMS_CACHE[target_dir] = (available_items, mod_items_map, time.time())
                self.sdm_log_text.insert(tk.END, f"   扫描到 {len(available_items)} 个可用物品\n")
                self.sdm_log_text.see(tk.END)
                self.root.update()
            
            # 5. 解析 sdmshop.snbt
            self.sdm_log_text.insert(tk.END, "\n5. 解析 sdmshop.snbt...\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            categories_data = parse_snbt_by_category("sdmshop.snbt")
            self.sdm_log_text.insert(tk.END, f"   发现 {len(categories_data)} 个原有分类\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            
            # 6. 检查物品存在性
            self.sdm_log_text.insert(tk.END, "\n6. 检查物品存在性...\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            filtered_categories = []
            total_existing = 0
            total_missing = 0
            missing_items_by_category = {}
            
            # 获取可用的模组 ID 列表
            available_mods_set = set(target_mods.keys())
            
            for cat in categories_data:
                title = cat['title']
                icon = cat['icon']
                items = cat['items']
                
                # 检查图标模组是否存在
                icon_mod_id = icon.split(':')[0]
                if icon_mod_id not in available_mods_set:
                    # 图标模组不存在，替换为屏障方块
                    icon = "minecraft:barrier"
                
                existing_items = []
                missing_items = []
                
                for item in items:
                    # 检查是否为原版物品
                    item_mod_id = item['id'].split(':')[0]
                    if item_mod_id == 'minecraft' or item['id'] in available_items:
                        existing_items.append(item)
                        total_existing += 1
                    else:
                        missing_items.append(item)
                        total_missing += 1
                
                # 保存缺失物品信息
                missing_items_by_category[title] = missing_items
                
                if existing_items:
                    filtered_categories.append({
                        'title': title,
                        'icon': icon,
                        'items': existing_items
                    })
            
            # 显示分类状态
            self.sdm_log_text.insert(tk.END, "   分类状态:\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            for idx, cat in enumerate(filtered_categories, 1):
                title = cat['title']
                existing_count = len(cat['items'])
                
                # 找到对应的原始分类，计算缺失数量
                original_cat = next((c for c in categories_data if c['title'] == title), None)
                missing_count = 0
                if original_cat:
                    missing_count = len([item for item in original_cat['items'] if item['id'] not in available_items])
                
                if missing_count > 0:
                    self.sdm_log_text.insert(tk.END, f"      {idx}. {title}: {existing_count}个可用, {missing_count}个缺失 (图标: {cat['icon']})\n")
                    self.sdm_log_text.see(tk.END)
                    self.root.update()
                else:
                    self.sdm_log_text.insert(tk.END, f"      {idx}. {title}: {existing_count}个可用, 0个缺失 (图标: {cat['icon']})\n")
                    self.sdm_log_text.see(tk.END)
                    self.root.update()
            
            self.sdm_log_text.insert(tk.END, f"   ✅ 存在的物品: {total_existing} 个\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            if total_missing > 0:
                self.sdm_log_text.insert(tk.END, f"   ⚠️  排除缺失物品: {total_missing} 个 (这些物品在目标模组中不存在)\n")
                self.sdm_log_text.see(tk.END)
                self.root.update()
            
            # 7. 构建商店
            self.sdm_log_text.insert(tk.END, "\n7. 构建商店...\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            categories = []
            
            for cat in filtered_categories:
                title = cat['title']
                icon = cat['icon']
                items = cat['items'][:30]  # 每个分类最多30个物品
                
                merchants = [create_shopproj_item(item) for item in items]
                
                categories.append(create_category(title, icon, merchants))
                self.sdm_log_text.insert(tk.END, f"   ✓ 添加 {title} 分类 ({len(merchants)} 个物品)\n")
                self.sdm_log_text.see(tk.END)
                self.root.update()
            
            # 8. 生成配置文件
            self.sdm_log_text.insert(tk.END, "\n8. 生成配置文件...\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            shopproj = {
                "_root_name": "",
                "_root_type": "compound",
                "data": {
                    "_type": "compound",
                    "meta": {
                        "_type": "compound",
                        "version_num": {"_type": "int", "_value": 1},
                        "suffix": {"_type": "string", "_value": ".shopproj"},
                        "version": {"_type": "string", "_value": "1.0"},
                        "name": {"_type": "string", "_value": "商店项目"}
                    },
                    "data": {
                        "_type": "compound",
                        "shop": {
                            "_type": "compound",
                            "lockedMerchantVisibility": {"_type": "string", "_value": "viscript_shop.data.shop.lockedItemVisibility.show_with_lock"},
                            "isQuickOpening": {"_type": "byte", "_value": 0},
                            "name": {"_type": "string", "_value": ""},
                            "stage": {"_type": "int", "_value": 0},
                            "categoryInfos": {
                                "_type": "compound",
                                "payload": {
                                    "_type": "list",
                                    "_element_type": "compound",
                                    "_value": categories
                                },
                                "uid": {"_type": "int", "_value": len(categories)}
                            }
                        }
                    }
                }
            }
            
            # 使用默认文件名，保存到过程文件夹
            process_dir = get_process_dir()
            json_file = os.path.join(process_dir, "extracted_shop_by_category.shopproj.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(shopproj, f, ensure_ascii=False, indent=2)
            
            self.sdm_log_text.insert(tk.END, f"   ✓ JSON 文件已保存: {json_file}\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            
            # 9. 替换 minecraft:scute 为 minecraft:turtle_scute
            self.sdm_log_text.insert(tk.END, "\n9. 检测并替换物品 ID...\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            
            def replace_scute(obj):
                """递归替换 minecraft:scute 为 minecraft:turtle_scute"""
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key == "_value" and value == "minecraft:scute":
                            obj[key] = "minecraft:turtle_scute"
                            self.sdm_log_text.insert(tk.END, "   ✓ 替换 minecraft:scute 为 minecraft:turtle_scute\n")
                            self.sdm_log_text.see(tk.END)
                            self.root.update()
                        else:
                            replace_scute(value)
                elif isinstance(obj, list):
                    for item in obj:
                        replace_scute(item)
            
            # 加载 JSON 文件并替换
            with open(json_file, 'r', encoding='utf-8') as f:
                shopproj_data = json.load(f)
            
            replace_scute(shopproj_data)
            
            # 保存修改后的 JSON 文件
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(shopproj_data, f, ensure_ascii=False, indent=2)
            
            self.sdm_log_text.insert(tk.END, "   ✓ 物品 ID 替换完成\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            
            # 10. 自动转换为 NBT
            self.sdm_log_text.insert(tk.END, "\n10. 转换为 NBT 格式...\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            nbt_file = os.path.join("2.输出", "extracted_shop_by_category.shopproj")
            try:
                json_to_nbt(json_file, nbt_file, compress=False)
                self.sdm_log_text.insert(tk.END, f"   ✓ NBT 文件已生成: {nbt_file}\n")
                self.sdm_log_text.see(tk.END)
                self.root.update()
            except Exception as e:
                self.sdm_log_text.insert(tk.END, f"   ✗ 转换 NBT 失败: {e}\n")
                self.sdm_log_text.see(tk.END)
                self.root.update()
                nbt_file = None
            
            # 保存缺失物品
            missing_file = None
            if total_missing > 0:
                missing_file = save_missing_items(missing_items_by_category, total_missing)
                self.sdm_log_text.insert(tk.END, f"   📄 缺失物品已保存: {missing_file}\n")
                self.sdm_log_text.see(tk.END)
                self.root.update()
            
            # 完成提示
            self.sdm_log_text.insert(tk.END, "\n" + "="*70 + "\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            self.sdm_log_text.insert(tk.END, "✅ 完成！\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            self.sdm_log_text.insert(tk.END, f"   JSON 文件: {json_file}\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            if nbt_file:
                self.sdm_log_text.insert(tk.END, f"   NBT 文件: {nbt_file}\n")
                self.sdm_log_text.see(tk.END)
                self.root.update()
            self.sdm_log_text.insert(tk.END, f"   分类数: {len(categories)}\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            total_items = sum(len(c['merchants']['payload']['_value']) for c in categories)
            self.sdm_log_text.insert(tk.END, f"   总物品数: {total_items}\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            self.sdm_log_text.insert(tk.END, f"   模组对比: {comparison_file}\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            if total_missing > 0:
                self.sdm_log_text.insert(tk.END, f"   缺失物品: {missing_file}\n")
                self.sdm_log_text.see(tk.END)
                self.root.update()
            self.sdm_log_text.insert(tk.END, "="*70 + "\n")
            self.sdm_log_text.see(tk.END)
            self.root.update()
            
            messagebox.showinfo("成功", "SDM 商店转 ViScriptShop 转换完成！")
            
        except Exception as e:
            error_msg = f"转换失败: {str(e)}"
            self.sdm_log_text.insert(tk.END, error_msg + "\n")
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", error_msg)


def main():
    """主函数"""
    root = tk.Tk()
    app = ViScriptShopToolkitGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()