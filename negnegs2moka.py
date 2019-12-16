"""
v1.1 - AB 2019/12/16
Requirements:
    ODBC connection to Moka
    Python 3.6
    pyodbc

usage: negnegs2moka.py [-h] -i INPUT_FILE -o OUTPUT_FILE

Parses output from negneg_cases.py and books negnegs into Moka

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT_FILE, --input_file INPUT_FILE
                        output from negneg_cases.py
  -o OUTPUT_FILE, --output_file OUTPUT_FILE
                        tab-separated log file
"""
import argparse
from configparser import ConfigParser
import os
import sys
import socket
import pyodbc
import datetime

# Read config file (must be called config.ini and stored in same directory as script)
config = ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.ini"))

def process_arguments():
    """
    Uses argparse module to define and handle command line input arguments and help menu
    """
    # Create ArgumentParser object. Description message will be displayed as part of help message if script is run with -h flag
    parser = argparse.ArgumentParser(description='Parses output from negneg_cases.py and books negnegs into Moka')
    # Define the arguments that will be taken.
    parser.add_argument('-i', '--input_file', required=True, help='output from negneg_cases.py')
    parser.add_argument('-o', '--output_file', required=True, help='tab-separated log file')
    # Return the arguments
    return parser.parse_args()

def run_case_tests(case):
    """
    Patient/case level tests to check if case suitable for automated booking in and reporting
    """
    # Check patient is in Probands_100k table
    if not case.internalPatientID:
        raise Exception("No InternalPatientID found in Probands_100k table")
    # Check patient status is either complete (4) or 100K (1202218839) 
    # If patient is currently having other testing in the lab, overwriting the patient status could cause them to drop off worksheets etc.
    if case.patient_status not in (4, 1202218839):
        raise Exception("Patient status is not 'Complete' or '100K'. Is this patient undergoing other testing in the lab?")
    # Check there's a clinician in the Probands_100K table
    if not case.clinicianID:
        raise Exception("No referring clinician found in Probands_100k table")

def run_ngstest_tests(case, ngstest):
    """
    NGStest level tests to check if case suitable for automated booking in and reporting
    """
    # Check automated reporting of case isn't blocked
    if ngstest.BlockAutomatedReporting != 0:
        raise Exception("Automated reporting of this case is blocked")
    # Check interpretation request IDs match
    if ngstest.IRID != case.intrequestID:
        raise Exception("Interpretation request ID in CIP-API and existing NGSTest request do not match")
    # Check participant IDs match
    if int(ngstest.GELProbandID) != int(case.participantID):
        raise Exception("Participant ID in CIP-API and existing NGSTest request do not match")
    # Check that the exisiting test doesn't already have a different (i.e. not negneg) result code
    if ngstest.ResultCode and ngstest.ResultCode != 1189679668:
        raise Exception("Existing NGSTest request has a different result code to NN")
    # Check that there isn't already a different referring clinician associated with the test
    if ngstest.BookBy != case.clinicianID:
        raise Exception("Existing NGSTest request has a different referring clinician")
    # Check that test status isn't not required
    if ngstest.StatusID == 1202218787:
        raise Exception("NGSTest request already exists with status of NOT REQUIRED")
    # If the existing test already has Check1ID but no result code, or vice versa, print error
    if (ngstest.Check1ID and not ngstest.ResultCode) or (not ngstest.Check1ID and ngstest.ResultCode):
        raise Exception("Existing test either has Check1ID with no result code, or result code with no Check1ID")

class MokaConnector(object):
    """
    Connection to Moka database for use by other functions
    """
    def __init__(self):
        self.cnxn = pyodbc.connect('DRIVER={{SQL Server}}; SERVER={server}; DATABASE={database};'.format(
            server=config.get("MOKA", "SERVER"),
            database=config.get("MOKA", "DATABASE")
            ), 
            autocommit=True
        )
        self.cursor = self.cnxn.cursor()

    def __del__(self):
        self.cnxn.close()

