Feature: Contact management
  As a small company managing relationships with contacts and companies
  I want to record contacts, their companies, and interactions with them
  So that follow-ups never get lost

  Rule: A contact must be identifiable by at least a name

    Scenario: Recording a contact with only a first name is accepted
      Given no contacts have been recorded yet
      When I record a contact with first name "Ada" and no last name
      Then the contact is accepted

    Scenario: Recording a contact with no name at all is rejected
      Given no contacts have been recorded yet
      When I record a contact with no first name and no last name
      Then the contact is rejected with a reason mentioning "name"

  Rule: A company must have a unique name

    Scenario: Registering a new company with a unique name succeeds
      Given no companies have been registered yet
      When I register a company named "Acestus Infrastructure"
      Then the company is accepted

    Scenario: Registering a company with a name already in use is rejected
      Given a company named "Acestus Infrastructure" is already registered
      When I register a company named "Acestus Infrastructure"
      Then the company is rejected with a reason mentioning "already exists"

  Rule: Every interaction belongs to a known contact and has a valid type

    Scenario: Logging a call against an existing contact succeeds
      Given a contact named "Ada Lovelace" has been recorded
      When I log a "call" interaction against "Ada Lovelace" today
      Then the interaction is accepted
      And "Ada Lovelace" has 1 recorded interaction

    Scenario: Logging an interaction against a contact that does not exist is rejected
      Given no contacts have been recorded yet
      When I log a "call" interaction against "Ghost Contact" today
      Then the interaction is rejected with a reason mentioning "does not exist"

    Scenario: Logging an interaction with an unrecognized type is rejected
      Given a contact named "Ada Lovelace" has been recorded
      When I log a "carrier-pigeon" interaction against "Ada Lovelace" today
      Then the interaction is rejected with a reason mentioning "not one of"

  Rule: A follow-up date must come after the interaction it follows up on

    Scenario: Scheduling a follow-up after the interaction date succeeds
      Given a contact named "Ada Lovelace" has been recorded
      When I log a "email" interaction against "Ada Lovelace" today with a follow-up 3 days later
      Then the interaction is accepted

    Scenario: Scheduling a follow-up before the interaction date is rejected
      Given a contact named "Ada Lovelace" has been recorded
      When I log a "email" interaction against "Ada Lovelace" today with a follow-up 3 days earlier
      Then the interaction is rejected with a reason mentioning "after"
