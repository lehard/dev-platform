# project-factory Specification Delta

## ADDED Requirements

### Requirement: Rendered templates end with a single clean trailing newline

Templates SHALL NOT render a trailing blank line at end-of-file, so that a Copier update's staged diff never fails a standard whitespace-hygiene gate (`git diff --cached --check`) purely because of a control-tag formatting artifact rather than a real content change.

#### Scenario: A control tag closes a template file

- **GIVEN** a template file's last line is a Jinja control tag (for example `{% endif %}`) with no further content after it
- **WHEN** the template is rendered for any valid combination of its governing variables
- **THEN** the rendered file ends with exactly one trailing newline and no blank line

#### Scenario: Whitespace-control trimming never corrupts inline expressions

- **WHEN** a template fix removes an unwanted rendered blank line
- **THEN** it SHALL NOT rely on a Jinja environment-wide whitespace-trimming setting unless every template using inline control or escape tags (such as `{% raw %}...{% endraw %}` guarding literal `${{ }}` expressions) has been verified unaffected
