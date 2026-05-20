# Training The Tool

## Manual Training

Use this when you already know the correct ODI/manual/final SQL and want to teach the tool specific patterns.

1. Open Test Management and use Training Studio.
2. Set Target Table and Source Tables.
3. Pick `GHC` or `Local Agent`. For local mode, choose the SQL Dev agent.
4. Paste the ODI/manual SQL into `ODI / Manual SQL To Reproduce`.
5. Paste the expected final SQL or expected result into `Expected Final SQL / Result`.
6. Add notes about joins, mappings, exceptions, or known business rules.
7. Click `Run SQL Dev Reproduction`.
8. Review the generated output.
9. Click `Mark Win` if the output is acceptable, or `Mark Loss` if it is not.
10. Click `Save Example to KB` to save the example pack under `training_packs/`.

What gets remembered:

- Training packs with source SQL, expected SQL, notes, and uploaded references.
- Win/loss outcomes from Training Studio.
- Test management events such as create, update, rerun, delete, and TFS import.

## Control Table Background Training

Use this when you are working inside the CT flow and want background rule learning.

1. Open `Control Table Tests`.
2. Generate or paste the SQL you want to compare.
3. Use `Save Insert SQL + Learn` to save the current final logic and create reusable correction rules.
4. Use `Save Rule` on individual mismatched columns when only a few attributes need to be taught.
5. Use `Save Real Example Pack` to store DRD files, reference SQL, generated SQL, and notes.
6. Use `Run Replay` to regression-test saved rules against fixture packs.

What gets remembered:

- Column-level correction rules.
- Final insert SQL state.
- Training packs and follow-up questions.
- Replay outcomes and comparison context.

## Self-Training With Expected Result

Use this when you want the tool to improve from repeated expected-vs-actual comparison.

1. Run a reproduction in Training Studio or generate CT output.
2. Compare the produced SQL against the expected final SQL.
3. If it matches well enough, mark `Win`.
4. If it does not, mark `Loss`, adjust notes or expected SQL, and run again.
5. Save the final successful version as a training pack.

Recommended pattern:

- First run: broad notes, get a baseline.
- Second run: add missing joins, aliases, or target-column rules.
- Final run: once it is correct, save to KB and mark win.

## Practical Guidance

- Use project-valid Area Path and Iteration Path values from the TFS autocomplete lists instead of typing them manually.
- Prefer saving one strong example pack per target table over many partial examples.
- Mark losses honestly. Loss events are useful because they capture patterns that should not be repeated.
- When editing or rerunning tests in Test Management, the app records those actions so they can be correlated with training history later.