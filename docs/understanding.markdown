## Convert the raw text files to Parquet
> Parquet is a compact, fast file format that Athena and every cloud tool understands. This step produces what data engineers call the bronze layer: the raw data, stored exactly as received (all text), with proper column names attached. Typing and cleaning come in a later step. Keeping a faithful raw copy means you can always re-derive everything.

> The script uses DuckDB, which streams the large files from disk instead of loading 450 MB into memory at once. It writes into vintage_year=2013/-style folders, which is the layout Athena expects.

## After uploading parquet files into s3.
>> Generate the table definitions:
 Athena needs a table definition (called DDL) that lists every column and its type. Your silver origination table has about 40 columns, and typing them by hand invites typos. So this script reads your local silver files, works out the columns and types, and writes the SQL for you. It uses partition projection, so Athena finds the vintage_year=... folders by itself with no repair command needed.


## WoE: Weight of Evidence
>> WoE means Weight of Evidence. In credit risk charts, it shows how strongly a group—such as a FICO score range—leans toward non-default or default, compared with the overall dataset.
A common definition is:

WoE(i) = ln(share of defaults in bin i/ share of non-defaults in bin i)
Here, “share” means the bin’s portion of all non-defaults or all defaults. With this convention:
- Positive WoE: the bin has a higher share of non-defaults relative to defaults, so it looks safer.
- Negative WoE: the bin has a higher share of defaults relative to non-defaults, so it looks riskier.
- Near zero: the bin’s default/non-default mix is close to the overall mix.
Some tools reverse the ratio, so check the chart’s definition before interpreting the sign. WoE is often used to turn binned features into inputs for a scorecard; the related Information Value (IV) summarizes how much the bins distinguish defaults from non-defaults overall.


## AUC fell from train to test:


Diagnose the drop

This step uses two tools, and neither lets us tune the model on 2019.
>>  PSI: Population Stability Index: measures how much each feature’s distribution moved compared with training. It doesn’t use labels at all. Below 0.1 is stable, 0.1 to 0.25 is a moderate shift, and above 0.25 is a major shift. This is the same measure the monitoring layer will use in Week 6.
>> Single Feature AUC by year: r shows how well each feature alone ranks borrowers in each year, so we can see where the ranking weakened.

>> PSI of each feature in 2017, 2018 and 2019 against training.

