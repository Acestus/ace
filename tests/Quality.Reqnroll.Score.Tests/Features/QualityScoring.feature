Feature: Test quality scoring pipeline
  Produce quality score reports for inner-loop and outer-loop tests.

  @inner-loop-score
  Scenario: Generate inner-loop quality score reports
    Given the repository root is discovered
    When I score inner-loop tests with the quality rubric
    Then I write the inner-loop quality reports

  @outer-loop-gherkin-score
  Scenario: Generate outer-loop Gherkin quality score reports
    Given the repository root is discovered
    When I score outer-loop Gherkin tests with the quality rubric
    Then I write the outer-loop Gherkin quality reports
