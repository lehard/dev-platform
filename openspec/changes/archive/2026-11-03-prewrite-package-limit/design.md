## Decisions

Use a single 65,536-character constant, sourced to GitHub's HTTP 422 response stating “maximum is 65536 characters” and the observed publication failure in friction #831. Measure Python string length of the complete serialized comment, including manifest and artifacts, rather than UTF-8 byte length. Build the estimate using the actual serializer and account for all fields that will be present after creation, including source Issue evidence.

Before creation the Issue number is unknown. Substitute a proven upper bound on its decimal digit count, with evidence and a test for the bound. The format stays unchanged. For an actual number of d digits and bound B digits, the conservative boundary zone is at most B − d characters: within that zone a fitting comment may be rejected; outside it a fitting comment must not be rejected. This is accepted because the number cannot be known before the first write. Do not add an arbitrary margin. Ensure the other estimated fields have their actual serialized lengths; any assumption required to establish that must be justified and tested.

An over-limit refusal names the change, estimated character count, limit, and inclusion of the Issue-number upper bound, and happens before any GitHub write. Successful creation follows the existing path. Preserve explicit GitHub errors, including 422. Verify using stubs; no live boundary test is authorized. Record that limitation and the risk of GitHub changing its limit in verification.md.

## Length proof and implementation boundary

GitHub's [Issue schema](https://docs.github.com/en/graphql/reference/issues#issue)
declares `Issue.number` as `Int!`; its [Int scalar contract](https://docs.github.com/en/graphql/reference/other#int)
limits that value to `2^31 - 1 = 2147483647`. Positive Issue numbers therefore
have at most B = 10 decimal digits. This bounds the Issue number, not the
unrelated global database ID. Use that maximum as the estimate's number.

The REST [response body contract](https://docs.github.com/en/rest/using-the-rest-api/getting-started-with-the-rest-api#about-the-response-body)
explicitly specifies all returned timestamps as UTC `YYYY-MM-DDTHH:MM:SSZ`.
Thus the newly fetched `source_issue_evidence.updated_at` is exactly 20 ASCII
characters, with no JSON escapes. `body_sha256` is produced by Python's
SHA-256 `hexdigest()`, exactly 64 ASCII hex characters, also without escapes.
Use a timestamp in that contracted form and an actual SHA-256 hex digest as
length witnesses; their values are not published. The other manifest fields,
including routing and process evidence, and all artifact contents are already
known and passed unchanged to the real serializer. Derived revision, parent
Requirement and work identity are not serialized.

Run the check only on fresh creation, immediately before `create_issue` (all
preceding operations on this path are local validation or GitHub reads).
Existing duplicate/resume behavior remains outside this change; no existing
Issue recovery is added. After creation, fail explicitly before publishing if
the returned number violates the proven bound or the actual serialized length
differs from `estimate - (B - d)`. This detects external contract drift without
substitution or a recovery path. The pre-write guarantee depends on GitHub
honoring its published number and timestamp contracts; it cannot undo the
Issue creation if GitHub violates them.

With only the number's length different, the actual comment length A and
estimate E satisfy `E - A = B - d`. Hence the only fitting comments rejected
have `65536 - (B - d) < A <= 65536`; no additional reserve exists. Tests use
the actual serializer, including its JSON escaping of manifest values and
literal non-ASCII artifact contents, rather than UTF-8 bytes or input lengths.
