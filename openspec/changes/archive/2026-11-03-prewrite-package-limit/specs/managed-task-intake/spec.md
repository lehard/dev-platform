## ADDED Requirements

### Requirement: Oversized managed comments are rejected before GitHub writes

Managed task creation SHALL estimate the complete serialized package comment in Python characters before any GitHub write, using a 65,536-character limit and a proven upper bound B on the decimal length of the unknown Issue number. An estimate exceeding the limit SHALL fail explicitly naming the change, estimate, limit and inclusion of the number upper bound. Package format and Issue layout SHALL remain unchanged.

#### Scenario: Estimated package exceeds the limit
- **WHEN** the estimated serialized comment exceeds 65,536 characters
- **THEN** creation fails before any GitHub write and names the change, estimate, limit and Issue-number upper bound

#### Scenario: Estimated package fits exactly
- **WHEN** the estimated serialized comment is exactly 65,536 Python characters
- **THEN** creation follows the existing path

#### Scenario: Non-ASCII content
- **WHEN** package artifacts contain non-ASCII characters
- **THEN** the limit is measured in Python string characters of the serialized comment, not UTF-8 bytes

#### Scenario: Package fits outside the conservative zone
- **WHEN** the actual comment fits with more than B − d characters of space
- **THEN** the size check does not reject it

### Requirement: Conservative estimation has a bounded boundary zone

For an actual Issue number of d digits, a fitting package MAY be conservatively rejected only within the boundary zone of at most B − d characters. A fitting package outside this zone SHALL follow the existing creation and publication path. The format is unchanged and the Issue number is unknown before creation.

#### Scenario: Fitting package is near the limit
- **WHEN** the actual package fits but the estimate exceeds the limit solely because the upper bound exceeds the actual number length
- **THEN** the check may reject it within the B − d character boundary zone
