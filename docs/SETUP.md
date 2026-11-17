# Jim Silent v1 — setup and test

Runner: public repository `bfipbf/catalyst-runner`, branch `main`.
Workflow: `.github/workflows/jim-silent.yaml`, **Run workflow** button only.

## Safety boundary

- No Issue event, no Issue comment, no push, no artifact upload.
- `smoke` is the default; it checks the runner and Python only, without any secret.
- `index` performs read-only checkout of `bfi-finance/bfi-pbf-live` at `Branch_Gabungan`.
- Source and generated index are ephemeral inside the runner; stdout/stderr from parsing and validation are suppressed. Final step removes temporary files.
- GitHub Actions run logs on public repositories are public. Never enable `ACTIONS_STEP_DEBUG` or `ACTIONS_RUNNER_DEBUG` and never add `set -x`.
- Source contents must never be uploaded as artifacts or copied to logs.

## Credential for index mode

Configure repository Actions secret `CATALYST_SOURCE_READ_TOKEN` with **only** read access to `bfi-finance/bfi-pbf-live` (e.g., narrowly scoped fine-grained PAT with Contents: Read, with organizational authorization if needed). A credential is not required for `smoke`. Do not enter the token in workflow inputs, Issue, or files. Access to edit workflow files and trigger credentialed runs must remain restricted to trusted maintainers.

The current workflow intentionally has **no publication job, no publication secret, and no write permission**.

## Testing

1. Open Actions → **Jim Silent — Catalyst (read-only)** → **Run workflow**, mode `smoke`.
2. Confirm the `smoke` job finishes successfully. A workflow listed in GitHub is not by itself an execution proof.
3. After configuring read-only source token, run mode `index` manually.
4. Confirm the index job ends with `Catalyst read-only parsing and coverage checks: PASS.` and no source XML, token, index JSON, or private diagnostics appear in public logs.
5. If index mode fails, repair parser/validator in the public code **without** printing private diagnostics. No index is published.

## Future publishing (not enabled)

Implement **separate** protected publish workflow only after successful read-only validation and human review. Use a separate scoped publication credential, a GitHub Environment with required reviewers, a private target repository `bfipbf/GPT-PBF`, and safeguards against publishing into wrong paths. GitHub repository Contents: Write permission is repository-wide, not folder-scoped.

No changes to `bfi-finance/bfi-pbf-live` or existing Jim Bash workflows.
