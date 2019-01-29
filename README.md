# 100k_negnegs v1.0
This script retrieves Guy's 100k cases from CIP-API that are ready for interpretation and groups them based on whether they are negative negative (i.e. no tier 1, 2 or CIP candidate variants) or not. This is to facilitate automated reporting for these cases.

Groups cases can be placed into are:
* `negnegs_one_request`
    * negneg cases where there are no other ongoing or reported interpretation requests for that patient - can be reported automatically.
* `negnegs_multiple_requests`
    * negneg cases where there are other active or reported interpretation requests for that patient (which may or may not be negneg) 
* `error`
    * Error encountered when trying to parse the CIP-API data for this case. Some early pilot cases have broken formatting so they end up here.
* `all_other`
    * Everything else (cases with tier 1/2 or CIP candidate variants end up here).

The script outputs a tsv file containing participant ID, interpretation request ID, and the group the case belongs to.

## Usage

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

