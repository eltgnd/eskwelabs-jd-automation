# Packages
import streamlit as st
import json
import pdfplumber
import re
import io
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

import openai
import tiktoken

from user_editable import user_dict

##### Variables
page_title = 'Eskwelabs AI-Augmented Job Description Transformer'
SCOPES = ['https://www.googleapis.com/auth/presentations', 'https://www.googleapis.com/auth/drive']
ss = st.session_state
ss['creds'] = ''

##### Initialize
st.set_page_config(page_title=page_title, layout="centered", initial_sidebar_state="auto", menu_items=None)

##### Callable
def authenticate_google():
    '''
    Authentication process for Google, requires user to input auth_id
    '''
    creds = None
    if 'credentials' in st.session_state:
        creds = Credentials.from_authorized_user_info(st.session_state['credentials'], SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = {
                "web": {
                    "client_id": st.secrets["google"]["client_id"],
                    "client_secret": st.secrets["google"]["client_secret"],
                    "auth_uri": st.secrets["google"]["auth_uri"],
                    "token_uri": st.secrets["google"]["token_uri"],
                    "redirect_uris": st.secrets["google"]["redirect_uris"][0]
                }
            }
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=st.secrets["google"]["redirect_uris"][0]
            )
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            st.link_button('Log-in with Google', auth_url, icon='🔑')
            
            # User must enter the authorization code manually
            redirect_link = st.text_input("Enter the redirect link:")
            
            if redirect_link:
                try:
                    # Extract the code
                    auth_code = redirect_link.split('&')[1][5:]
                    flow.fetch_token(code=auth_code)
                    creds = flow.credentials
                    st.session_state['credentials'] = json.loads(creds.to_json())
                    st.success("Authentication successful! You can now proceed.")
                except Exception as e:
                    st.error(f"Authentication failed: {e}")
                    st.stop()

    return creds

def submitted_done():
    '''
    Callback function for modifying submit button behavior
    '''
    st.session_state.submitted = True

def extract_id(google_drive_link: str):
    '''
    Extract id from Google Drive link
    '''
    return google_drive_link.split('/')[-1].split('?')[0]

def get_document_type(doc):
    '''
    Determine if the passed in object is a docx or pdf file
    '''
    if doc['mimeType'] == 'application/pdf':
        return 'pdf'
    else:
        return 'docx'

def get_input_documents(google_drive_id):
    '''
    Open the Google Drive folder and extract each document/pdf file, output metadata as a dictionary
    '''
    service = build('drive', 'v3', credentials=ss['creds'])
    query = f"'{google_drive_id}' in parents"
    results = service.files().list(q=query).execute()
    return results.get('files', [])

def extract_docx_text(doc):
    '''
    Extract a docx file's text content
    '''
    docs_service = build('docs', 'v1', credentials=ss['creds'])

    # Get the document content
    document = docs_service.documents().get(documentId=doc['id']).execute()

    # Extract text from document structure
    text = ""
    for element in document.get("body", {}).get("content", []):
        if "paragraph" in element:
            for run in element["paragraph"].get("elements", []):
                if "textRun" in run:
                    text += run["textRun"]["content"]

    return text.strip()

def download_pdf_file(doc):
    '''
    Download a pdf file given its file id from Google Drive
    '''
    service = build('drive', 'v3', credentials=ss['creds'])
    request = service.files().get_media(fileId=doc['id'])
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    
    output_path = f"downloaded_files/{doc['name']}"
    with open(output_path, "wb") as f:
        f.write(file_stream.getvalue())

    return output_path

def extract_pdf_text(pdf_path):
    '''
    Extracts text from a PDF file stored locally
    '''
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])

def extract_text(doc):
    '''
    Extract a document's text, where the document is a dictionary containing information about the Google Drive file.
    '''
    doc_type = doc['mimeType']
    
    if doc_type == 'application/pdf':
        output_path = download_pdf_file(doc) # Save the PDF file locally
        return extract_pdf_text(output_path)
    
    else:
        return extract_docx_text(doc)

def clean_text(text):
    '''
    Cleans a string by removing irrelevant strings
    '''

    # Removes strings of the form "X of 8 3/6/2025, 9:16 AM" found in downloaded PDF files
    # - `\d+ of 8` matches the page number format (X of 8)
    # - `\s+\d{1,2}/\d{1,2}/\d{4}, \d{1,2}:\d{2} (AM|PM)` matches the date and time
    pattern = r"\d+ of 8\s+\d{1,2}/\d{1,2}/\d{4}, \d{1,2}:\d{2} (AM|PM)"
    cleaned_text = re.sub(pattern, "\n", text)

    # Removes new lines
    # cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    return cleaned_text

def get_prompt(refs, jds, prompt_instruction=user_dict['prompt_instruction']):
    '''
    Combines the prompt instruction, processed JDs, and processed reference materials
    '''
    prompt = prompt_instruction
    for ind, ref in enumerate(refs):
        prompt += f'\n### REFERENCE MATERIAL {ind+1} ###\n{ref}'
    for ind, jd in enumerate(jds):
        prompt += f'\n### JOB DESCRIPTION {ind+1} ###\n{jd}'

    return prompt

