"""
v1.1 - AB 2019/12/11
Requirements:
    Python 3.6
    JellyPy
    GeL Report Models (v6 or higher)

usage: get_tiered_variants.py [-h] -o OUTPUT_FILE

Pulls Guys 100k cases from CIP-API and outputs file showing which are negative
negatives

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT_FILE, --output_file OUTPUT_FILE
                        Output file (tsv)
"""

import argparse
from pyCIPAPI.interpretation_requests import get_interpretation_request_json, get_interpretation_request_list
# Import InterpretedGenome from GeLReportModels v6.0
from protocols.reports_6_0_0 import InterpretedGenome
from collections import Counter


def process_arguments():
    """
    Uses argparse module to define and handle command line input arguments and help menu
    """
    # Create ArgumentParser object. Description message will be displayed as part of help message if script is run with -h flag
    parser = argparse.ArgumentParser(description='Pulls Guys 100k cases from CIP-API and outputs file showing which are negative negatives')
    # Define the arguments that will be taken.
    parser.add_argument('-o', '--output_file', required=True, help='Output file (tsv)')
    # Return the arguments
    return parser.parse_args()


def group_vars_by_cip(interpreted_genomes_json):
    """
    Groups variants by CIP provider
    Args:
        interpreted_genomes_json: interpreted genome JSON from CIP API
    Returns:
        Nested dictionary of variants grouped by CIP and cip version. {key = CIP value = {key = cip_version, value = list_of_variants}}
    """
    # Note this does not pull out CNVs/SVs
    vars_by_cip = {}
    # possible values for cip at time of writing:
    # omicia, congenica, nextcode, genomics_england_tiering, illumina, exomiser
    # There will be a separate interepreted genome for each cip used
    for ig in interpreted_genomes_json:
        # Convert the interpreted genome JSON into InterpretedGenome object from GeL Report Models v6.0
        ig_obj = InterpretedGenome.fromJsonDict(ig['interpreted_genome_data'])
        # cip provider stored in the interpretationService field.
        # Store the list of reported variants for that cip
        cip = ig_obj.interpretationService.lower()
        cip_version = int(ig['cip_version'])
        # If cip not already in dictionary, add it in with an empty dictionary as value
        vars_by_cip[cip] = vars_by_cip.setdefault(cip, {})
        # If CIP is present multiple times each should have it's own version number
        # However do a quick test to make sure this is true and error out if not
        if cip_version in vars_by_cip[cip]:
            sys.exit(f"Multiple interpreted genomes with version number '{cip_version}' for interpretation service '{cip}'")
        # If there are variants, add the variant list for that cip/version to dictionary.
        if ig_obj.variants:
            vars_by_cip[cip][cip_version] = ig_obj.variants
        # If there aren't any variants just store empty list
        else:
            vars_by_cip[cip][cip_version] = []
    return vars_by_cip


def group_vars_by_tier(variants_json):
    """
    Groups variants according to their GeL tier
    Args:
        variants_json: list of GeL report model v6 variant objects
    Returns:
        Dictionary of variants grouped by tier {key = tier, value = list of variant objects}
    """
    # Takes list of variants and groups them by tier (Note this doesn't include SVs/CNVs)
    tiered_vars = {
        'TIER1': [],
        'TIER2': [],
        'TIER3': [],
        'OTHER': []
        }
    for variant in variants_json:
        # Log the tier for each report event for a variant
        tiers = []
        for reportevent in variant.reportEvents:
            # Possible values for tier in report model v6 are NONE, TIER1, TIER2, TIER3, TIER4, TIER5, TIERA, TIERB
            if reportevent.tier.upper() in ('TIER1', 'TIER2', 'TIER3'):
                # Record the tier number
                tiers.append(int(reportevent.tier.strip('TIER')))
            else:
                # Value of 4 used to represent any other or no tier.
                tiers.append(4)
        # The lowest number represents the highest ranked tier for that variant (e.g. tier 1 ranks higher than tier 2)
        top_rank_tier = min(tiers)
        # Record the variant in the dictionary based on it's highest ranked tier
        if top_rank_tier == 4:
            tiered_vars['OTHER'].append(variant)
        else:
            tiered_vars[f'TIER{top_rank_tier}'].append(variant)
    return tiered_vars


