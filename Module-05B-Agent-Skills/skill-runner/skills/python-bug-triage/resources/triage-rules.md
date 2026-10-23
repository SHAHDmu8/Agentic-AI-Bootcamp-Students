# Bug triage rules

## Severity
- SEV1: crash, data loss, auth bypass, production outage, or complete block of a core workflow.
- SEV2: major regression or broken primary path that blocks a significant user journey.
- SEV3: important but limited issue with a workaround.
- SEV4: low-impact, cosmetic, or nuisance issue.

## Required evidence for a complete bug report
1. What failed.
2. Expected result.
3. Actual result.
4. Steps to reproduce.
5. Version or environment.
6. Whether it is a one-off or reproducible.

## Missing fact workflow
- If the report is missing version or environment, ask for it.
- If there are no reproduction steps, ask for them.
- If the expected result is missing, say it is not actionable.

## Triage output format
- Severity: <SEV1..SEV4>
- Likely component: <component or module>
- Missing facts: <items>
- Next action: <single concrete step>
