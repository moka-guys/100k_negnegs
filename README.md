# 100k_negnegs v1.1

## negneg_cases.py

This script retrieves Guy's 100k cases from CIP-API that are ready for interpretation and groups them based on whether they are negative negative or not. A negative negative case is one which has no tier 1, 2 or CIP candidate variants, and no tier A CNVs/SVs with a GeL population frequency <1%. This is to facilitate automated reporting for these cases.

Groups cases can be placed into are:
* `negnegs_one_request`
    * negneg cases where there are no other ongoing or reported interpretation requests for that patient - can be reported automatically.
* `negnegs_multiple_requests`
    * negneg cases where there are other active or reported interpretation requests for that patient (which may or may not be negneg) 
* `error`
    * Error encountered when trying to parse the CIP-API data for this case. Some early pilot cases have broken formatting so they end up here.
* `all_other`
    * Everything else (cases with tier 1/2 or CIP candidate variants end up here).

The script outputs a tsv file containing participant ID, interpretation request ID, genome assembly, and the group the case belongs to.

### Usage

This script requires access to the CIPAPI so must be run on our trust linux server.

Requirements:

* Python 3.6
* Access to CIPAPI
* JellyPy (in PYTHONPATH)
* GelReportModels (v6 or higher)

On `SV-TE-GENAPP01` activate the `jellypy_py3` conda environment so that above requirements are met:

```
source activate jellypy_py3
```

Run the script:

```
python /home/mokaguys/Apps/100k_negnegs/negneg_cases.py -i INPUT_FILE
```

## negnegs2moka.py

This script parses the ouput from negneg_cases.py and creates/updates NGStest requests for the negneg cases in Moka, assigning negneg (NN) as the result code and entering 'Moka' as the first checker. It only books in cases if there is a single interpretation request (the `negnegs_one_request` group) found in the CIP-API. If there is an existing 100k NGStest already in Moka for a patient, providing there is only one test and all the details are as expected, the result code will be updated to negneg (NN) and 'Moka' entered as the first checker.

The script outputs a tab seperated logfile, showing the action performed on each case, and flagging cases that couldn't be entered to Moka and the reason why.


### Usage

This script requires access to Moka via ODBC, which currently means it must be run from Trust Windows machines.

Requirements:
    ODBC connection to Moka
    Python 2.7
    pyodbc

The python installation in Genetics_Data2 contains all required packages.

```
python negnegs2moka.py -i INPUT_FILE -o OUTPUT_FILE
```