def create_google_doc(doc_title, content):
    """
    Create a Google Document inside a given folder and insert text.
    """

    drive_service = build("drive", "v3", credentials=ss['creds'])
    docs_service = build("docs", "v1", credentials=ss['creds'])

    # Create a new Google Doc inside the folder
    file_metadata = {
        "name": f'{doc_title} (AI-Augmented)',
        "mimeType": "application/vnd.google-apps.document",
        "parents": [ss['output_id']]
    }
    file = drive_service.files().create(body=file_metadata, fields="id").execute()
    doc_id = file.get("id")
    font = user_dict['font']
    
    clean_content = re.sub(r"\*\*(.*?)\*\*", r"\1", content)
    lines = clean_content.split("\n")
    requests = []

    index = 1
    
    for i, line in enumerate(lines):
        requests.append({
            "insertText": {
                "location": {"index": index},
                "text": line + "\n"
            }
        })
        
        end_index = index + len(line) + 1
        
        if i == 0:
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": index, "endIndex": end_index},
                    "paragraphStyle": {"namedStyleType": "HEADING_1"},
                    "fields": "namedStyleType"
                }
            })
        elif len(line.split()) < 5 and ":" in line:
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": index, "endIndex": end_index},
                    "paragraphStyle": {"namedStyleType": "HEADING_2"},
                    "fields": "namedStyleType"
                }
            })
        
        index = end_index
    
    docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

def is_token_within_limit(text):
    '''
    Checks if the input text is within the context limit of the used OpenAI LLM
    '''
    encoder = tiktoken.encoding_for_model('gpt-4o')  # Using GPT-4o tokenizer
    tokens = encoder.encode(text)

    return len(tokens) <= user_dict['gpt_input_limit']

def get_output(prompt):
    '''
    Make the API call to OpenAI
    '''

    client = openai.OpenAI(api_key = ss['api_key'])
    response = client.chat.completions.create(
        model = user_dict['gpt_model'],
        messages = [
            {"role": "system", "content": "You are an NLP and data visualization expert analyzing qualitative survey feedback."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
    )

    response_text = response.choices[0].message.content
    return [i.strip() for i in response_text.split('[DIVIDER]')]

def get_output_link(folder_id):
    '''
    Returns a hyperlink that leads to the Google Drive folder
    '''
    return f'https://drive.google.com/drive/folders/{folder_id}?usp=drive_link'

def main():

    if 'submitted' not in ss:
        ss['submitted'] = False

    st.title(page_title)
    st.info('For Google Driver folder links, ensure that anyone can view the folder.', icon='ℹ️')

    testing_phase = st.toggle('Prototype Mode', help='Turning this on means using test inputs and reference materials. Otherwise, input your own Google Drive folders and documents.')

    # User input
    with st.form('slide_info_form'):
        input_folder = st.text_input('Google Drive folder link containing JD Documents', help='Ensure that anyone can view the folder')
        ref_folder = st.text_input('Google Drive folder link containing methodology/reference materials', help='Ensure that anyone can view the folder')
        output_folder = st.text_input('Google Drive folder link where new JD documents will be uploaded', help='Ensure that anyone can edit the folder')
        uploaded_api_key_file = st.file_uploader("Text file containing the ChatGPT API Key", type=["txt"], help='The text (.txt) file is assumed to only contain the API key and no other string.')
        submitted = st.form_submit_button('Submit', on_click=submitted_done)


    if ss['submitted']:

        # Authenticate with Google
        ss['creds'] = authenticate_google()
   
        # Submit auth
        if st.button('Start Automation'):
            
            with st.status('Running'):
                
                st.write('Setting up...')
                # Set global variables
                # ss['api_key'] = st.secrets['testing']['api_key'] if testing_phase else user_key
                user_key = uploaded_api_key_file.read().decode("utf-8").strip()
                ss['api_key'] = user_key

                ids = {'input_id':input_folder, 'ref_id':ref_folder, 'output_id':output_folder}
                if testing_phase:
                    for var_name in ids.keys():
                        ss[var_name] = extract_id(st.secrets['testing'][var_name])
                else:
                    for var, var_name in enumerate(ids):
                        ss[var_name] = extract_id(var)

                # Instantiate to append documents from 
                ss['jd'] = []
                ss['ref'] = []

                
                st.write('Collecting methodology documents...')
                # Collect methodology docs
                ref_documents = get_input_documents(ss['ref_id'])
                for doc in ref_documents:
                    extracted_text = extract_text(doc)
                    cleaned_text = clean_text(extracted_text)
                    ss['jd'].append(cleaned_text)

                st.write('Collecting JD documents...')
                # Collect input JDs
                input_documents = get_input_documents(ss['input_id'])
                for doc in input_documents:
                    extracted_text = extract_text(doc)
                    cleaned_text = clean_text(extracted_text)
                    ss['ref'].append(cleaned_text)

                st.write('Preparing the prompt...')
                # Get prompt
                ss['prompt'] = get_prompt(ss['jd'], ss['ref'])
                

                st.write('Calling the API...')
                # Get output
                if is_token_within_limit(ss['prompt']):
                    ss['output'] = get_output(ss['prompt'])
                    ss['is_output_processed'] = True
                else:
                    st.warning('Token limit exceeded. Please remove documents to minimize text')
                    ss['is_output_processed'] = False

                st.write('Uploading new JDs...')
                # Prepare output
                if ss['is_output_processed']:
                    for output in ss['output']:
                        title = output.split('\n')[0]
                        create_google_doc(title, output)

            st.success('Automation completed!')
            output_link = get_output_link(ss['output_id'])
            st.link_button('View folder', output_link)

if __name__ == "__main__":
    main()
