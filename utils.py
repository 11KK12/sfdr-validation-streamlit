#### Imports
from PyPDF2 import PdfReader
import openai
import pdfplumber
import numpy as np
from numpy.linalg import norm
import json
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from openpyxl.styles import PatternFill
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Font
from openpyxl.styles import Border, Side
import os
import streamlit as st
import io

# Set up open AI
try:
    openai.api_type = st.secrets["OPENAI_API_TYPE"]
    openai.api_key = st.secrets["OPENAI_API_KEY"]
    openai.api_base = st.secrets["OPENAI_API_BASE"]
    openai.api_version = st.secrets["OPENAI_API_VERSION"]
except:
    openai.api_type = os.environ["OPENAI_API_TYPE"]
    openai.api_key = os.environ["OPENAI_API_KEY"]
    openai.api_base = os.environ["OPENAI_API_BASE"]
    openai.api_version = os.environ["OPENAI_API_VERSION"]

# Functions
def generate_embeddings(text: str) -> list:
    response = openai.Embedding.create(
        input=text, engine="text-embedding-ada-002")
    embeddings = response['data'][0]['embedding']
    return embeddings

def estimate_costs(template_count: int) -> float:
    avg_validation_cost_per_template = 0.07
    custom_extraction_cost_per_page = 0.046817 # with this approach, custom extraction is only used on one page per document -> cost savings
    embedding_costs_per_template = 0.001

    total_costs = (avg_validation_cost_per_template + custom_extraction_cost_per_page + embedding_costs_per_template) * template_count
    
    return total_costs

def get_value(index, name, dataframe):
    try:
        return str(dataframe.at[index, name])
    except:
        return ""

def find_templates_in_pdf(uploaded_file) -> list:
    try:
        pdf_reader = PdfReader(uploaded_file)
        pages = pdf_reader.pages
        num_pages = len(pages)
        templates = []
        i = 0
        last_start_page = 0
        
        # Define all variables that we want to extract (from the first page)
        f_template_article = None
        f_product_name = None
        f_legal_entity_identifier = None

        while i < num_pages:
            page = pages[i]
            text = page.extract_text()
            
            if "asetuksen (eu) 2019/2088" in text.lower():
                # if there has been a previous start page, a new start page means the end of the previous template
                # -> save and reset extracted variables
                if last_start_page != 0:
                    template = {
                        "start_page": last_start_page,
                        "end_page": i,
                        "f_template_article": f_template_article,
                        "f_product_name": f_product_name,
                        "f_legal_entity_identifier": f_legal_entity_identifier
                    }
                    templates.append(template)

                    # Reset variables
                    f_template_article = None
                    f_product_name = None
                    f_legal_entity_identifier = None
            
                # Split text of the first page of the template to find f_template_article, product name, legal identity code
                text = page.extract_text()
                try:
                    f_template_article = int(text.split("2088")[1].split("artiklan")[0].strip())
                except:
                    f_template_article = None
                try:
                    f_product_name = text.split("Tuotenimi")[1].split("Oikeushenkilö")[0].replace(":","").strip()
                except:
                    f_product_name = None
                try:
                    # (legal entity identifier is always 20 digits long; if it is longer, something went wrong in the extraction)
                    f_legal_entity_identifier = text.split("tunnus")[1].split("Ympäristöön")[0].replace(":","").strip()[:20]
                except:
                    # identifier needed for saving and validation
                    if f_product_name != None:
                        f_legal_entity_identifier = f_product_name
                    else:
                        f_legal_entity_identifier = "no_name_found_" + str(i)

                last_start_page = i+1
            i += 1
                
        # add information of last template in PDF to list
        if last_start_page != 0:
            template = {
                "start_page": last_start_page,
                "end_page": num_pages,
                "f_template_article": f_template_article,
                "f_product_name": f_product_name,
                "f_legal_entity_identifier": f_legal_entity_identifier
            }
            templates.append(template) 

        return templates
    
    except:
        return []

