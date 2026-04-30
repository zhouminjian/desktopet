"""
数据持久化模块
保存和读取宠物数据到JSON文件
"""

import json
import os
from datetime import datetime
from typing import Optional
from pathlib import Path


class PetDatabase:
    """
    宠物存档管理器
    处理宠物数据的保存和加载
    """
    
    SAVE_FILENAME = "pii_save.json"
    
    def __init__(self):
        """初始化数据库"""
        self._save_path = self._get_save_path()
    
    def _get_save_path(self) -> Path:
        """获取存档文件路径"""
        # 优先使用应用数据目录
        if os.name == 'nt':  # Windows
            app_data = os.environ.get('APPDATA', '')
            if app_data:
                save_dir = Path(app_data) / "DesktopPet"
            else:
                save_dir = Path.home() / ".desktoppet"
        else:  # Linux/Mac
            save_dir = Path.home() / ".desktoppet"
        
        # 确保目录存在
        save_dir.mkdir(parents=True, exist_ok=True)
        
        return save_dir / self.SAVE_FILENAME
    
    def save(self, data: dict) -> bool:
        """
        保存宠物数据
        
        Args:
            data: 宠物数据字典
        
        Returns:
            bool: 是否成功保存
        """
        try:
            # 添加存档元数据
            save_data = {
                "version": "1.0",
                "saved_at": datetime.now().isoformat(),
                "pet_data": data
            }
            
            # 写入文件
            with open(self._save_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            print(f"[存档] 已保存到: {self._save_path}")
            return True
            
        except Exception as e:
            print(f"[存档] 保存失败: {e}")
            return False
    
    def load(self) -> Optional[dict]:
        """
        加载宠物数据
        
        Returns:
            dict: 宠物数据，如果不存在或失败则返回None
        """
        try:
            if not self._save_path.exists():
                print("[存档] 无存档文件")
                return None
            
            with open(self._save_path, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
            
            # 提取宠物数据
            pet_data = save_data.get("pet_data")
            if pet_data:
                saved_time = save_data.get("saved_at", "未知")
                print(f"[存档] 已加载 (存档时间: {saved_time})")
                return pet_data
            
            return None
            
        except json.JSONDecodeError as e:
            print(f"[存档] 存档文件损坏: {e}")
            return None
        except Exception as e:
            print(f"[存档] 加载失败: {e}")
            return None
    
    def has_save(self) -> bool:
        """检查是否存在存档"""
        return self._save_path.exists()
    
    def delete_save(self) -> bool:
        """删除存档"""
        try:
            if self._save_path.exists():
                self._save_path.unlink()
                print("[存档] 已删除")
                return True
            return False
        except Exception as e:
            print(f"[存档] 删除失败: {e}")
            return False
    
    def get_save_info(self) -> Optional[dict]:
        """获取存档信息（不加载完整数据）"""
        try:
            if not self._save_path.exists():
                return None
            
            with open(self._save_path, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
            
            pet_data = save_data.get("pet_data", {})
            stats = pet_data.get("stats", {})
            
            return {
                "saved_at": save_data.get("saved_at"),
                "name": pet_data.get("name", "Pii"),
                "level": stats.get("level", 1),
                "stage": pet_data.get("growth_stage", "BABY"),
                "exists": True
            }
            
        except Exception:
            return None


# ============ 模块自测试 ============
if __name__ == "__main__":
    print("=" * 40)
    print("模块测试: core/database.py")
    print("=" * 40)
    
    db = PetDatabase()
    
    # 测试1: 保存
    print("\n[测试1] 保存数据")
    test_data = {
        "name": "Pii",
        "stats": {
            "hunger": 80.0,
            "happiness": 70.0,
            "energy": 100.0,
            "hygiene": 100.0,
            "level": 3,
            "exp": 250,
            "age_days": 1
        },
        "growth_stage": "BABY",
        "personality": ["温柔"],
        "state": "IDLE"
    }
    
    success = db.save(test_data)
    print(f"  保存结果: {'成功' if success else '失败'}")
    assert success, "保存应成功"
    print("  ✓ 保存通过")
    
    # 测试2: 加载
    print("\n[测试2] 加载数据")
    loaded = db.load()
    assert loaded is not None, "应能加载数据"
    assert loaded["name"] == "Pii", "名字应匹配"
    assert loaded["stats"]["level"] == 3, "等级应匹配"
    print(f"  加载数据: {loaded['name']} (Lv.{loaded['stats']['level']})")
    print("  ✓ 加载通过")
    
    # 测试3: 存档信息
    print("\n[测试3] 获取存档信息")
    info = db.get_save_info()
    assert info is not None, "应有存档信息"
    print(f"  存档信息: {info}")
    print("  ✓ 信息获取通过")
    
    # 测试4: 检查存在性
    print("\n[测试4] 检查存档存在性")
    exists = db.has_save()
    print(f"  存档存在: {exists}")
    assert exists, "应有存档"
    print("  ✓ 检查通过")
    
    print("\n" + "=" * 40)
    print("所有测试通过! 数据库模块正常")
    print("=" * 40)
