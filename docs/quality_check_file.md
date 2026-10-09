Quality_check: Created after built_silver, and diagnose_default_timing files created

So far we’ve checked the data by eye. This step turns those checks into a script that prints PASS or FAIL for each rule and exits with an error code if anything fails. Later it runs automatically as a gate in the pipeline, before any model trains. In an interview you can describe it as a data validation layer. It does the same job as tools like Great Expectations or pandera, with no extra libraries.

What it checks:

All 10 vintages are present with the expected loan count, and loan IDs are unique
Origination and label tables contain exactly the same loans
Labels are 0 or 1 with no nulls, and the adjusted label never exceeds the raw label
Credit score, DTI, LTV, interest rate, loan amount, units and borrowers fall in sensible ranges
Dates are consistent, and missing-value rates stay below thresholds
Default rates per vintage stay in a plausible band, which would have caught the pandemic problem
Default rate falls as credit score rises