def generate_question_embeddings():
    # Define variables for questions (preparation for labelling)
    question_variables = {
        "a_promoted_e_s_characteristics": "Mitä ympäristöön ja/tai yhteiskuntaan littyviä ominaisuuksia tämä rahoitustuote edistää?",
        "a_sustainability_indicators_used": "Mitä kestävyysindikaattoreita käytetään mittaamaan kunkun tämän rahoitustuotteen edistämän ympäristöön tai yhteiskuntaan littyvän ominaisuuden toteutumista?",
        "a_sustainable_investment_objectives": "Mitkä ovat niiden kestävien sijoitusten tavoitteet, jotka rahoitustuotteessa aiotaan tehdä osittain, ja miten kestävä sijoitus edistää näiden tavoitteiden saavuttamista?",
        "a_no_significant_harm": "Miten kestävät sijoitukset, jotka rahoitustuotteessa aiotaan tehdä osittain eivät aiheuta haittaa yhdellekään yynmpäristöön tai yhteiskuntaan liittyvälle kestävälle sijoitustavoitteelle?",          
        "a_principal_adverse_impacts_explaination": "Otetaanko tässä rahoitustuotteessa huomioon pääasialliset haitalliset vaikutukset kestävyystekijöihin?",
        "a_investment_strategy": "Mitä sijoitusstrategiaa tässä rahoitustuotteessa noudatetaan?",
        "a_binding_elements_investment_strategy": "Mitä ovat sijoitusstrategian sitovat osatekijät, joita käytetään valittaessa sijoitukset kunkin tämän rahoitustuotteen edistämän ympäristöön tai yhteiskuntaann littyvän ominaisuuden toteutumiseksi?",
        "a_committed_minimum_rate": "Mikä on sitova vähimmäismäärä, jolla vähennetään niiden sijoitusten laajuuutta, jotka on otettu huomioon ennen sijoitusstrategian soveltamista?",
        "a_policy_good_governance_practice": "Mitkä ovat toimintaperiaatteet, joiden mukaisesti arvioidaan sijoituskohteina olevien yritysten hyviä hallintotapooja?",
        "a_planned_asset_allocation": "Mikä on tälle rahoitustuotteelle suunniteltu varojen allokointi?",
        "a_derivatives_e_s_characteristics": "Miten johdannaisten käyttö saa aikaan rahoitustuotteen edistämien ympäristöön tai yhteiskuntaan liittyvien ominaisuuksien totetumista?",
        "a_minimum_extent_taxonomy_alignment": "Missä määrin kestävät sijoitukset, joillla on ympäristötavoite, ovat EU:n luokitusjärjestelmän mukaisia?", # TODO: form extraction needed here for %?
        "a_invest_fossil_nuclear": "Sijoitetaanko rahoitustuotteessa EU:n luokitusjärjestelmän mukaisiin fossiiliseen kaasuun ja/tai ydinenergiaan liittyviin toimintoihin?", # Tform extraction may be needed here for pie chart? no condition regarding that information though
        "a_minimum_share_env_objective": "Mikä on sellaisten ympäristötavoitteita edistävien kestävien sijoitusten vähimmäisosuus, jotka eivät ole EU:n luokitusjärjestelmän mukaisia?",
        "a_minimum_share_social_investment": "Mikä on yhteiskunnallisesti kestävien sijoitusten vähimmäisosuus?",
        "a_investment_included_in_other": "Mitkä sijoitukset sisältyvät kohtaan “#2 Muu”, mikä on niiden tarkoitus ja sovelletaanko ympäristöön liittyvi tai yhteiskunnallisia vähimmäistason suojatoimia?",
        "a_specific_index_benchmark": "Onko tietty indeksi nimetty vertailuarvoksi, jotta voidaanmäärittää, vastaako tämä rahoitustuote edistämiään ympäristöön ja/tai yhteiskuntaan liittyviä ominaisuuksia?",
        "a_product_information_online": "Mistä voin saada tarkempia tuotekohtaisia tietoja verkossa?"
    }
    # generate embedding for each question variable
    for key, value in question_variables.items():
        emb = generate_embeddings(value)
        question_variables[key] = emb
    
    return question_variables

