Feature: Scheduled slots use the heating slope learned for them
  As a user with a heating schedule
  I want each scheduled slot to use the slope learned while preheating for that slot
  So that anticipation adapts to how the room heats at that time of day

  Background:
    Given a heating slope learner with persistent storage
    And a preheat cycle from 05:30 to 07:00 that heated at 3.0 degrees per hour
    And a preheat cycle from 06:00 to 07:15 that heated at 4.0 degrees per hour
    And a daytime cycle from 13:00 to 14:00 that heated at 1.0 degrees per hour
    And contextual slopes are learned from these cycles

  Scenario: A 07:00 slot reads the slope learned while preheating for it
    When the heating slope for a slot at 07:00 is requested
    Then the heating slope returned is 3.5 degrees per hour

  Scenario: The learned slot slope survives a restart
    Given Home Assistant restarts
    When the heating slope for a slot at 07:00 is requested
    Then the heating slope returned is 3.5 degrees per hour

  Scenario: The hour a preheat cycle started does not pick up its slope
    When the heating slope for a slot at 05:00 is requested
    Then the heating slope returned is not learned from the preheat cycles
