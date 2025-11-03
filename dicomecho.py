from pynetdicom import AE, evt
from pydicom.dataset import Dataset
from pynetdicom.sop_class import (
    ComprehensiveSRStorage,
    StudyRootQueryRetrieveInformationModelFind,
    Verification
)
from typing import List, Dict, Optional
from copy import deepcopy
import pandas as pd
from math import log10, trunc


def get_studies(server_ip, server_aet, client_aet, port=4242, number=10):
    """
    Query DICOM server and return list of studies with proper error handling
    
    Args:
        server_ip (str): PACS server IP
        server_aet (str): PACS AE Title
        client_aet (str): Client AE Title
        port (int): DICOM port (default: 104)
    
    Returns:
        list: List of study datasets or None if error
    """
    ae = AE(ae_title=client_aet)
    ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)
    
    studies = []
    
    try:
        # Explicit association handling (avoiding context manager issues)
        assoc = ae.associate(server_ip, port, ae_title=server_aet)
        
        if not assoc.is_established:
            print(f"Association failed with {server_aet}")
            if assoc.is_rejected:
                print(f"Rejection reason: {assoc.rejected_permanent_or_transient}")
            return None
            
        try:
            ds = Dataset()
            ds.QueryRetrieveLevel = "STUDY"
            ds.StudyInstanceUID = ''
            ds.StudyDate = ''
#            ds.StudyDescription = ''
            ds.PatientName = ''
#            ds.PatientID = ''
            ds.PatientBirthDate = ''  # (0010,0030) - Format: 'YYYYMMDD'
#            ds.PatientSex = ''        # (0010,0040) - Values: 'M', 'F', 'O' (Other), or empty
#            ds.StationName = ''
#            ds.ManufacturerModelName = ''
#            ds.Manufacturer = ''
            
            responses = assoc.send_c_find(ds, StudyRootQueryRetrieveInformationModelFind)
            for status, identifier in responses:
                if status and status.Status in (0xFF00, 0xFF01) and identifier:
                    studies.append(identifier)
                    
        finally:
            # Always release the association
            assoc.release()
            
    except Exception as e:
        print(f"DICOM query failed: {str(e)}")
        return None
    
    return studies
  


def has_comprehensive_sr(server_ip, server_aet, study_instance_uid, client_aet='MY_CLIENT', port=104):
    """
    Check if a study contains Comprehensive SR reports
    
    Args:
        server_ip (str): PACS server IP
        server_aet (str): PACS AE Title
        study_instance_uid (str): Study Instance UID to check
        client_aet (str): Client AE Title (default: 'MY_CLIENT')
        port (int): DICOM port (default: 104)
    
    Returns:
        bool: True if study contains Comprehensive SR, False otherwise
        int: Number of Comprehensive SRs found (optional - see below)
    """
    ae = AE(ae_title=client_aet)
    ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)
    ae.add_requested_context(ComprehensiveSRStorage)
    
    try:
        assoc = ae.associate(server_ip, port, ae_title=server_aet)
        if not assoc.is_established:
            print(f"Association failed with {server_aet}")
            return False  # or (False, 0) if using count version
            
        try:
            # Query for Comprehensive SR series in this study
            ds = Dataset()
            ds.QueryRetrieveLevel = "SERIES"
            ds.StudyInstanceUID = study_instance_uid
            ds.Modality = 'SR'
            ds.SOPClassUID = ComprehensiveSRStorage  # Specific to Comprehensive SR
            
            responses = assoc.send_c_find(ds, StudyRootQueryRetrieveInformationModelFind)
            
            # Count how many Comprehensive SRs we find
            sr_count = 0
            for status, identifier in responses:
                if status and status.Status in (0xFF00, 0xFF01) and identifier:
                    sr_count += 1
                    # If you just want to know if ANY exist, you could return True here
            
            return sr_count > 0  # Returns True/False
            # Alternatively return sr_count if you want the actual count
            
        finally:
            assoc.release()
            
    except Exception as e:
        print(f"Error checking for Comprehensive SR: {str(e)}")
        return False  # or (False, 0)
      
      