def extract_template_data(template, uploaded_file, document_analysis_client, question_variables):
    # Get list of all paragraphs in a template with style information
    paragraph_list = []
    pages_text = {}
    fontname_dict = {}
    size_dict = {}

    with pdfplumber.open(uploaded_file) as pdf: 
        current_paragraph = ""
        paragraph_fontname = None
        paragraph_size = None
        page_number = None

        # Consider all pages from template
        # PDF page numbers start at 1 but pdf.pages starts with index 0 --> start_page -1
        for i in range(template["start_page"]-1, template["end_page"]):

            page = pdf.pages[i]
            page_text = ""

            for char in page.chars:
                page_text += char["text"]   
                fontname = char["fontname"]
                fontname_dict[fontname] = fontname_dict.get(fontname, 0) + 1
                size = round(char["size"])
                size_dict[size] = size_dict.get(size, 0) + 1

                if (fontname == paragraph_fontname) & (size == paragraph_size):
                    current_paragraph += char["text"]
                else:
                    if current_paragraph != "":
                        paragraph_list.append({"text": current_paragraph.strip(), "fontname": paragraph_fontname, "size": paragraph_size, "page": page_number})
                    current_paragraph = char["text"]
                    paragraph_fontname = fontname
                    paragraph_size = size
                    page_number = char["page_number"]

            if current_paragraph != "":
                paragraph_list.append({"text": current_paragraph.strip(), "fontname": paragraph_fontname, "size": paragraph_size, "page": page_number})

            pages_text[page.page_number] = page_text

    # Select all paragraphs that are bold and contain a questionmark
    question_list = []
    main_fontname = max(fontname_dict, key = fontname_dict.get)
    main_size = max(size_dict, key = size_dict.get)

    for paragraph in paragraph_list:
        # not all questions are bold -> see Alandsbanken; however, not all paragraphs that contain question marks are actual template questions either -> see Nordea
        # --> relevant paragraph if: contains "?" AND (font is bold OR size is bigger than main size OR font is other than main font)
        if ("?" in paragraph["text"]) and (("bold" in paragraph["fontname"].lower()) or (paragraph["size"] != main_size) or (paragraph["fontname"] != main_fontname)):
            # Problem: question on top of the template box ("Onko tällä rahoitustuotteella kestävä sijoitustavoite?") not extracted in proper order
            if not "onko tällä rahoitustuotteella kestävä sijoitustavoite" in paragraph["text"].lower():
                question_list.append(paragraph)

    # Get all text between two questions as associated answers
    q_n_a_pairs = {}

    for i in range(len(question_list)-1):

        # get text split between current question and next question
        start_question = question_list[i]["text"]
        stop_question = question_list[i+1]["text"]

        # only consider relevant pages of the template to reduce risk of wrong splitting (sometimes questions are refered to in answer to other question)
        first_page = question_list[i]["page"]
        last_page = question_list[i+1]["page"]

        relevant_text = " " # relevant text starts with white space to ensure that the start of the relevant text is never equal to the start question, so that the the answer will always be in split[1], not split[0]
        for j in range(first_page, last_page+1):
            relevant_text += pages_text[j] + " "

        answer = relevant_text.split(start_question)[1].split(stop_question)[0].strip()

        q_n_a_pairs[start_question] = answer

    # get answer for last question
    last_question = question_list[len(question_list)-1]["text"]
    first_page = question_list[len(question_list)-1]["page"]
    last_page = template["end_page"]

    relevant_text = " "
    for j in range(first_page, last_page+1):
        relevant_text += pages_text[j] + " "

    answer = relevant_text.split(last_question)[1].strip() # last answer is everything from last question to end of template

    q_n_a_pairs[last_question] = answer

    # Match questions (and answers) with variables of interested for template validation using embeddddings
    # generate and match embedding for each extracted question with question variable embeddings
    for question, answer in q_n_a_pairs.items():

        quest_emb = generate_embeddings(question)

        for key, value in question_variables.items():

            # calculate cosine similarity between value and quest emb
            cosine = np.dot(quest_emb,value)/(norm(quest_emb)*norm(value))
            
            # if variable above treshhold, add to template dict with cosine similarity; if already in dict, keep value with higher cosine similarity
            #if cosine > 0.85: # TODO: no treshhold here? get a label for each extracted q_n_a pair and then check later which can be used
            if cosine > 0:
                # (this way it is possible that multiple questions have the same label --> keep in mind for validation)
                current_value = template.get(question, {})
                current_cosine = current_value.get("cosine",0)

                if cosine > current_cosine:
                    template[question] = {"label": key, "answer": answer, "cosine": cosine}
    
    # Use Azure AI Document Intelligence to get labeled fields from table on first page ####################
    start_page = template["start_page"]

    #with open(uploaded_file, "rb") as f:
    poller = document_analysis_client.begin_analyze_document(
        "sfdr_template_extraction_paid_version_only_1_page",
        document=uploaded_file.getvalue(),
        pages=start_page
    )
    result = poller.result()

    for document in result.documents:
        for k, v in document.fields.items():
            template[k] = v.value

    return template

