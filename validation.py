import openai
import json

def get_value(index, name, dataframe):
    try:
        return str(dataframe.at[index, name])
    except:
        return ""

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
    a_no_significant_harm = get_value(i,"a_no_significant_harm", template_fields)
    a_accounting_indicators_on_sustainability_factors = get_value(i,"a_accounting_indicators_on_sustainability_factors", template_fields)
    a_principal_adverse_impacts_explaination = get_value(i,"a_principal_adverse_impacts_explaination", template_fields)
    a_alignment_with_OECD_guidelines = get_value(i,"a_alignment_with_OECD_guidelines", template_fields)

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
    
    # 1B / 1C
    if sm_sustainable_investment_object_yes == "selected":
        relevant_sms = [sm_environmental_objective, sm_social_objective]
    elif sm_sustainable_investment_object_no == "selected":
        relevant_sms = [sm_minimum_sustainable_investment, sm_no_sustainable_investment]
    else:
        relevant_sms = []
   
    num_selected = 0
    for sm in relevant_sms:
        if sm == "selected":
            num_selected += 1
    if num_selected == 0:
        value = False
        comment += "No selection made for promotion of sustainable investment objective. "

    # apparently no problem if more than one of the selection marks is selected
    """if num_selected > 1:
        value = False
        comment += "More than one selection made for promotion of sustainable investment objective. " """

    # 1D
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
        "description": 'Check that the boxes in the table are ticked (and % if sustainable investments). / Tarkista että taulukon ruutuihin täytetty ruksit (ja %-osuus, jos kestäviä sijoituksia). [Table page 1]', 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)

    ##### 7. If the product promotes environmental features you should add this statement. Standard mutoinen!
    if (sm_environmental_objective == "selected") or (sm_minimum_sustainable_investment == "selected"):

        value = False
        comment = "Product promotes environmental features and 'No significant harm' statement has not been included."

        relevant_text = a_no_significant_harm + a_alignment_with_OECD_guidelines
        do_not_harm_statement_excerpt = 'EU:n luokitusjärjestelmässä vahvistetaan "ei merkittävää haittaa" -periaate'

        if do_not_harm_statement_excerpt in relevant_text:
            value = True
            comment = ""
            
    else:
        value = True
        comment = "'No significant harm' statement not required, product does not promote environmental features."

    # Save validation result
    condition = {
        "name": "'No significant harm' statement provided?",
        "description": 'If the product promotes environmental features you should add this statement. Standard mutoinen! / Jos tuote edistää ympäristöominaisuuksia tulee lisätä tämä statement. Vakio mutoinen! [Standard Statement below "How do the sustainable investments that the financial product partially intends to make, not cause significant harm to any environmental or social sustainable investment objective?"]', 
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
        "description": 'Answer to question "What is the asset allocation planned for this financial product?" should be provided. / Tulee lisätä kuvaus tähän. ["What is the asset allocation planned for this financial product?"]', 
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

    if value == False:
        if len([int(s) for s in a_minimum_extent_taxonomy_alignment if s.isdigit()]) > 0:
            value = True
            comment = ""
        
    # Save validation result
    condition = {
        "name": "Percentage of aligned assets min 70%?",
        "description": 'Percentage of assets aligned with E/S characteristics should be provided and at least 70 %. / Tarkista että % min 70% [Boxes below "To what minimum extent are sustainable investments with an environmental objective aligned with the EU Taxonomy?"]', 
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
        "description": 'If you promote environmental features, you should indicate to what extent sustainable investments are in line with the EU taxonomy. If not committed to taxonomy compliant investments should fill in 0%. Either way, the answer should contain a percentage value. / Jos edistää ympäristöominaisuuksia tulee kertoa missä määrin kestävät sijoitukset ovat EU taksonomian mukaisia. Jos ei ole sitoutunut taksonianmukaisiin sijoituksiin tulee täyttää 0%. Eli ei saa poistaa kyseistä kysymystä vaikka ei olisi taksonomian mukaisia sijoituksia jos edistää ympäristöominaisuuksia. ["To what minimum extent are sustainable investments with an environmental objective aligned with the EU Taxonomy?"]', 
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
        comment = "Information not required, no sustainable investments with a social objective."

    # Save validation result
    condition = {
        "name": "Minimum share of sustainable investments with social objective disclosed?",
        "description": 'If the product invests in sustainable investments with a social objective, it should be disclosed what their share is. / Jos tuote sijoittaa kestäviin sijoituksiin joilla on yhteiskunnallinen tavoitteite tulee kertoa mikä niiden osuus on. ["What is the minimum share of socially sustainable investments?"]', 
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
        "description": 'If the product invests in other investments "other" should be given in the question details. / Jos tuote sijoittaa muihin sijoituksiin ”other” tulee antaa kysymyksen tiedot. ["What investments are included under “#2 Other”, what is their purpose and are there any minimum environmental or social safeguards?"]', 
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
        "description": 'The description should indicate whether the fund promotes E and S or both. / Kuvauksesta tulee käydä ilmi edistääkö rahasto E ja S vai jompaakumpaa. ["What environmental and/or social characteristics are promoted by this financial product? "]', 
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
        except Exception as e:
            value = False
            comment = "Not able to judge the adequancy of the described sustainability indicators. Exception: " + str(e)

    # Save validation result
    condition = {
        "name": "Consistent sustainability indicators?",
        "description": 'The indicators should be consistent with the previous question. / Indikaattorit tulevat olla yhteneväisiä edellisen kysymyksen kanssa. ["What sustainability indicators are used to measure the attainment of each of the environmental or social characteristics promoted by this financial product?"]', 
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

    if sm_minimum_sustainable_investment == "selected":

        value = False
        comment = "Not able to validate alignment with the objectives of SFDR Article 2.17"

        # 5 a. the objective of the sustainable investment should be described, which should be in line with the objectives of SFDR Article 2.17
        if type(a_sustainable_investment_objectives) == str:

            system = """You are provided with a text regarding the objectives of sustainable investments of a financial product.
            Please carefully read the text and and check if it is in line with the objectives of the SFDR Article 2.17. Not all objectives of SFDR Article 2.17 have to be promoted by the product but it must be at least one.
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
        "description": 'If the table on the first page indicates that the fund makes sustainable investments, the objective of the sustainable investment should be described, which should be in line with the objectives of SFDR Article 2.17. / Jos ensimmäisen sivun taulukon mukaan rahasto tekee kestäviä sijoituksia, tulee kuvata kestävän sijoituksen tavoite, jonka tulee vastata SFDR artikla 2.17 tavoitteita. ["What are the objectives of the sustainable investments that the financial product partially intends to make and how does the sustainable investment contribute to such objectives? "]', 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)

    #### 5b. If the table on the first page indicates that the fund makes sustainable investments and the fund includes taxonomy investments, the taxonomy objective to be promoted should be stated.

    if sm_minimum_sustainable_investment == "selected":
        if type(a_sustainable_investment_objectives) == str:

            if sm_minimum_sustainable_investment_env_taxonomy == "selected":

                system = """You are provided with a text regarding the objectives of sustainable investments of a financial product.
                Please carefully read the text and and check if the taxonomy objective to be promoted is stated. The text should refer to at least one of the following taxonomy objectives:
                a) climate change mitigation; (b) climate change adaptation; (c) the sustainable use and protection of water and marine resources; (d) the transition to a circular economy; (e) pollution prevention and control; (f) the protection and restoration of biodiversity and ecosystems.
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
                comment = "Answer not required. The funds does not include taxonomy investments."

        else:
            value = False
            comment = "Sustainable investment object but no answer for objectives provided."

    else:
        value = True
        comment = "Answer not required. No sustainable investment objective."

    # Save validation result
    condition = {
        "name": "Promoted taxonomy objective stated?",
        "description": 'If the table on the first page indicates that the fund makes sustainable investments and the fund includes taxonomy investments, the taxonomy objective to be promoted should be stated. / Lisäksi jos rahasto sisältää taulukon mukaan taksonomian mukaisia sijoituksia tulee kertoa mitä taksonmian mukaista tavoitetta edistää. ["What are the objectives of the sustainable investments that the financial product partially intends to make and how does the sustainable investment contribute to such objectives? "]', 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)

    #### 6. If the fund makes sustainable investments (i.e. ticked and % indicated in the table on the first page), the annex I indicators that are monitored in order not to cause significant harm must be listed (it is not enough to mention but to report the annex I indicators).
    if sm_minimum_sustainable_investment == "selected":
        relevant_text = a_no_significant_harm + " " + a_accounting_indicators_on_sustainability_factors + " " + a_principal_adverse_impacts_explaination
        
        system = """You are provided with a text that should reference to 14 indicators that are monitored in order not to cause significant harm with a financial investment. 

        The 14 indicators are: 1.) Greenhous gas emissions; 2.) Carbon footprint; 3.) Greenhous gas intesity of investee companies; 4.) Exposure to companies active in the fossil fuel sector; 5.) Share of non-renewable energy consumption and production; 6.) Energy consumption intensity per high impact climate sector; 7.) Activities negatively affecting biodiversitysensitive areas; 8.) Emissions to water; 9.) Hazardous waste and radioactive waste ratio; 10.) . Violations of UN Global Compact principles and Organisation for Economic Cooperation and Development (OECD) Guidelines for Multinational Enterprises; 11.) Lack of processes and compliance mechanisms to monitor compliance with UN Global Compact principles and OECD Guidelines for Multinational Enterprises; 12.) Unadjusted gender pay gap; 13.) Board gender diversity; 14.) Exposure to controversial weapons (anti-personnel mines, cluster munitions, chemical weapons and biological weapons). 
        
        Please carefully go through all of these 14 indicators and check if they are mentioned at least once in the provided text. The text may be in Finnish, so make sure you also consider the translations of the indicators above.
         
        Your answer should be structured as: {"indicators_listed": indicators_listed, "comment": comment}, where the value of indicators_listed is "True" if all 14 indicators are listed in the provided text and "False" if not. If each of the 14 indicators is mentioned at least once in the text, the condition is True. It is not a problem if one number is mentioned multiple times, as long as each of the indicators is in the text. That is all you care about. If one indicator is mentioned twice in different contexts, that is not a problem as long as it is mentioned correctly at least once. If there are further indicators in the provided text that do not correspond to any of the 14 indicators, you can ignore that information and "indicators_listed" would still be True.
        
        If indicators_listed is False, you should mention all indicators that have not been listed in the provided text in the comment. Otherwise the comment can be an empty string like "".
        Your answer must not contain anything else."""
        
        response = openai.ChatCompletion.create(
            engine="gpt-4", 
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": relevant_text}
            ]    
        )
        resp = response['choices'][0]['message']['content']

        try:
            resp_dict = json.loads(resp)
            if "true" in str(resp_dict["indicators_listed"]).lower(): 
                value = True
            else:
                value = False
            comment = resp_dict["comment"]
        except:
            value = False
            comment = "Not able to check if answer inline with SFDR objectives."
        
    else:
        value = True
        comment = "Answer not required. No sustainable investments."

    # Save validation result
    condition = {
        "name": "Annex I indicators listed?",
        "description": 'If the fund makes sustainable investments (i.e. ticked and % indicated in the table on the first page), the annex I indicators that are monitored in order not to cause significant harm must be listed (it is not enough to mention but to report the annex I indicators). / Jos rahasto tekee kestäviä sijoituksia (eli ensimmäisen sivun taulukossa valittu ruksi ja ilmoitettu %), tulee luetella ne annex I indikaattorit joita seurataan jotta ei aiheuta merkittävää haittaa ( ei siis riitä että mainitaan vaan että raportoidaan annex I mukaiset indikaattorit). ["How do the sustainable investments that the financial product partially intends to make, not cause significant harm to any environmental or social sustainable investment objective? "]', 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)
    

    #### 15. If the fund makes sustainable investments with an environmental objective, it should explain why it invests in sustainable investments that have an environmental objective but do not comply with the taxonomy
    #  if 5.) is selected, let ChatGPT check if 25.) provides reasonable explaination why it invests in sustainable investments that have an environmental objective but do not comply with the taxonomy -> yes/no/unclear
    if sm_minimum_sustainable_investment == "selected":
    
        system = """You are provided with text regarding the share of sustainable investments in a financial product that are not aligned with the EU Taxonomy. Please carefully read the text and and check if it provides a reasonable explanation why the financial product invests in sustainable investments that have an environmental objective but do not comply with the taxonomy.

        If the fund is committed to making only sustainable investments that comply with the EU taxonomy, this condition does not apply. In that case you can answer that the condition is True.

        Your answer should be structured as: {"reasonable_explanation": reasonable_explanation, "comment": comment}, where the value of reasonable_explanation is either "True" or "False" and comment is a short explanation of why you made this decision.
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
        comment = "Answer not required. No sustainable investments with an environmental objective."

    # Save validation result
    condition = {
        "name": "Non-compliance with taxonomy explained?",
        "description": 'If the fund makes sustainable investments with an environmental objective, it should explain why it invests in sustainable investments that have an environmental objective but do not comply with the taxonomy. /Jos rahasto tekee kestäviä sijoituksia joilla ympäristötavoite tulee kertoa miksi sijoittaa kestäviin sijoituksiin joilla on ympäristötavoite mutta eivät ole taksonomian mukaisia. ["What is the minimum share of sustainable investments with an environmental objective that are not aligned with the EU Taxonomy?"]', 
        "value": value,
        "comment": comment
    }
    conditions.append(condition)

    return conditions
