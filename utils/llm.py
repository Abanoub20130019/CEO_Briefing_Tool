import google.generativeai as genai
from openai import OpenAI, AzureOpenAI
import base64
import json

def get_image_base64(file_bytes, mime_type):
    """Convert image bytes to base64 string for OpenAI."""
    base64_image = base64.b64encode(file_bytes).decode('utf-8')
    return f"data:{mime_type};base64,{base64_image}"

def extract_metrics_with_gemini(file_bytes, mime_type, api_key, model_name="gemini-1.5-flash"):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    prompt = """
    Analyze this image/document. Identify the table with Brand performance. 
    Extract the 'Sales vs BP %' and 'Margin vs BP %' for these specific brands: 
    [SBX, H&M, PM, VS, BBW, S.SHACK, AEO, R.CANES, FL, CT, CHIP, ULTA]. 
    Return the result as a strict JSON object.
    Format: {"SBX": {"sales": "-6%", "margin": "-4%"}, ...}
    """
    
    # Gemini accepts bytes directly for some mime types via inline data or blob, 
    # but the python SDK `generate_content` can take a dict `{'mime_type': ..., 'data': ...}`
    image_part = {
        "mime_type": mime_type,
        "data": file_bytes
    }
    
    response = model.generate_content([prompt, image_part], generation_config={"response_mime_type": "application/json"})
    return response.text

def extract_metrics_with_openai(file_bytes, mime_type, api_key, model_name="gpt-4o"):
    client = OpenAI(api_key=api_key)
    base64_url = get_image_base64(file_bytes, mime_type)
    
    prompt = """
    Analyze this image/document. Identify the table with Brand performance. 
    Extract the 'Sales vs BP %' and 'Margin vs BP %' for these specific brands: 
    [SBX, H&M, PM, VS, BBW, S.SHACK, AEO, R.CANES, FL, CT, CHIP, ULTA]. 
    Return the result as a strict JSON object.
    Format: {"SBX": {"sales": "-6%", "margin": "-4%"}, ...}
    """

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": base64_url}},
                ],
            }
        ],
        response_format={ "type": "json_object" }
    )
    return response.choices[0].message.content

def extract_metrics_with_azure(file_bytes, mime_type, api_key, azure_endpoint, api_version, deployment_name):
    client = AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=azure_endpoint
    )
    
    base64_url = get_image_base64(file_bytes, mime_type)
    
    prompt = """
    Analyze this image/document. Identify the table with Brand performance. 
    Extract the 'Sales vs BP %' and 'Margin vs BP %' for these specific brands: 
    [SBX, H&M, PM, VS, BBW, S.SHACK, AEO, R.CANES, FL, CT, CHIP, ULTA]. 
    Return the result as a strict JSON object.
    Format: {"SBX": {"sales": "-6%", "margin": "-4%"}, ...}
    """

    response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": base64_url}},
                ],
            }
        ],
        response_format={ "type": "json_object" }
    )
    return response.choices[0].message.content

def extract_metrics_from_file(file_bytes, mime_type, api_key, provider, model_name=None, azure_config=None):
    if provider == "Google Gemini":
        model = model_name if model_name else "gemini-1.5-flash"
        return extract_metrics_with_gemini(file_bytes, mime_type, api_key, model)
    elif provider == "OpenAI":
        model = model_name if model_name else "gpt-4o"
        return extract_metrics_with_openai(file_bytes, mime_type, api_key, model)
    elif provider == "Azure OpenAI":
        if not azure_config:
            raise ValueError("Azure config missing")
        return extract_metrics_with_azure(
            file_bytes, 
            mime_type, 
            api_key, 
            azure_config['endpoint'], 
            azure_config['version'], 
            azure_config['deployment']
        )
    else:
        raise ValueError("Invalid Provider")

def generate_email_with_gemini(system_instruction, combined_prompt, api_key, model_name="gemini-1.5-flash"):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
    response = model.generate_content(combined_prompt)
    return response.text

def generate_email_with_openai(system_instruction, combined_prompt, api_key, model_name="gpt-4o"):
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": combined_prompt}
        ]
    )
    return response.choices[0].message.content

def generate_email_with_azure(system_instruction, combined_prompt, api_key, azure_endpoint, api_version, deployment_name):
    client = AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=azure_endpoint
    )
    response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": combined_prompt}
        ]
    )
    return response.choices[0].message.content

def generate_email(notes, metrics_json, report_text, sample_text, api_key, provider, model_name=None, system_instruction_override=None, azure_config=None):
    
    default_system_instruction = "You are an Executive Assistant."
    system_instruction = system_instruction_override if system_instruction_override else default_system_instruction
    
    prompt = f"""
    Write a weekly brief based on the following context:

    1. THE DATA (Use these numbers exactly): {metrics_json}

    2. THE CEO NOTES (Use this for the intro): {notes}

    3. THE MARKET REPORT (Extract 'MENA Highlights' bullets verbatim from here): {report_text}

    4. FORMATTING RULE (CRITICAL): You must strictly follow the format, tone, headers, and layout of the SAMPLE TEXT below. Look at how the tables are formatted (plain text, no markdown bolding). Look at how the sections are ordered.

    SAMPLE TEXT: {sample_text}
    """
    
    if provider == "Google Gemini":
        model = model_name if model_name else "gemini-1.5-flash"
        return generate_email_with_gemini(system_instruction, prompt, api_key, model)
    elif provider == "OpenAI":
        model = model_name if model_name else "gpt-4o"
        return generate_email_with_openai(system_instruction, prompt, api_key, model)
    elif provider == "Azure OpenAI":
        if not azure_config:
            raise ValueError("Azure config missing")
        return generate_email_with_azure(
            system_instruction, 
            prompt, 
            api_key, 
            azure_config['endpoint'], 
            azure_config['version'], 
            azure_config['deployment']
        )
    else:
        raise ValueError("Invalid Provider")