def retrieve_comprehensive_srs(
    server_ip: str,
    server_aet: str,
    study_instance_uid: str,
    client_aet: str = "MY_CLIENT",
    port: int = 104
) -> List[Dict]:
    """Retrieve SRs with complete content extraction"""
    ae = AE(ae_title=client_aet)
    ae.add_requested_context(ComprehensiveSRStorage)
    ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)
    
    results = []
    assoc = None
    
    try:
        assoc = ae.associate(server_ip, port, ae_title=server_aet)
        if not assoc or not assoc.is_established:
            print("Association failed")
            return []
        
        # Query for SR instances
        ds = Dataset()
        ds.QueryRetrieveLevel = "IMAGE"
        ds.StudyInstanceUID = study_instance_uid
        ds.Modality = "SR"
        ds.SOPClassUID = ComprehensiveSRStorage
        ds.SOPInstanceUID = ""
        ds.StudyDate = ''
        ds.StudyDescription = ''
        ds.PatientName = ''
        ds.PatientID = ''
        ds.PatientBirthDate = ''  # (0010,0030) - Format: 'YYYYMMDD'
        ds.PatientSex = ''        # (0010,0040) - Values: 'M', 'F', 'O' (Other), or empty
        ds.StationName = ''
        ds.ManufacturerModelName = ''
        ds.Manufacturer = ''
        
        # Request ALL attributes to get complete content
        ds.ContentSequence = ''
        ds.VerificationFlag = ''
        ds.ContentDate = ''
        ds.ContentTime = ''
        
        responses = assoc.send_c_find(ds, StudyRootQueryRetrieveInformationModelFind)
        for status, identifier in responses:
            if status and status.Status in (0xFF00, 0xFF01) and identifier:
                try:
                    results.append({
                        'sop_instance_uid': identifier.SOPInstanceUID,
                        'content_date': identifier.get('ContentDate', ''),
                        'content_time': identifier.get('ContentTime', ''),
                        'verification_status': identifier.get('VerificationFlag', 'UNVERIFIED'),
                        'study_date': identifier.get('StudyDate', ''),
                        'study_description': identifier.get('StudyDescription', ''),
                        'patient_name': identifier.get('PatientName', ''),
                        'patient_id': identifier.get('PatientID', ''),
                        'patient_birth_date': identifier.get('PatientBirthDate', ''),
                        'patient_sex': identifier.get('PatientSex', ''),
                        'station_name': identifier.get('StationName', ''),
                        'model_name': identifier.get('ManufacturerModelName', ''),
                        'manufacturer': identifier.get('Manufacturer', ''),
                        
           

                        'content': extract_sr_content(identifier)
                    })
                except Exception as e:
                    print(f"Error processing SR {identifier.SOPInstanceUID}: {str(e)}")
    
    finally:
        if assoc and assoc.is_established:
            assoc.release()
    
    return results

def extract_sr_content(dataset: Dataset) -> Dict:
    """Enhanced SR content extractor that digs into nested structures"""
    def parse_content_item(item):
        """Recursively parse content sequence items"""
        result = {
            'concept': item.get('ConceptNameCodeSequence', [{}])[0].get('CodeMeaning', ''),
            'value_type': item.get('ValueType', ''),
            'value': '',
            'nested': []
        }
        
        # Handle different value types
        if result['value_type'] == 'TEXT':
            result['value'] = str(item.get('TextValue', ''))
        elif result['value_type'] == 'NUM':
            num_seq = item.get('MeasuredValueSequence', [{}])[0]
            result['value'] = f"{num_seq.get('NumericValue', '')} {num_seq.get('MeasurementUnitsCodeSequence', [{}])[0].get('CodeValue', '')}"
        elif result['value_type'] == 'CODE':
            result['value'] = item.get('ConceptCodeSequence', [{}])[0].get('CodeMeaning', '')
        
        # Recursively handle nested content
        if hasattr(item, 'ContentSequence'):
            for nested_item in item.ContentSequence:
                result['nested'].append(parse_content_item(nested_item))
        
        return result

    content = {
        'title': str(dataset.get('DocumentTitle', '')),
        'observations': []
    }
    
    try:
        if hasattr(dataset, 'ContentSequence'):
            for top_item in dataset.ContentSequence:
                content['observations'].append(parse_content_item(top_item))
    except Exception as e:
        print(f"Error extracting SR content: {str(e)}")
    
    return content
  
## recursive extraction of data from nested json
def decode(data, context=None):

    if context:
        newcontext = deepcopy(context)
    else:
        newcontext = {}
   
    if isinstance(data, dict):
        if data.get('value_type')=='NUM':
            if ' ' in data.get('value'):
                newcontext['Value'], newcontext['Units'] = data.get('value').split(' ', 1)
            else: 
                newcontext['Value'], newcontext['Units'] = data.get('value'), ''
            newcontext['measurement'] = data.get('concept')
            newcontext.update(decode(data.get('nested')))
            return(deepcopy(newcontext))
           
        if data.get('value_type') and data.get('concept'):
            newcontext[data.get('concept')] = data.get('value')

        if data.get('nested') and data.get('nested')!=[]:
            return(decode(data.get('nested'), deepcopy(newcontext)))
                
    if isinstance(data, list):
        non_context_items=[]
        for item in data:
            if item.get('value_type')!='NUM' and item.get('nested')==[]:
  #              print(item)
                newcontext[item.get('concept')] = item.get('value')
            else:
                non_context_items.append(item)
        if non_context_items==[]: return(deepcopy(newcontext))
        decoded_items = []
        for item in non_context_items:
            decoded = decode(item, deepcopy(newcontext))
            if isinstance(decoded, list): decoded_items.extend(decoded)
            else: decoded_items.append(decoded)
        return(decoded_items)
        
        

    return(deepcopy(newcontext))

            

