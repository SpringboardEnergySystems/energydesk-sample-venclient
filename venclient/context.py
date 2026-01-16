"""
Application Context - Singleton Registry for Shared Objects
Provides access to VENManager and MeterDataSimulator across scheduled tasks
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ApplicationContext:
    """
    Singleton registry for shared application objects.
    Allows scheduled tasks to access VENManager, MeterDataSimulator, etc.
    """
    _instance: Optional['ApplicationContext'] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the context only once"""
        if not self._initialized:
            self._objects: Dict[str, Any] = {}
            self._initialized = True
            logger.debug("ApplicationContext initialized")

    def register(self, name: str, obj: Any) -> None:
        """
        Register an object in the context

        Args:
            name: Unique name for the object (e.g., 'ven_manager', 'simulator')
            obj: The object to register
        """
        self._objects[name] = obj
        logger.info(f"Registered object '{name}' in ApplicationContext")

    def get(self, name: str) -> Any:
        """
        Retrieve an object from the context

        Args:
            name: Name of the object to retrieve

        Returns:
            The registered object or None if not found
        """
        obj = self._objects.get(name)
        if obj is None:
            logger.warning(f"Object '{name}' not found in ApplicationContext")
        return obj

    def has(self, name: str) -> bool:
        """Check if an object is registered"""
        return name in self._objects

    def unregister(self, name: str) -> None:
        """Remove an object from the context"""
        if name in self._objects:
            del self._objects[name]
            logger.info(f"Unregistered object '{name}' from ApplicationContext")

    def clear(self) -> None:
        """Clear all registered objects"""
        self._objects.clear()
        logger.info("Cleared all objects from ApplicationContext")

    def list_registered(self) -> list[str]:
        """Get list of all registered object names"""
        return list(self._objects.keys())


# Convenience functions for easy access
_ctx = ApplicationContext()


def get_context() -> ApplicationContext:
    """Get the global ApplicationContext instance"""
    return _ctx


def register_object(name: str, obj: Any) -> None:
    """Register an object in the global context"""
    _ctx.register(name, obj)


def get_object(name: str) -> Any:
    """Get an object from the global context"""
    return _ctx.get(name)


# Specific convenience functions for common objects
def get_ven_manager():
    """Get the VENManager instance"""
    return _ctx.get('ven_manager')


def get_simulator():
    """Get the MeterDataSimulator instance"""
    return _ctx.get('simulator')

