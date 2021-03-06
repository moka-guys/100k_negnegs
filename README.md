# 100k_negnegs v1.1

## negneg_cases.py

This script retrieves Guy's 100k cases from CIP-API that are ready for interpretation and groups them based on whether they are negative negative or not (this is to facilitate automated reporting for these cases). As of v1.1 of this script, a negative negative case is one which has:
- no tier 1, 2 or CIP candidate variants
- no tier A CNVs/SVs with a GeL population frequency <1%
- no tier 1 or 2 short tandem repeats (STRs)
- no case flags (these can indicate important information about a case such as suspected uniparental disomy, so should be reviewed manually)

Groups cases can be placed into are:
* `negnegs_one_request`
    * negneg cases where there are no other ongoing or reported interpretation requests for that patient - can be reported automatically.
* `negnegs_multiple_requests`
    * negneg cases where there are other active or reported interpretation requests for that patient (which may or may not be negneg) 
* `error`
    * Error encountered when trying to parse the CIP-API data for this case. Some early pilot cases have broken formatting so they end up here.
* `all_other`
    * Everything else (e.g. cases with tier 1/2 or CIP candidate variants end up here).

The script outputs a tsv file containing participant ID, interpretation request ID, genome assembly, case flags and the group the case belongs to.

### Usage

This script requires access to the CIPAPI so must be run on our trust linux server.

Requirements:

* Python 3.6
* Access to CIPAPI
* JellyPy
* GelReportModels

On `SV-PR-GENAPP01` activate the `100k_negnegs` conda environment so that above requirements are met:

```
conda activate `100k_negnegs`
```

Run the script:

```
python /usr/local/src/mokaguys/Apps/100k_negnegs/negneg_cases.py -i INPUT_FILE
```

## negnegs2moka.py

This script is designed to be run after [100k_negnegs/negneg_cases.py](https://github.com/moka-guys/100k_negnegs) has been run to generate a list of categorised 100k cases, and [100k_moka_booking_in/100k2moka.py](https://github.com/moka-guys/100k_moka_booking_in) has been run to book all cases into Moka.

This script uses the ouput from [100k_negnegs/negneg_cases.py](https://github.com/moka-guys/100k_negnegs) to update case details for the negneg cases in Moka ready for automatic reporting, assigning negneg (NN) as the result code and entering 'Moka' as the first checker. It only books in cases if there is a single interpretation request (the `negnegs_one_request` group) found in the CIP-API.

The script outputs a tab seperated logfile, showing the action performed on each case, and flagging cases that couldn't be entered to Moka and the reason why.


### Usage

This script requires access to Moka via ODBC.

Requirements:
    ODBC connection to Moka
    Python 3.6
    pyodbc

On `SV-PR-GENAPP01` activate the `100k_negnegs` conda environment so that above requirements are met:

```
conda activate `100k_negnegs`
```

Run the script:

```
python negnegs2moka.py -i INPUT_FILE -o OUTPUT_FILE
```