# removes duplicates and values that were used to derive derived values (and put them in "derived_from" list in derived value)
def unique_decode(l):
    decoded = decode(l)
    unique = []
    derivated = []

    # makes list of "aggregated" results (mean, last etc.)
    for item in decoded:
        if item.get('Derivation') or item.get('Selection Status'):
            item_copy = item.copy()
            item_copy.pop('Derivation', None)
            item_copy.pop('Selection Status', None)
            item_copy.pop('Value', None)
            derivated.append(item_copy)
            for orig_item in decoded:
                orig_item_copy = orig_item.copy()
                deriv_value = orig_item_copy.pop('Value', None)
                if orig_item_copy == item_copy:
                    if item.get('Derivated_from'):
                        item['Derivated_from'].append(orig_item.get('Value'))
                    else:
                        item['Derivated_from'] = [orig_item.get('Value')]
            derivated.append(item_copy)

    # makes list of unique results (excluding those used for derivation of mean, last etc.)
    for item in decoded:
        if item not in unique:
            item_copy = item.copy()
            item_copy.pop('Value', None)
            if item_copy not in derivated:
                unique.append(item)
    
    return(unique)


def dicom_to_echo(observations, metadata,
                  file_path = "/Users/okhotin/Downloads/DICOM_SR_translate.xlsx"):

    #file_path = "/Users/okhotin/Downloads/DICOM_SR_translate.xlsx"
    df = pd.read_excel(file_path, engine='openpyxl')
    df = df.fillna('')

    df.columns = df.columns.str.replace('.', ' ')
    df['code'] = df['code'].str.upper()

    all_fields = [column for column in df.columns if column not in ['code', 'coefficient', 'precision', 'depth', 'priority']]
    fields_abbr = [''.join([word[0] for word in field.split(' ')]).upper() for field in all_fields]

    fields_dict = dict(zip(fields_abbr, all_fields))

    values = {}
    all_obs = []

    for index, row in df.iterrows():
        if row.code.upper()!='NO':
            if row.fields == '': row.fields = 'FS, M'
            fields = [fields_dict.get(field.upper(), field) for field in row.fields.replace(' ', '').split(',')]
            ob = [o for o in observations if all([o.get(field, '') == row.get(field, 2) for field in fields])]
            if len(ob)>0: 
                all_obs.append([row.code, ob])
                if row.code not in values.keys():
                    values[row.code] = {}
                    if ob[0].get('Value', '')!='': 
                        value = float(ob[0].get('Value', ''))
                        if row.coefficient!='':
                            value = value * float(row.coefficient)
                        if row.precision!='':
                            if int(row.precision)==0:
                                value = round(value)
                            else:
                                value = round(value, int(row.precision))    
                        else: 
                            value = round(value, 2-trunc(log10(abs(value))))
                        values[row.code]['value'] = value
                        if row.priority!='':
                            values[row.code]['priority'] = int(row.priority)
                        values[row.code]['units'] = row.Units
                        values[row.code]['coefficient'] = row.coefficient
                    elif row["Finding site"]=='Myocardial wall':
                        values[row.code]['value'] = row['Cardiac Wall Motion']
                        values[row.code]['morphology'] = row['Associated Morphology']
                    else:
                        values[row.code]['value'] = 'Other'
                else:
                    if ob[0].get('Value', '')!='': 
                        value = float(ob[0].get('Value', ''))
                        if row.coefficient!='':
                            value = value * float(row.coefficient)
                        if row.precision!='':
                            value = round(value, int(row.precision))
                        else: 
                            value = round(value, 2-trunc(log10(abs(value))))
                        if row.priority!='':
                            if values[row.code]['priority'] < int(row.priority):
                                values[row.code]['priority'] = int(row.priority)
                                values[row.code]['value'] = value
                        values[row.code]['units'] = row.Units
                        values[row.code]['coefficient'] = row.coefficient

    echo={}
    for key in metadata.keys():
        echo[f"_{key}".upper()]=str(metadata[key])
    
    for key in values.keys():
        echo[str(key)] = values[key]['value']

    return(echo, values)

