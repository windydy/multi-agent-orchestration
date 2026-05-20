"""
State状态管理抽象

定义状态存储、更新、历史追踪接口
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass
from datetime import datetime
import copy


@dataclass
class StateUpdate:
    """状态更新记录"""
    key: str
    old_value: Any
    new_value: Any
    timestamp: datetime
    node_id: str = ""
    agent_id: str = ""


class BaseState(ABC):
    """状态管理基类"""
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """获取状态值"""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, metadata: dict = None) -> None:
        """设置状态值"""
        pass
    
    @abstractmethod
    def update(self, updates: dict, metadata: dict = None) -> None:
        """批量更新状态"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除状态"""
        pass
    
    @abstractmethod
    def history(self, key: str = None) -> list[StateUpdate]:
        """获取状态变更历史"""
        pass
    
    @abstractmethod
    def snapshot(self) -> dict:
        """获取完整快照"""
        pass
    
    @abstractmethod
    def restore(self, snapshot: dict) -> None:
        """从快照恢复"""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """清空状态"""
        pass
    
    @abstractmethod
    def keys(self) -> list[str]:
        """获取所有键"""
        pass


class InMemoryState(BaseState):
    """内存状态管理
    
    状态存储在内存中，支持历史追踪
    """
    
    def __init__(self, initial_state: dict = None):
        self._state: dict = copy.deepcopy(initial_state) if initial_state else {}
        self._history: list[StateUpdate] = []
    
    def get(self, key: str, default: Any = None) -> Any:
        """支持嵌套键访问，如 'result.data'"""
        keys = key.split('.')
        value = self._state
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any, metadata: dict = None) -> None:
        old_value = self.get(key)
        self._set_nested(key, value)
        
        update = StateUpdate(
            key=key,
            old_value=copy.deepcopy(old_value),
            new_value=copy.deepcopy(value),
            timestamp=datetime.now(),
            node_id=metadata.get("node_id", "") if metadata else "",
            agent_id=metadata.get("agent_id", "") if metadata else ""
        )
        self._history.append(update)
    
    def _set_nested(self, key: str, value: Any) -> None:
        """设置嵌套值"""
        keys = key.split('.')
        target = self._state
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
    
    def update(self, updates: dict, metadata: dict = None) -> None:
        for key, value in updates.items():
            self.set(key, value, metadata)
    
    def delete(self, key: str) -> bool:
        if key not in self._state:
            return False
        
        old_value = self._state[key]
        del self._state[key]
        
        self._history.append(StateUpdate(
            key=key,
            old_value=old_value,
            new_value=None,
            timestamp=datetime.now()
        ))
        return True
    
    def history(self, key: str = None) -> list[StateUpdate]:
        if key:
            return [u for u in self._history if u.key == key or u.key.startswith(key + '.')]
        return self._history.copy()
    
    def snapshot(self) -> dict:
        return {
            "state": copy.deepcopy(self._state),
            "history_count": len(self._history)
        }
    
    def restore(self, snapshot: dict) -> None:
        self._state = copy.deepcopy(snapshot.get("state", {}))
    
    def clear(self) -> None:
        self._state.clear()
        self._history.clear()
    
    def keys(self) -> list[str]:
        return list(self._state.keys())
    
    def to_dict(self) -> dict:
        return copy.deepcopy(self._state)
    
    def __repr__(self) -> str:
        return f"State(keys={len(self._state)}, history={len(self._history)})"