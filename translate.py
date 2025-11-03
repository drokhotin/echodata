import csv

dicom_translation_file = 'translated_terms.csv'
siemens_translation_file = 'echo_values_russian.csv'

# translation for echoview (siemens legacy format)
russian={}
with open(siemens_translation_file, encoding='utf-8') as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=',')
    for row in csv_reader:
        russian[row[0]]=row[1]

# translation for dicom
russian_dicom={}
with open(dicom_translation_file, mode='r', encoding='utf-8') as file:
    reader = csv.DictReader(file)  # Assumes first row is header
    for row in reader:
        key = row['English']
        russian_dicom[key.lower()] = {
            'Translation': row['Russian'],
            'Abbreviation': row['Ru-Abbreviation']
             }

# russian.update(russian_dicom)

def translate(text='', dictionary=russian):
    if text in dictionary: return(dictionary[text])
    return(text)


def dicom_translate(word, abbrev=False):
    if not isinstance(word, str): return(str(word))
    translation = russian_dicom.get(word.lower(), {})
    if abbrev:
        if translation.get('Abbreviation', '') !='':
            return(translation['Abbreviation'])
    return translation.get('Translation', word)