def validate(template_fields, i):

    # store validation results for current template
    conditions = []

    # following validation steps only apply to Article 8 products (Article 9 template is slightly different)
    #if get_value("f_template_article",i) != "8":
        #continue

    # Get required variables
    sm_sustainable_investment_object_yes = get_value(i,"sm_sustainable_investment_object_yes", template_fields)
    sm_sustainable_investment_object_no = get_value(i,"sm_sustainable_investment_object_no", template_fields)
    sm_environmental_objective = get_value(i,"sm_environmental_objective", template_fields)
    sm_social_objective = get_value(i,"sm_social_objective", template_fields)
    sm_minimum_sustainable_investment = get_value(i,"sm_minimum_sustainable_investment", template_fields)
    sm_no_sustainable_investment = get_value(i,"sm_no_sustainable_investment", template_fields)
    f_environmental_objective = get_value(i,"f_environmental_objective", template_fields)
    f_social_objective = get_value(i,"f_social_objective", template_fields)
    f_minimum_sustainable_investment = get_value(i,"f_minimum_sustainable_investment", template_fields)
    f_taxonomy_do_not_harm_statement = get_value(i,"f_taxonomy_do_not_harm_statement", template_fields)
    a_planned_asset_allocation = get_value(i,"a_planned_asset_allocation", template_fields)
    f_percentage_aligned_with_e_s_characteristics = get_value(i,"f_percentage_aligned_with_e_s_characteristics", template_fields)
    a_minimum_extent_taxonomy_alignment = get_value(i,"a_minimum_extent_taxonomy_alignment", template_fields)
    f_taxonomy_aligned_fossil_gas_incl_sov_bonds = get_value(i,"f_taxonomy_aligned_fossil_gas_incl_sov_bonds", template_fields)
    f_non_taxonomy_aligned_fossil_gas_incl_sov_bonds = get_value(i,"f_non_taxonomy_aligned_fossil_gas_incl_sov_bonds", template_fields)
    f_taxonomy_aligned_fossil_gas_excl_sov_bonds = get_value(i,"f_taxonomy_aligned_fossil_gas_excl_sov_bonds", template_fields)
    f_non_taxonomy_aligned_fossil_gas_excl_sov_bonds = get_value(i,"f_non_taxonomy_aligned_fossil_gas_excl_sov_bonds", template_fields)
    a_minimum_share_social_investment = get_value(i,"a_minimum_share_social_investment", template_fields)
    a_investment_included_in_other = get_value(i,"a_investment_included_in_other", template_fields)
    a_promoted_e_s_characteristics = get_value(i,"a_promoted_e_s_characteristics", template_fields)
    a_sustainability_indicators_used = get_value(i,"a_sustainability_indicators_used", template_fields)
    a_sustainable_investment_objectives = get_value(i,"a_sustainable_investment_objectives", template_fields)
    sm_environmental_objective_taxonomy = get_value(i,"sm_environmental_objective_taxonomy", template_fields)
    sm_minimum_sustainable_investment_env_taxonomy = get_value(i,"sm_minimum_sustainable_investment_env_taxonomy", template_fields)
    a_minimum_share_env_objective = get_value(i,"a_minimum_share_env_objective", template_fields)

    #################### Check for basic validation conditions ####################
    # basic validation conditions are such conditions that can be simply answered with yes or no
    # e.g., answer for specific questions has been provided and contains a numerical value

    ##### 1. Check that the boxes in the table are ticked (and % if sustainable investments).
    value = True
    comment = ""
    
    # 1A
    if (sm_sustainable_investment_object_yes != "selected") & (sm_sustainable_investment_object_no != "selected"):
        value = False
        comment += "No selection made for sustainable investment object. "
    
    # 1B
    num_selected = 0
    for sm in [sm_environmental_objective, sm_social_objective, sm_minimum_sustainable_investment, sm_no_sustainable_investment]:
        if sm == "selected":
            num_selected += 1
    if num_selected == 0:
        value = False
        comment += "No selection made for promotion of sustainable investment objective. "
    if num_selected > 1:
        value = False
        comment += "More than one selection made for promotion of sustainable investment objective. "

    # 1C
    if sm_environmental_objective == "selected":
        if len([int(s) for s in f_environmental_objective if s.isdigit()]) == 0:
            value = False
            comment += "Environmental objective selected but no minimum % provided. "
    elif sm_social_objective == "selected":
        if len([int(s) for s in f_social_objective if s.isdigit()]) == 0:
            value = False
            comment += "Social objective selected but no minimum % provided. "
    elif sm_minimum_sustainable_investment == "selected":
        if len([int(s) for s in f_minimum_sustainable_investment if s.isdigit()]) == 0:
            value = False
            comment += "Minimum sustainable investment selected but no minimum % provided. "

    # Save validation result
    condition = {
        "name": "Table filled correctly?",
        "description": "Check that the boxes in the table are ticked (and % if sustainable investments).", 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)

    ##### 7. If the product promotes environmental features you should add this statement. Standard mutoinen!
    if (sm_environmental_objective == "selected") or (sm_minimum_sustainable_investment == "selected"):

        value = False
        comment = "Product promotes environmental features and 'No significant harm' statement has not been included."

        if type(f_taxonomy_do_not_harm_statement) == str:
            if len(f_taxonomy_do_not_harm_statement) > 5:
                value = True
                comment = ""
    else:
        value = True
        comment = "'No significant harm' statement not required, product does not promote environmental features."

    # Save validation result
    condition = {
        "name": "'No significant harm' statement provided?",
        "description": "If the product promotes environmental features you should add this statement. Standard mutoinen!", 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)

    ##### 10. A description should be added
    if (type(a_planned_asset_allocation) == str) & (len(a_planned_asset_allocation) > 5):
        value = True
        comment = ""
    else:
        value = False
        comment = "No answer found."

    # Save validation result
    condition = {
        "name": "Description for planned asset allocation added?",
        "description": "Answer to question 'What is the asset allocation planned for this financial product?' should be provided.", 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)

    #### 12. Check that % min 70%  
    value = False
    comment = "Percentage of assets aligned with E/S characteristics not found."

    if type(f_percentage_aligned_with_e_s_characteristics) == str:
        digits = [int(s) for s in f_percentage_aligned_with_e_s_characteristics if s.isdigit()]

        if len(digits) > 0:
            number = int("".join(str(s) for s in digits))

            if number >= 70:
                value = True
                comment = ""
            else:
                value = False
                comment = "Percentage of assets aligned with E/S characteristics below 70 %."

    # Save validation result
    condition = {
        "name": "Percentage of aligned assets min 70%?",
        "description": "Percentage of assets aligned with E/S characteristics should be provided and at least 70 %.", 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)

    #### 13. If you promote environmental features, you should indicate to what extent sustainable investments are in line with the EU taxonomy. If not committed to taxonomy compliant investments should fill in 0%. In other words, you cannot delete this question even if you do not have taxonomy compliant investments if you promote environmental 
    value = False
    comment = "The % of investments in line with EU taxonomy has not been provided."

    for var in [a_minimum_extent_taxonomy_alignment, a_planned_asset_allocation]:
        if type(var) == str:
            # check if answer contains "%" and digits
            if (len([int(s) for s in var if s.isdigit()]) > 0) & ("%" in var):
                value = True
                comment = ""

    # Save validation result
    condition = {
        "name": "EU Taxonomy alignment indicated?",
        "description": "If you promote environmental features, you should indicate to what extent sustainable investments are in line with the EU taxonomy. If not committed to taxonomy compliant investments should fill in 0%. Either way, the answer should contain a %.", 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)

    #### 14. If the fund makes sustainable investments, the extent to which they comply with the EU taxonomy should be indicated using pie charts.
    if sm_sustainable_investment_object_yes == "selected":

        num_numerical_info = 0
        for var in [f_taxonomy_aligned_fossil_gas_incl_sov_bonds, f_non_taxonomy_aligned_fossil_gas_incl_sov_bonds, f_taxonomy_aligned_fossil_gas_excl_sov_bonds, f_non_taxonomy_aligned_fossil_gas_excl_sov_bonds]:
            if type(var) == str:
                if len([int(s) for s in var if s.isdigit()]) > 0:
                    num_numerical_info += 1
        
        if num_numerical_info >= 2:
            value = True
            comment = ""
        else:
            value = False
            comment = "Compliance with EU taxonomy not specified in the pie charts"

    else:
        value = True
        comment = "Information not required, no sustainable investment objective."

    # Save validation result
    condition = {
        "name": "Compliance with EU taxonomy specified in pie charts?",
        "description": "If the fund makes sustainable investments, the extent to which they comply with the EU taxonomy should be indicated using pie charts.", 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)

    #### 16. If the product invests in sustainable investments with a social objective, it should be disclosed what their share is. 
    if sm_social_objective == "selected":
        value = False
        comment = "Minimum share of social objective investments not provided"

        if type(a_minimum_share_social_investment) == str:
            if (len([int(s) for s in a_minimum_share_social_investment if s.isdigit()]) > 0) & ("%" in a_minimum_share_social_investment):
                value = True
                comment = ""
    else:
        value = True
        comment = "Information not required, no social objective."

    # Save validation result
    condition = {
        "name": "Minimum share of sustainable investments with social objective disclosed?",
        "description": "If the product invests in sustainable investments with a social objective, it should be disclosed what their share is.", 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)

    #### 17. If the product invests in other investments "other" should be given in the question details.
    value = False
    comment = "Other investments not specified."
    
    if (type(a_investment_included_in_other) == str):
        if (len(a_investment_included_in_other) > 5):
            value = True
            comment = ""
        
    if type(f_percentage_aligned_with_e_s_characteristics) == str:
        digits = [int(s) for s in f_percentage_aligned_with_e_s_characteristics if s.isdigit()]
        if len(digits) > 0:
            number = int("".join(str(s) for s in digits))
            if number == 100:
                value = True
                comment = "No other investments"

    # Save validation result
    condition = {
        "name": "Other investments specified?",
        "description": "If the product invests in other investments 'other' should be given in the question details.", 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)


    #################### Check for advanced validation conditions ####################
    # advanced validation conditions are such conditions that require reasoning capabilities
    # e.g., "The description should indicate whether the fund promotes E and S or both."
    # the reasoning of a large language model (ChatGPT) is used for this task

    #### 3. The description should indicate whether the fund promotes E and S or both.
    system = """You are provided with a description of environmental and/or social characteristics that are promoted by finanicial product.
    Please carefully read the text and find out if the product promotes environmental characteristics (E), social characteristics (S) or both.
    Your answer has to be one of the following: ["E","S","both","unclear"].
    Your answer must not contain any further explainations.
    """
    text = a_promoted_e_s_characteristics

    response = openai.ChatCompletion.create(
        engine="gpt-4", 
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": text}
        ]
    )
    resp = response['choices'][0]['message']['content']

    if resp == "both":
        value = True
        comment = "Products promotes environmental and social characteristics."
        prev_resp = "environmental and social characteristics"
    elif resp == "E":
        value = True
        comment = "Products promotes environmental characteristics."
        prev_resp = "environmental characteristics"
    elif resp == "S":
        value = True
        comment = "Products promotes social characteristics."
        prev_resp = "social characteristics"
    else:
        value = False
        comment = "No clear explaination provided of what environmental and/or social characteristics are promoted by the product."
    
    prev_value = value

    # Save validation result
    condition = {
        "name": "Promoted E/S characteristics indicated?",
        "description": "The description should indicate whether the fund promotes E and S or both.", 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)

    #### 4. The indicators should be consistent with the previous question.
    if prev_value == False:
        value = False
        comment = "Consistency could not be checked as no clear explaination of promoted E/S characteristics has been provided in previous answer."
    else:
        system = """You are provided with a description of sustainability indicators for a financial product.
        Please carefully read the description and check if it contains indicators that are consistent with the goal to measure the attainment of  """ + prev_resp + """ promoted by this financial product.
        Your answer should be structured as: {"adequate": adequate, "comment": comment}, where adequate is either "True" or "False" and comment is a short explaination of why you made this decision.
        Your answer must not contain anything else.        
        """
        text = a_sustainability_indicators_used

        response = openai.ChatCompletion.create(
            engine="gpt-4", 
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text}
            ]
        )
        resp = response['choices'][0]['message']['content']

        try:
            resp_dict = json.loads(resp)
            if "true" in str(resp_dict["adequate"]).lower():
                value = True
            else:
                value = False
            comment = resp_dict["comment"]
        except:
            value = False
            comment = "Not able to judge the adequancy of the described sustainability indicators."

    # Save validation result
    condition = {
        "name": "Consistent sustainability indicators?",
        "description": "The indicators should be consistent with the previous question.", 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)

    #### 5. If the table on the first page indicates that the fund makes sustainable investments, the objective of the sustainable investment should be described, which should be in line with the objectives of SFDR Article 2.17. In addition, if the table indicates that the fund includes taxonomy investments, the taxonomy objective to be promoted should be stated.

    objectives = """‘sustainable investment’ means an investment in an economic activity that contributes to an environmental objective, as measured, for example, 
    by key resource efficiency indicators on the use of energy, renewable energy, raw materials, water and land, on the production of waste, and greenhouse gas emissions, 
    or on its impact on biodiversity and the circular economy, or an investment in an economic activity that contributes to a social objective, in particular an investment 
    that contributes to tackling inequality or that fosters social cohesion, social integration and labour relations, or an investment in human capital or economically or 
    socially disadvantaged communities, provided that such investments do not significantly harm any of those objectives and that the investee companies follow good 
    governance practices, in particular with respect to sound management structures, employee relations, remuneration of staff and tax compliance"""

    if sm_sustainable_investment_object_yes == "selected":

        value = False
        comment = "" # TODO

        # 5 a. the objective of the sustainable investment should be described, which should be in line with the objectives of SFDR Article 2.17
        if type(a_sustainable_investment_objectives) == str:

            system = """You are provided with text regarding the objectives of sustainable investments of a financial product.
            Please carefully read the text and and check if it is in line with the objectives of the SFDR Article 2.17.
            Your answer should be structured as: {"inline_with_objectives": inline_with_objectives, "comment": comment}, where the value of inline_with_objectives is either "True" or "False" and comment is a short explaination of why you made this decision.
            Your answer must not contain anything else.
            The relevant part of the SFDR Article 2.17 is: """ + objectives

            text = a_sustainable_investment_objectives

            response = openai.ChatCompletion.create(
                engine="gpt-4", 
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": text}
                ]    
            )
            resp = response['choices'][0]['message']['content']

            try:
                resp_dict = json.loads(resp)
                if "true" in str(resp_dict["inline_with_objectives"]).lower():
                    value = True
                else:
                    value = False
                comment = resp_dict["comment"]
            except:
                value = False
                comment = "Not able to check if answer inline with SFDR objectives."
            
        else:
            value = False
            comment = "Sustainable investment object but no answer for objectives provided."

    else:
        value = True
        comment = "Answer not required. No sustainable investment objective."

    # Save validation result
    condition = {
        "name": "Objectives align with SFDR Article 2.17?",
        "description": "If the table on the first page indicates that the fund makes sustainable investments, the objective of the sustainable investment should be described, which should be in line with the objectives of SFDR Article 2.17.", 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)

    #### 5b. If the table on the first page indicates that the fund makes sustainable investments and the fund includes taxonomy investments, the taxonomy objective to be promoted should be stated.

    if sm_sustainable_investment_object_yes == "selected":
        if type(a_sustainable_investment_objectives) == str:

            if (sm_environmental_objective_taxonomy == "selected") or (sm_minimum_sustainable_investment_env_taxonomy == "selected"):
                includes_taxonomy = True
            else:
                includes_taxonomy = False

            if includes_taxonomy:

                system = """You are provided with text regarding the objectives of sustainable investments of a financial product.
                Please carefully read the text and and check if the taxonomy objective to be promoted is stated.
                Your answer should be structured as: {"taxonomy_object_stated": taxonomy_object_stated, "comment": comment}, where the value of taxonomy_object_stated is either "True" or "False" and comment is a short explaination of why you made this decision.
                Your answer must not contain anything else."""

                text = a_sustainable_investment_objectives

                response = openai.ChatCompletion.create(
                    engine="gpt-4", 
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": text}
                    ]    
                )
                resp = response['choices'][0]['message']['content']

                try:
                    resp_dict = json.loads(resp)
                    if "true" in str(resp_dict["taxonomy_object_stated"]).lower():
                        value = True
                    else:
                        value = False
                    comment = resp_dict["comment"]
                except:
                    value = False
                    comment = "Not able to check if taxonomy object stated."

            else:
                value = True
                comment = "Answer not required. No taxonomy investments included."

        else:
            value = False
            comment = "Sustainable investment object but no answer for objectives provided."

    else:
        value = True
        comment = "Answer not required. No sustainable investment objective."

    # Save validation result
    condition = {
        "name": "Promoted taxonomy objective stated?",
        "description": "If the table on the first page indicates that the fund makes sustainable investments and the fund includes taxonomy investments, the taxonomy objective to be promoted should be stated.", 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)


    #### 15. If the fund makes sustainable investments with an environmental objective, it should explain why it invests in sustainable investments that have an environmental objective but do not comply with the taxonomy
    #  if 1.) is selected, let ChatGPT check if 25.) provides reasonable explaination why it invests in sustainable investments that have an environmental objective but do not comply with the taxonomy -> yes/no/unclear
    if sm_sustainable_investment_object_yes == "selected":
    
        system = """You are provided with text regarding the share of sustainable investments in a financial product that are not aligned with the EU Taxonomy.
        Please carefully read the text and and check if it provides a reasonable explaination why the financial product invests in sustainable investments that have an environmental objective but do not comply with the taxonomy.
        Your answer should be structured as: {"reasonable_explaination": reasonable_explaination, "comment": comment}, where the value of reasonable_explaination is either "True" or "False" and comment is a short explaination of why you made this decision.
        Your answer must not contain anything else."""

        text = a_minimum_share_env_objective

        response = openai.ChatCompletion.create(
            engine="gpt-4", 
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text}
            ]    
        )
        resp = response['choices'][0]['message']['content']

        try:
            resp_dict = json.loads(resp)
            if "true" in str(resp_dict["reasonable_explaination"]).lower():
                value = True
            else:
                value = False
            comment = resp_dict["comment"]
        except:
            value = False
            comment = "Not able to check if the explaination is reasonable."

    else:
        value = True
        comment = "Answer not required. No sustainable investment object."

    # Save validation result
    condition = {
        "name": "Non-compliance with taxonomy explained?",
        "description": "If the fund makes sustainable investments with an environmental objective, it should explain why it invests in sustainable investments that have an environmental objective but do not comply with the taxonomy.", 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)

    return conditions

