# Historical estimates in post-run review

Missing pace, HR or RPE comparison values now fall back to the historical estimator
at read time, even without a locked pre-run prediction. Saved predictions and plan
targets retain priority. At least three observations for each metric are required.

The estimator receives intended workout distance, saved session intensity where
available and earlier runs only. It never uses the actual execution metrics or
observed weather of the run being compared. Values are labelled retrospective and
shown with coverage. They can change when more old history is imported. Existing
evaluation records, prediction-valid flags, learning and plan changes are untouched.
No schema/environment changes. Tests: 149 passed; mobile review flow passed.
