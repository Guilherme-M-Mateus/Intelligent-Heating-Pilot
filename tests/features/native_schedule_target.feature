Feature: Native schedule anticipates the comfort temperature
  As a user driving my thermostat with a native Home Assistant schedule
  I want IHP to anticipate the comfort temperature of the next ON slot
  So that the anticipated start is computed for the comfort setpoint, not the night setpoint

  Native schedules are compute-only: IHP exposes the anticipation as sensors
  but has no HACS Scheduler to delegate the heating action to.

  Background:
    Given a native schedule "schedule.heating" that is off with its next ON event at 07:00
    And the thermostat "climate.living_room" currently targets 17.0°C

  Scenario: The next slot targets the thermostat comfort preset
    Given the thermostat comfort preset is 21.0°C
    When IHP reads the next scheduled timeslot
    Then the timeslot starts at 07:00
    And the timeslot target temperature is 21.0°C

  Scenario: An uninitialized comfort preset falls back to the default comfort temperature
    Given the thermostat comfort preset is not initialized
    When IHP reads the next scheduled timeslot
    Then the timeslot target temperature is 20.0°C

  Scenario: Anticipation is computed but no scheduler action is triggered
    Given the thermostat comfort preset is 21.0°C
    And HACS Scheduler is not installed
    When IHP recalculates twice inside the preheating window of the native schedule
    Then no scheduler service is called
    And IHP tracks the preheating of the native schedule slot as started

  Scenario: The anticipation timer fires without triggering any scheduler action
    Given HACS Scheduler is not installed
    When the anticipation timer fires for the native schedule
    Then no scheduler service is called
    And IHP tracks the preheating of the native schedule slot as started