def template_checks_to_excel(tempys, template_checks):
    #Export validation results into structured excel file
    val_result_dfs = {}

    for k,v in template_checks.items():
        # write results to df
        val_results = pd.DataFrame(None, [], ["name", "description", "value", "comment"])

        for i in range(len(v)):
            val_results.at[i, "name"] = v[i]["name"]
            val_results.at[i, "description"] = v[i]["description"]
            val_results.at[i, "value"] = v[i]["value"]
            val_results.at[i, "comment"] = v[i]["comment"]

        val_result_dfs[k] = val_results

    # buffer to use for excel writer
    buffer = io.BytesIO()

    #with pd.ExcelWriter(filename) as writer:
    with pd.ExcelWriter(buffer) as writer:
        for k, df in val_result_dfs.items():
            extracted_data = tempys[tempys["f_legal_entity_identifier"] == k].transpose()
            if len(k) > 30: # excel sheet name cant be longer than 30 characters
                k = k[len(k)-30:]
            df.to_excel(writer, sheet_name=k, index=False)
            extracted_data.to_excel(writer, sheet_name=k, header=[k], startrow=15)
            
    return buffer

def change_excel_design(buffer):
    
    wb = load_workbook(buffer)

    for ws in wb._sheets:
        
        # change column width
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 50
        ws.column_dimensions['C'].width = 10
        ws.column_dimensions['D'].width = 50

        # merge B (2) to D (4) for template data rows
        for i in range(18,67):
            ws.merge_cells(start_row=i, start_column=2, end_row=i, end_column=4)

        # add conditional formatting for True / False
        green_fill = PatternFill(start_color="92D050",end_color="92D050",fill_type="solid")
        red_fill = PatternFill(start_color="C00000",end_color="C00000",fill_type="solid")

        ws.conditional_formatting.add('C2:C15', CellIsRule(operator='equal', formula=["True"], fill=green_fill))
        ws.conditional_formatting.add('C2:C15', CellIsRule(operator='equal', formula=["False"], fill=red_fill))
        
        # style to add borders
        border_style = Side(border_style="medium", color="000000")

        true_count = 0
        false_count = 0

        for row in ws.iter_rows():
            for cell in row:

                # count true and false values (for tab formatting)
                if cell.value == True:
                    true_count += 1
                elif cell.value == False:
                    false_count += 1

                # change text alignment
                cell.alignment = Alignment(wrap_text=True, horizontal="center",vertical="center")
                cell.font = Font(size=11)
                cell.border = None

                # add borders
                if cell.row == 1:
                    cell.font = Font(size=11, bold=True)
                    if cell.column == 4:
                        cell.border = Border(top=border_style, left=None, right=border_style, bottom=border_style)
                    else:
                        cell.border = Border(top=border_style, left=None, right=None, bottom=border_style)
                elif cell.row == 65:
                    if cell.column == 4:
                        cell.border = Border(top=None, left=None, right=border_style, bottom=border_style)
                    else:
                        cell.border = Border(top=None, left=None, right=None, bottom=border_style)
                elif (cell.column == 4) & (cell.row <= 65):
                    cell.border = Border(top=None, left=None, right=border_style, bottom=None)

        # add headers
        # "VALIDATION"
        ws.insert_rows(1)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=4)
        cell = ws.cell(row=1, column=1)
        cell.value = "VALIDATION"
        cell.alignment = Alignment(wrap_text=True, horizontal="center",vertical="center")
        cell.font = Font(size=16, bold=True)
        cell.border = Border(top=border_style, left=border_style, right=None, bottom=border_style)
        ws.cell(row=1, column=2).border = Border(top=border_style, left=None, right=None, bottom=border_style)
        ws.cell(row=1, column=3).border = Border(top=border_style, left=None, right=None, bottom=border_style)
        ws.cell(row=1, column=4).border = Border(top=border_style, left=None, right=border_style, bottom=border_style)
        ws.row_dimensions[1].height = 40

        # "TEMPLATE DATA"
        ws.delete_rows(17)
        ws.insert_rows(17)
        ws.merge_cells(start_row=17, start_column=1, end_row=17, end_column=4)
        cell = ws.cell(row=17, column=1)
        cell.value = "TEMPLATE DATA"
        cell.alignment = Alignment(wrap_text=True, horizontal="center",vertical="center")
        cell.font = Font(size=16, bold=True)
        cell.border = Border(top=border_style, left=border_style, right=None, bottom=border_style)
        ws.cell(row=17, column=2).border = Border(top=border_style, left=None, right=None, bottom=border_style)
        ws.cell(row=17, column=3).border = Border(top=border_style, left=None, right=None, bottom=border_style)
        ws.cell(row=17, column=4).border = Border(top=border_style, left=None, right=border_style, bottom=border_style)
        ws.row_dimensions[17].height = 40
        
        # Change tab color based on validation results
        if false_count == 0:
            # green if all validations positive
            ws.sheet_properties.tabColor = "92D050"
        elif true_count == 0:
            # red if all validations negative
            ws.sheet_properties.tabColor = "C00000" 
        else:
            ratio = true_count / false_count
            # yellow if at least 50 % positive
            if ratio >= 1:
                ws.sheet_properties.tabColor = "FFC000"
            else:
                # red if less than 50 % positive
                ws.sheet_properties.tabColor = "C00000"
                
    wb.save(buffer)
    return buffer