def is_neg_neg(ir_json):
    """
    Checks if a case is a negative negative (no variants other than tier 3)
    Args:
        ir_json: Interpretation request JSON from the CIP-API
        cips: List of CIPs that should be checked for candidate variants (e.g. 'omicia', 'genomics_england', 'exomiser' etc)
    Returns:
        Boolean: True if negative negative, False if not.
    """
    # Create a dictionary of variant lists (value) grouped by CIP (key - lowercase)
    vars_by_cip = group_vars_by_cip(ir_json['interpreted_genome'])
    # There may be multiple interpreted genomes for a single CIP, so take the one with the highest cip_version number
    max_version = max(vars_by_cip['genomics_england_tiering'].keys())
    # Group variants from genomics_england_tiering by tier
    gel_tiered_vars = group_vars_by_tier(vars_by_cip['genomics_england_tiering'][max_version])
    # negneg if no non-tier3 or cip candidate variants
    num_tier1 = len(gel_tiered_vars['TIER1'])
    num_tier2 = len(gel_tiered_vars['TIER2'])
    num_other = len(gel_tiered_vars['OTHER'])
    # Initialise cip_candidates variable to zero, then loop through cips counting variants
    cip_candidates = 0
    for cip in vars_by_cip:
        if cip not in ['genomics_england_tiering', 'exomiser']:
            # There may be multiple interpreted genomes for a single CIP, so take the one with the highest cip_version number
            max_version = max(vars_by_cip[cip].keys())
            cip_candidates += len(vars_by_cip[cip][max_version])
    # Return true if it's a negative negative, otherwise return false.
    if sum((num_tier1, num_tier2, num_other, cip_candidates)) == 0:
        return True
    return False


def group_cases():
    """
    Groups all Guys cases in CIP-API based on whether they are negative negatives
    Returns:
        Dictionary of grouped cases {key = group, value = list of case JSONs from CIP-API}
    """
    # Pull out all cases that are either ready for interpretation or have been reported
    sent_to_gmcs = get_interpretation_request_list(last_status='sent_to_gmcs', sample_type='raredisease')
    report_generated = get_interpretation_request_list(last_status='report_generated', sample_type='raredisease')
    report_sent = get_interpretation_request_list(last_status='report_sent', sample_type='raredisease')
    # Count number of times each proband ID occurs and store in dictionary (key = proband ID, value = count), used later to identify cases with multiple interpretation requests.
    num_requests = Counter([case['proband'] for case in sent_to_gmcs + report_generated + report_sent])
    # Filter cases that are awaiting interpretation to only include Guys cases
    guys_cases = (case for case in sent_to_gmcs if ('RJ1' in case['sites'] or 'RJ101' in case['sites'] or 'GSTT' in case['sites']))
    # Cases will be grouped as below.
    # 'negnegs_one_request' = negneg cases where there are no other ongoing or reported interpretation requests for that patient - can be reported automatically
    # 'negnegs_multiple_requests' = negneg cases where there are other active or reported interpretation requests for that patient (which may not be negneg)
    # 'error' = Error encountered when trying to parse the CIP-API data for this case. Some early pilot cases have broken formatting so they end up here.
    # 'all_other' = Everything else.
    grouped_cases = {
        'negnegs_one_request': [],
        'negnegs_multiple_requests': [],
        'error': [],
        'all_other': []
    }
    for case in guys_cases:
        # Capture interpretation request ID and version
        ir_id = case['interpretation_request_id'].split('-')[0]
        ir_version = case['interpretation_request_id'].split('-')[1]
        participant_id = case['proband']
        # Return JSON from CIP API, use report models v6
        try:
            ir_json = get_interpretation_request_json(ir_id, ir_version, reports_v6=True)
        except:
            grouped_cases['error'].append(case)
            continue
        # Check if case is a negneg
        # Some very old pilot cases have broken formatting causing error here, so catch these with try/except
        try:
            negneg = is_neg_neg(ir_json)
        except:
            grouped_cases['error'].append(case)
            continue
        # If it is negneg, check if there's any other active or reported requests for the same participant
        if negneg and num_requests[participant_id] == 1:
            grouped_cases['negnegs_one_request'].append(case)
        elif negneg:
            grouped_cases['negnegs_multiple_requests'].append(case)
        # Else if it's not negneg
        else:
            grouped_cases['all_other'].append(case)
    return grouped_cases


def main():
    # Get command line arguments
    args = process_arguments()
    out_file = args.output_file
    # Open output file and write headers
    with open(out_file, 'w') as output_file:
        output_file.write('participant_ID\tCIP_ID\tgroup\n')
        # Group cases according to variants found in CIP-API
        grouped_cases = group_cases()
        # Write the results to a tab separated file
        for group in grouped_cases.keys():
            for case in grouped_cases[group]:
                output_file.write(f"{case['proband']}\t{case['interpretation_request_id']}\t{group}\n")

if __name__ == '__main__':
    main()
