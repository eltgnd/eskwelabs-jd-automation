# Packages
import streamlit as st
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import openai

from user_editable import user_dict

##### Variables
testing_phase = True
page_title = 'Eskwelabs AI-Augmented Job Description Transformer'
SCOPES = ['https://www.googleapis.com/auth/presentations', 'https://www.googleapis.com/auth/drive']
ss = st.session_state
ss['gpt_model'] = '4o_mini'
ss['prompt_instruction'] = user_dict['prompt_instruction']


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

def get_input_documents(google_drive_id):
    '''
    Open the Google Drive folder and extract each document object, outputted as a dictionary
    '''
    
    return ''

def extract_text(doc):
    '''
    Extract a document's text, where the document can be a pdf or a docx file
    '''

    doc_type = get_document_type(doc)

    def extract_docx_text(doc):
        return ''

    def extract_pdf_text(doc):
        return ''        


    if doc_type == 'docx':
        extracted_text = extract_docx_text(doc)
        
    if doc_type == 'pdf':
        extracted_text = extract_pdf_text(doc)

    return extracted_text

def clean_text(str):
    '''
    Cleans a string by removing whitespace
    '''

    return ''

def process_text(str):
    '''
    Trims a string by removing unnecessary text using NLP
    '''

    return ''

def get_prompt(jds, refs, prompt_instruction=ss['prompt_instruction']):
    '''
    Combines the prompt instruction, processed JDs, and processed reference materials
    '''

    return ''
    
def create_doc_from_text(text):
    '''
    Creates a docx file containing the inputted text
    '''

    return ''

def upload_doc(doc, target_id):
    '''
    Uploads the input doc into the Google Drive folder id
    '''

    return ''

##### Initialize
st.set_page_config(page_title=page_title, layout="centered", initial_sidebar_state="auto", menu_items=None)

def main():

    if 'submitted' not in st.session_state:
        st.session_state.submitted = False

    st.title(page_title)
    st.info('For Google Driver folder links, ensure that anyone can view the folder.', icon='ℹ️')

    # User input
    with st.form('slide_info_form'):
        input_folder = st.text_input('Google Drive folder link containing JD Documents', help='Ensure that anyone can view the folder')
        ref_folder = st.text_input('Google Drive folder link containing methodology/reference materials', help='Ensure that anyone can view the folder')
        output_folder = st.text_input('Google Drive folder link where new JD documents will be uploaded', help='Ensure that anyone can edit the folder')
        user_key = st.text_input("ChatGPT API Key")
        submitted = st.form_submit_button('Submit', on_click=submitted_done)


    if st.session_state.submitted:

        # Authenticate with Google
        creds = authenticate_google()

        # Submit auth
        if st.button('Start Automation'):
            
            # Set global variables
            ss['api_key'] = st.secrets['testing']['api_key'] if testing_phase else user_key

            ids = {'input_id':input_folder, 'ref_id':ref_folder, 'output_id':output_folder}
            if testing_phase:
                for var_name in ids.keys():
                    ss[var_name] = extract_id(st.secrets['testing'][var_name])
            else:
                for var, var_name in enumerate(ids):
                    ss[var_name] = extract_id(var)

            ss['jd'] = []
            ss['ref'] = []


            # Collect methodology docs
            ref_documents = get_input_documents(ss['ref_folder'])
            for doc in ref_documents:
                extracted_text = extract_text(doc)
                cleaned_text = clean_text(extracted_text)
                final_text = process_text(cleaned_text)

                ss['jd'].append(cleaned_text)

            # Collect input JDs
            input_documents = get_input_documents(ss['input_folder'])
            for doc in input_documents:
                extracted_text = extract_text(doc)
                cleaned_text = clean_text(extracted_text)
                final_text = process_text(cleaned_text)

                ss['ref'].append(extracted_text)

            # Get prompt
            ss['prompt'] = get_prompt(ss['jd'], ss['ref'])

            # Get output
            if is_token_within_limit(ss['prompt']):
                ss['output'] = get_output()
                ss['is_output_processed'] = True
            else:
                st.warning('Token limit exceeded. Please temporarily remove JD documents to minimize text')
                ss['is_output_processed'] = False


            # Prepare output
            if ss['is_output_processed']:
                for text in ss['output']:
                    doc = create_doc_from_text(text)
                    upload_doc(doc, ss['output_id'])
                
                st.success('Automation completed!')
                output_link = get_output_link(folder_id)
                st.link_button('View folder', output_link)

if __name__ == "__main__":
    main()