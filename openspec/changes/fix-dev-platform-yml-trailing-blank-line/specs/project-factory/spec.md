# project-factory Specification Delta

## MODIFIED Requirements

### Requirement: Rendered templates end with a single clean trailing newline

Templates SHALL NOT render a trailing blank line at end-of-file, so that a Copier update's staged diff never fails a standard whitespace-hygiene gate (`git diff --cached --check`) purely because of a control-tag formatting artifact rather than a real content change. This requirement covers every rendered branch of every affected template's conditional, not merely the branch first found failing.

#### Scenario: A control tag closes a template file

- **GIVEN** a template file's last line is a Jinja control tag (for example `{% endif %}`) with no further content after it
- **WHEN** the template is rendered for any valid combination of its governing variables
- **THEN** the rendered file ends with exactly one trailing newline and no blank line

#### Scenario: An if/else construct has asymmetric whitespace-control trim markers

- **GIVEN** one branch of an `{% if %}/{% else %}/{% endif %}` construct has a whitespace-trim marker on its closing tag and the other branch does not
- **WHEN** the untrimmed branch is the one that actually renders
- **THEN** a trailing blank line SHALL NOT appear at end-of-file, requiring the same trim marker on both branches' closing tags

#### Scenario: Whitespace-control trimming never corrupts inline expressions

- **WHEN** a template fix removes an unwanted rendered blank line
- **THEN** it SHALL NOT rely on a Jinja environment-wide whitespace-trimming setting unless every template using inline control or escape tags (such as `{% raw %}...{% endraw %}` guarding literal `${{ }}` expressions) has been verified unaffected
