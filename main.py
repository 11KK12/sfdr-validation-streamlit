import streamlit as st
import pandas as pd
import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from utils import find_templates_in_pdf, estimate_costs, generate_question_embeddings, extract_template_data, template_checks_to_excel, change_excel_design
from validation import validate

# $ streamlit run /workspaces/sfdr-validation-streamlit/Hello.py --server.enableXsrfProtection false

def run():
  st.set_page_config(
      page_title="SFDR Template Validation",
      page_icon="📄",
  )

  st.write("# SFDR Template Validation")

  # Initialize session state
  if "file_results" not in st.session_state:
      st.session_state.file_results = {}

  uploaded_file = st.file_uploader("Please select a PDF file that contains SFDR templates")
  text_placeholder = st.empty()
  start_button_placeholder = st.empty()
  extraction_progress_bar_placeholder = st.empty()
  validation_progress_bar_placeholder = st.empty()
  download_button_placeholder = st.empty()

  if uploaded_file is not None:
      text_placeholder.empty()
      start_button_placeholder.empty()
      extraction_progress_bar_placeholder.empty()
      download_button_placeholder.empty()
      validation_progress_bar_placeholder.empty()
    
      if uploaded_file.name in st.session_state.file_results:
        output = st.session_state.file_results[uploaded_file.name]
        
        download_button_placeholder.download_button(
          label="📥 Download validation results",
          data=output,
          file_name="validation_results.xlsx",
          type="primary",
          use_container_width=True,
          mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
      else:
        with st.spinner("Working..."):
          # Read PDF documents with PyPDF to find starts of templates
          template_list = find_templates_in_pdf(uploaded_file)
    
          template_count = len(template_list)
            
          if template_count == 0:
            text_placeholder.markdown("No SFDR templates found in the provided document.")
          else:
            #st.markdown(str(template_count) + " template(s) found in the provided document.")
            estimated_costs = estimate_costs(template_count)
            #st.markdown("\nEstimated cost for extraction and validation is {:0.2f} €.\n".format(estimated_costs))
            text_placeholder.markdown(str(template_count) + " template(s) found in the provided document. \nEstimated cost for extraction and validation is {:0.2f} €.\n".format(estimated_costs))

            if start_button_placeholder.button("Start", type="primary", use_container_width=True):
                # TODO hide button after click
                text_placeholder.empty()
                start_button_placeholder.empty()
          
                # Create dataframe to store extraction results
                template_fields = pd.DataFrame()
          
                # Set up Azure AI Document Intelligence
                try:
                    document_ai_endpoint = os.environ["DOCUMENT_AI_ENDPOINT"]
                    document_ai_key = os.environ["DOCUMENT_AI_KEY"]
                except:
                    document_ai_endpoint = st.secrets["DOCUMENT_AI_ENDPOINT"]
                    document_ai_key = st.secrets["DOCUMENT_AI_KEY"]
                    
          
                document_analysis_client = DocumentAnalysisClient(
                    endpoint=document_ai_endpoint, credential=AzureKeyCredential(document_ai_key)
                )
          
                # Generate embeddings of question variables for labelling of extracted paragraphs
                question_variables = generate_question_embeddings()
          
                extraction_bar = extraction_progress_bar_placeholder.progress(0, text="Extracting data...")
          
                # Extract data from template
                for i, template in enumerate(template_list):
          
                    # Show progress
                    extraction_bar.progress(((i+1)/template_count), text="Extracting data from " + template["f_product_name"] + "...")
          
                    template_data = extract_template_data(template, uploaded_file, document_analysis_client, question_variables)
          
                    #Save all results from this template to dataframe
                    id = template_data["f_legal_entity_identifier"]
                    for k,v in template_data.items():
                        if type(v) == dict: # -> q_n_a_pairs
                            key = v["label"]
                            try: 
                                # there might be multiple answers to one label
                                existing_value = template_fields.at[key, id]
                                template_fields.at[key, id] = existing_value + " / " + v["answer"]
                            except:
                                template_fields.at[key, id] = v["answer"]
                        else:
                            template_fields.at[k, id] = v
          
                validation_bar = validation_progress_bar_placeholder.progress(0, text="Validating data...")
          
                template_checks = {}
          
                # Validate extracted data from each template
                tempys = template_fields.transpose()
          
                for i, index in enumerate(tempys.index):
                    validation_bar.progress(((i+1)/len(tempys.index)), text="Validating data from " + tempys.at[index, "f_product_name"] + "...")
                    id = tempys.at[index,"f_legal_entity_identifier"]
                    validation_results = validate(tempys, index)
                    template_checks[id] = validation_results
          
                sheet = template_checks_to_excel(tempys, template_checks)
                output = change_excel_design(sheet)
                st.session_state.file_results[uploaded_file.name] = output
                st.balloons()

                download_button_placeholder.download_button(
                    label="📥 Download validation results",
                    data=output,
                    file_name="validation_results.xlsx",
                    type="primary",
                    use_container_width=True,
                    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

if __name__ == "__main__":
    run()
