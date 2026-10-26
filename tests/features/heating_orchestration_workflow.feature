Feature: Heating Orchestration Workflow
  As a heating system
  I want the orchestrator to coordinate use cases for intelligent preheating
  So that the home reaches target temperature at the scheduled time

  # ===================================================================
  # HAPPY PATH — Normal preheating workflow
  # ===================================================================

  Scenario: Calculate anticipation and schedule preheating when needed
    Given the orchestrator is configured with all use cases
    And the next timeslot is at 07:00 with target temperature 21°C
    And the current indoor temperature is 18°C
    And the calculated anticipated start time is 05:30
    When the orchestrator calculates and schedules anticipation
    Then a preheating timer should be scheduled for 05:30
    And the result should contain anticipated start time 05:30
    And the result should contain next target temperature 21°C

  Scenario: Already at target temperature — skip preheating
    Given the orchestrator is configured with all use cases
    And the next timeslot is at 07:00 with target temperature 21°C
    And the current indoor temperature is 22°C
    And anticipation calculation returns 0 minutes of anticipation
    When the orchestrator calculates and schedules anticipation
    Then no preheating timer should be scheduled
    And the result should contain 0 anticipation minutes

  Scenario: No scheduler configured — return clear values
    Given the orchestrator is configured with all use cases
    And no scheduler timeslot is available
    When the orchestrator calculates and schedules anticipation
    Then the result should indicate clear values
    And no preheating timer should be scheduled

  # ===================================================================
  # REVERT LOGIC — Room heating faster than predicted: postpone, then resume
  # A preheat that would reach the target too early is reverted and a timer
  # restarts it at the new anticipated start, so the target is still met on time.
  # ===================================================================

  Scenario: Room heating faster than predicted postpones preheating to the new start
    Given the orchestrator is configured with all use cases
    And preheating is currently active for target time 07:00
    And the new anticipated start time is 06:15 which is after the current time
    When the orchestrator calculates and schedules anticipation
    Then the active preheating should be canceled
    And a new preheating timer should be rescheduled for 06:15
    And the preheating state should be reset to inactive

  Scenario: Continue preheating when anticipated start is still in the past
    Given the orchestrator is configured with all use cases
    And preheating is currently active for target time 07:00
    And the anticipated start time is still in the past
    When the orchestrator calculates and schedules anticipation
    Then preheating should continue without interruption
    And no cancel action should be triggered

  Scenario: Mark preheating complete when target time is reached
    Given the orchestrator is configured with all use cases
    And preheating is currently active for target time 07:00
    And the current time is past 07:00
    When the orchestrator calculates and schedules anticipation
    Then preheating should be marked as complete
    And the anticipation state should be cleared

  Scenario: Completed preheating does not block the next timeslot
    Given the orchestrator is configured with all use cases
    And preheating is currently active for target time 04:00
    And the next timeslot is at 07:00 with target temperature 21°C
    And the current indoor temperature is 18°C
    And the calculated anticipated start time is 05:30
    When the orchestrator calculates and schedules anticipation
    Then no cancel action should be triggered
    And a preheating timer should be scheduled for 05:30

  # ===================================================================
  # NO FLAPPING — An active preheat must not bounce before its slot (#182)
  # ===================================================================

  Scenario: Target reached early keeps active preheating until the slot
    Given the orchestrator is configured with all use cases
    And preheating is currently active for target time 07:00
    And the next timeslot is at 07:00 with target temperature 21°C
    And anticipation calculation returns 0 minutes of anticipation
    When the orchestrator calculates and schedules anticipation
    Then preheating should continue without interruption
    And preheating should still be active

  Scenario: Indoor temperature unavailable keeps active preheating
    Given the orchestrator is configured with all use cases
    And preheating is currently active for target time 07:00
    And the indoor temperature is unavailable
    When the orchestrator calculates and schedules anticipation
    Then preheating should continue without interruption
    And preheating should still be active

  Scenario: Postponed start still in the past does not revert preheating
    Given the orchestrator is configured with all use cases
    And preheating is currently active for target time 07:00
    And the anticipated start time moves later but stays in the past
    When the orchestrator calculates and schedules anticipation
    Then preheating should continue without interruption
    And preheating should still be active

  # ===================================================================
  # IHP ENABLED / DISABLED — Switch controls preheating behavior
  # ===================================================================

  Scenario: IHP disabled — cancel active preheating and skip scheduling
    Given the orchestrator is configured with all use cases
    And preheating is currently active for target time 07:00
    When the orchestrator calculates and schedules anticipation with IHP disabled
    Then the active preheating should be canceled
    And the anticipation state should be cleared
    And no new preheating timer should be scheduled

  Scenario: IHP disabled with no active preheating — skip quietly
    Given the orchestrator is configured with all use cases
    And no preheating is currently active
    When the orchestrator calculates and schedules anticipation with IHP disabled
    Then no cancel action should be triggered
    And the anticipation state should be cleared

  Scenario: IHP re-enabled — resume normal scheduling
    Given the orchestrator is configured with all use cases
    And the next timeslot is at 07:00 with target temperature 21°C
    And the current indoor temperature is 18°C
    And the calculated anticipated start time is 05:30
    When the orchestrator calculates and schedules anticipation with IHP enabled
    Then a preheating timer should be scheduled for 05:30
    And the result should contain anticipated start time 05:30

  # ===================================================================
  # SCHEDULER DISABLED — Detect scheduler state change mid-workflow
  # ===================================================================

  Scenario: Scheduler disabled mid-workflow — clear anticipation state
    Given the orchestrator is configured with all use cases
    And the scheduler entity was previously active
    And the scheduler is now disabled
    When the orchestrator calculates and schedules anticipation
    Then the result should indicate clear values
    And the anticipation state should be cleared
    And any active preheating should be canceled
