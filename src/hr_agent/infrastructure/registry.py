"""
Dependency Injection Registry

Centralized registry for all singleton services, repositories, and engines.
This eliminates scattered global variables and makes testing/mocking easier.

Usage:
    from hr_agent.registry import registry

    # Get services
    employee_service = registry.get_employee_service()

    # Reset for testing
    registry.reset()
    registry.register_employee_service(MockEmployeeService())
"""

from typing import TypeVar, Callable, Any
from threading import Lock

T = TypeVar("T")


class SingletonRegistry:
    """Thread-safe singleton registry with lazy initialization."""

    def __init__(self):
        self._instances: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._lock = Lock()

    def register(self, name: str, factory: Callable[[], Any]) -> None:
        """Register a factory function for lazy instantiation."""
        with self._lock:
            self._factories[name] = factory
            # Clear existing instance to allow re-registration
            self._instances.pop(name, None)

    def get(self, name: str) -> Any:
        """Get or create a singleton instance."""
        if name not in self._instances:
            with self._lock:
                if name not in self._instances:
                    if name not in self._factories:
                        raise KeyError(f"No factory registered for '{name}'")
                    self._instances[name] = self._factories[name]()
        return self._instances[name]

    def reset(self, name: str | None = None) -> None:
        """Reset one or all instances (useful for testing)."""
        with self._lock:
            if name:
                self._instances.pop(name, None)
            else:
                self._instances.clear()

    def set_instance(self, name: str, instance: Any) -> None:
        """Directly set an instance (useful for testing with mocks)."""
        with self._lock:
            self._instances[name] = instance


class AppRegistry:
    """
    Application-level registry for all services and components.

    Provides typed accessors for common components while using
    the generic SingletonRegistry under the hood.
    """

    def __init__(self):
        self._registry = SingletonRegistry()
        self._initialized = False

    def initialize(self) -> None:
        """Initialize all default factories."""
        if self._initialized:
            return

        # Import here to avoid circular imports
        from .db import get_engine as _get_engine
        from ..repositories import (
            EmployeeRepository,
            HolidayRepository,
            CompensationRepository,
            CompanyRepository,
        )
        from ..services import (
            EmployeeService,
            HolidayService,
            CompensationService,
            CompanyService,
        )
        from ..core.policy_engine import PolicyEngine
        from ..core.memory import MemoryStore

        # Register database engine
        self._registry.register("db_engine", _get_engine)

        # Register repositories
        self._registry.register("employee_repo", EmployeeRepository)
        self._registry.register("holiday_repo", HolidayRepository)
        self._registry.register("compensation_repo", CompensationRepository)
        self._registry.register("company_repo", CompanyRepository)

        # Register services (these use repos internally)
        self._registry.register("employee_service", EmployeeService)
        self._registry.register("holiday_service", HolidayService)
        self._registry.register("compensation_service", CompensationService)
        self._registry.register("company_service", CompanyService)

        # Register engines
        self._registry.register("policy_engine", PolicyEngine)
        self._registry.register("memory_store", MemoryStore)

        self._initialized = True

    # Typed accessors for services
    def get_employee_service(self):
        self.initialize()

        return self._registry.get("employee_service")

    def get_holiday_service(self):
        self.initialize()

        return self._registry.get("holiday_service")

    def get_compensation_service(self):
        self.initialize()

        return self._registry.get("compensation_service")

    def get_company_service(self):
        self.initialize()

        return self._registry.get("company_service")

    # Typed accessors for repositories
    def get_employee_repo(self):
        self.initialize()

        return self._registry.get("employee_repo")

    def get_holiday_repo(self):
        self.initialize()

        return self._registry.get("holiday_repo")

    def get_compensation_repo(self):
        self.initialize()

        return self._registry.get("compensation_repo")

    def get_company_repo(self):
        self.initialize()

        return self._registry.get("company_repo")

    # Typed accessors for engines
    def get_policy_engine(self):
        self.initialize()

        return self._registry.get("policy_engine")

    def get_memory_store(self):
        self.initialize()

        return self._registry.get("memory_store")

    def get_db_engine(self):
        self.initialize()
        return self._registry.get("db_engine")

    # Testing helpers
    def reset(self) -> None:
        """Reset all instances for testing."""
        self._registry.reset()
        self._initialized = False

    def set_mock(self, name: str, instance: Any) -> None:
        """Set a mock instance for testing."""
        self.initialize()
        self._registry.set_instance(name, instance)


# Global registry instance
registry = AppRegistry()