class Case100kMoka(object):
    """
    Represents a 100k case. Instantiated using a GeL participant ID and interpretation request ID (<irid>-<version>)
    """
    def __init__(self, participantID, intrequestID):
        self.participantID = participantID
        self.intrequestID = intrequestID
        self.proband_100k_rows = []
        self.internalPatientID = None
        self.patient_status = None
        self.clinicianID = None
        self.pru = None
        self.ngstests = []


    def get_moka_patientIDs(self, cursor):
        """
        Get information from Moka related to the proband 
        """
        sql = "SELECT InternalPatientID, Referring_Clinician, PatientTrustID FROM Probands_100k WHERE Participant_ID = '{participantID}'".format(participantID=self.participantID)
        self.proband_100k_rows = cursor.execute(sql).fetchall()
        # Only update attributes if a single matching record is found.
        if len(self.proband_100k_rows) == 1:
            self.internalPatientID = self.proband_100k_rows[0].InternalPatientID
            self.clinicianID = self.proband_100k_rows[0].Referring_Clinician
            self.pru = self.proband_100k_rows[0].PatientTrustID

    def get_patient_status(self, cursor):
        """
        Get the patient status from Moka
        """
        if self.internalPatientID:
            sql = "SELECT s_StatusOverall FROM Patients WHERE InternalPatientID = {internalPatientID}".format(internalPatientID=self.internalPatientID)
            self.patient_status = cursor.execute(sql).fetchone().s_StatusOverall

    def get_moka_ngstests(self, cursor):
        """
        Get list of matching 100k NGS test records from Moka
        """
        # Only execute if internal patient ID is known.
        if self.internalPatientID:
            sql = "SELECT NGSTestID, StatusID, IRID, GELProbandID, ResultCode, BookBy, Check1ID, Check1Date, BlockAutomatedReporting FROM dbo.NGSTest WHERE InternalPatientID = {internalPatientID} AND ReferralID = 1199901218".format(
                internalPatientID=self.internalPatientID
                )
            # Capture matching NGSTests
            self.ngstests = cursor.execute(sql).fetchall()

    def set_result_code(self, cursor, ngstest, resultcode, status):
        """
        Update result code and status for a supplied NGStest.
        
        Args:
            ngstest: An NGSTest pyodbc object (as stored in list self.ngstests)
            resultcode: Moka resultcode ID to be stored in NGStest
        """
        # Only execute if internal patient ID is known.
        if self.internalPatientID:
            # Update the result code and set Moka as Checker1
            sql = "UPDATE NGSTest SET ResultCode = {resultcode}, StatusID = {status}, Check1ID = 1201865448, Check1Date = '{today_date}' WHERE NGSTestID = {ngstestid}".format(
                today_date=datetime.datetime.now().strftime(r'%Y%m%d %H:%M:%S %p'),
                resultcode=resultcode,
                status=status,
                ngstestid=ngstest.NGSTestID,
                )
            cursor.execute(sql)
            # Get the human readable result code for recording in patient log
            sql = "SELECT ResultCode FROM ResultCode WHERE ResultCodeID = {resultcode}".format(resultcode=resultcode)
            resultcode_name = cursor.execute(sql).fetchone().ResultCode
            # Get the human readable status for recording in patient log
            sql = "SELECT Status FROM Status WHERE StatusID = {status}".format(status=status)
            status_name = cursor.execute(sql).fetchone().Status
            # Update the patient log
            sql = (
                "INSERT INTO PatientLog (InternalPatientID, LogEntry, Date, Login, PCName) "
                "VALUES ({internalPatientID},  'NGS: NGSTest result code updated to {resultcode_name} and status updated to {status_name} for 100k interpretation request: {intrequestID}', '{today_date}', '{username}', '{computer}');"
                ).format(
                    internalPatientID=self.internalPatientID,
                    resultcode_name=resultcode_name,
                    status_name=status_name,
                    intrequestID=self.intrequestID,
                    today_date=datetime.datetime.now().strftime(r'%Y%m%d %H:%M:%S %p'),
                    username=os.path.basename(__file__),
                    computer=socket.gethostname()
                    )
            cursor.execute(sql)
                 
    def get_moka_details(self, cursor):
        """
        Execute functions to retrieve case details from Moka
        """
        self.get_moka_patientIDs(cursor)
        self.get_moka_ngstests(cursor)
        self.get_patient_status(cursor)

