    
import re
import json
from fastapi import FastAPI, File, UploadFile
import pdfplumber
import httpx

app = FastAPI()

OPENROUTER_API_KEY = "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"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/completions"

def extract_json(text):
    start = text.find('{')
    if start == -1:
        return None

    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                json_str = text[start:i+1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    return None
    return None

@app.post("/extract-backlogs/")
async def extract_backlogs(file: UploadFile = File(...)):
    try:
        with pdfplumber.open(file.file) as pdf:
            text = "".join(page.extract_text() or "" for page in pdf.pages)
        text = text[:2000]  # Limiter à 2000 caractères pour meilleure compréhension

        # Forcer l'extraction du titre (1ère ligne)
        lines = text.splitlines()
        title = lines[0].strip() if lines else "Titre du projet"
        prompt = f"""
        Voici un texte extrait d'un cahier de charges : {text}. 
        Analyse ce texte et :
        1. Génère les backlogs sous forme de liste JSON, avec chaque backlog contenant 'title' et 'description'.
        2. Identifie le titre du projet et affiche-le clairement dans la réponse JSON.
        Répond uniquement avec un JSON valide, comme ceci :
        {{
            "title": "Titre du projet",
            "backlogs": [
                {{"title": "Backlog 1", "description": "Description 1"}},
                {{"title": "Backlog 2", "description": "Description 2"}}
            ]
        }}
        """


        async with httpx.AsyncClient() as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "qwen/qwen3-0.6b-04-28:free",
                    "prompt": prompt,
                    "max_tokens": 800,
                    "temperature": 0.5
                }
            )

        if response.status_code != 200:
            return {"error": f"Erreur OpenRouter: {response.text}"}

        result = response.json()
        generated_text = result.get("choices", [{}])[0].get("text", "").strip()

        print("Texte généré :", repr(generated_text))

        # Nettoyer la réponse pour enlever tout avant le premier {
        index_first_brace = generated_text.find('{')
        if index_first_brace != -1:
            cleaned_text = generated_text[index_first_brace:]
        else:
            cleaned_text = generated_text

        response_json = extract_json(cleaned_text)

        if response_json is None:
            return {
                "error": "Le modèle n'a pas généré un JSON valide.",
                "generated_text": generated_text
            }

        # Si le JSON n'a pas de backlogs, extraire les backlogs manuellement
        if not response_json.get("backlogs"):
            response_json["title"] = title
            response_json["backlogs"] = []
            for line in lines:
                if "objectif" in line.lower() or "but" in line.lower() or "tâche" in line.lower():
                    response_json["backlogs"].append({
                        "title": line.strip(),
                        "description": "Description détectée automatiquement."
                    })

        return response_json

    except Exception as e:
        return {"error": str(e)}
