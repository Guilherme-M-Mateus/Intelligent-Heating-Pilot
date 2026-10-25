"""Use cases for Intelligent Heating Pilot.

This package contains use cases that encapsulate single business operations.
Each use case is a focused, testable unit of business logic.

Use cases follow the Single Responsibility Principle and are composed by
the HeatingOrchestrator to implement complex workflows.
"""

from __future__ import annotations

from .calculate_anticipation_use_case import CalculateAnticipationUseCase
from .control_preheating_use_case import ControlPreheatingUseCase
from .schedule_anticipation_action_use_case import ScheduleAnticipationActionUseCase
from .update_cache_data_use_case import LearningResetError, UpdateCacheDataUseCase

__all__ = [
    "CalculateAnticipationUseCase",
    "ControlPreheatingUseCase",
    "LearningResetError",
    "ScheduleAnticipationActionUseCase",
    "UpdateCacheDataUseCase",
]