def negnegs_one_request(input_file):
    with open(input_file, 'r') as input_cases:
        return [
            # Capture the first two columns (participant id and interpretation request id)
            row.strip().split('\t')[:2] for row in input_cases.readlines() 
            # Ignore the header line
            if not row.startswith('participant_ID')
            # Only select cases that are negnegs with only one interpretation request
            and row.strip().split('\t')[-1] == 'negnegs_one_request'
            ]

def print_log(log_file, participantid, irid, pru, status, message):
    with open(log_file, 'a') as file_obj:
        file_obj.write(
                "{participantid}\t{irid}\t{pru}\t{status}\t{message}\n".format(
                participantid=participantid,
                irid=irid,
                pru=pru,
                status=status,
                message=message                
            )
        )

def book_in_moka(cases, mokaconn, log_file):
    # Print header for output
    print_log(log_file, 'GeLParticipantID', 'InterpretationRequestID', 'PRU', 'Status', 'Log')
    for case in cases:
        case.get_moka_details(mokaconn.cursor)
        # Test that required case details are in Moka
        try:
            run_case_tests(case)
        # If tests fail, print error to log file and skip to next case
        except Exception as err:
            print_log(log_file, case.participantID, case.intrequestID, case.pru, "ERROR", err)
            continue        
        if len(case.ngstests) > 1:
            # If there are multiple 100k NGS requests for that patient, print error to log file
            print_log(log_file, case.participantID, case.intrequestID, case.pru, "ERROR", "Multiple 100k NGStest request found for this patient")        
        elif len(case.ngstests) < 1:
            # Cases should have already been booked in using the script found in https://github.com/moka-guys/100k_moka_booking_in
            # If case not found in Moka, error and skip to next case
            print_log(log_file, case.participantID, case.intrequestID, case.pru, "ERROR", "No NGSTest request found. Please run 100k_moka_booking_in/100k2moka.py script first")
        # If there's already one 100k NGS request in Moka...       
        elif len(case.ngstests) == 1:
            ngstest = case.ngstests[0]
            # Run NGStest through tests to check if details as expected.
            try:
                run_ngstest_tests(case, ngstest)
            # If tests fail, print error to log file and skip to next case
            except Exception as err:
                print_log(log_file, case.participantID, case.intrequestID, case.pru, "ERROR", err)
                continue
            # If there's not currently a result code, add negneg result code and set status to Negative report:
            if not ngstest.ResultCode:
                case.set_result_code(mokaconn.cursor, ngstest, resultcode=1189679668, status=1202218811)
                print_log(log_file, case.participantID, case.intrequestID, case.pru, "SUCCESS", "Added result code to existing NGSTest request")
            # Otherwise all details match and no updates required, so skip
            else:
                print_log(log_file, case.participantID, case.intrequestID, case.pru, "SKIP", "NGSTest request already exists with matching details")       
        else:
            # Above criteria should catch everything, but if not catch here and print error
            print_log(log_file, case.participantID, case.intrequestID, case.pru, "ERROR", "An unknow error has occurred")

def main():
    # Get command line arguments
    args = process_arguments()
    # Raise error if file doesn't start with expected header row
    with open(args.input_file, 'r') as file_to_check:
        if not file_to_check.read().startswith('participant_ID\tCIP_ID\tgroup'):
            sys.exit('Input file does not contain expected header row. Exiting')
    # Create a list of 100k case objects for negneg cases with only one interpretation request
    negnegs = negnegs_one_request(args.input_file)
    cases = [Case100kMoka(participantID, intrequestID) for participantID, intrequestID in negnegs]
    # Create a Moka connection
    mokaconn = MokaConnector()
    # Book cases into moka
    book_in_moka(cases, mokaconn, args.output_file)


if __name__ == '__main__':
    main()
