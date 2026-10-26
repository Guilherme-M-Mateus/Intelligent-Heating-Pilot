Feature: Native schedule preheats to the comfort temperature
  As a user driving my thermostat with a native Home Assistant schedule
  I want IHP to anticipate the comfort temperature of the next ON slot
  So that the room is warm when the slot starts, not left at the night setpoint

  Background:
    Given a native schedule "schedule.heating" that is off with its next ON event at 07:00
    And the thermostat "climate.living_room" currently targets 17.0°C

  Scenario: The next slot targets the thermostat comfort preset
    Given the thermostat comfort preset is 21.0°C
    When IHP reads the next scheduled timeslot
    Then the timeslot starts at 07:00
    And the timeslot target temperature is 21.0°C

  Scenario: Without a comfort preset the default comfort temperature is used
    Given the thermostat has no comfort preset
    When IHP reads the next scheduled timeslot
    Then the timeslot target temperature is 20.0°C
