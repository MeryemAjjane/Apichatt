# import pdfplumber
# from fastapi import FastAPI, UploadFile, File
# import requests
# import json

# app = FastAPI()

# OPENROUTER_API_KEY = "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"

# @app.post("/extract-backlogs/")
# async def extract_backlogs(file: UploadFile = File(...)):
#     with pdfplumber.open(file.file) as pdf:
#         text = ""
#         for page in pdf.pages[:5]:  # Limiter à 10 pages maximum pour éviter l'excès de texte
#             text += page.extract_text() or ""

#     # Limiter le texte à environ 10 000 caractères (environ 2000 tokens)
#     if len(text) > 10000:
#         text = text[:10000]  # Limite de 10 000 caractères

#     # Envoyer le texte extrait à OpenRouter
#     response = requests.post(
#         url="https://openrouter.ai/api/v1/chat/completions",
#         headers={
#             "Authorization": f"Bearer {OPENROUTER_API_KEY}",
#             "Content-Type": "application/json"
#         },
#         data=json.dumps({
#             "model": "shisa-ai/shisa-v2-llama3.3-70b:free",
#             "messages": [
#                 {
#                     "role": "user",
#                     "content": text
#                 }
#             ],
#         })
#     )

#     # Vérifier la réponse
#     if response.status_code == 200:
#         return response.json()
#     else:
#         return {"error": "Échec de la connexion à OpenRouter", "details": response.text}

from fastapi import FastAPI, File, UploadFile
import pdfplumber
import json
import httpx  # Pour faire des requêtes HTTP asynchrones

app = FastAPI()

OPENROUTER_API_KEY = "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"  # Remplace par ta clé OpenRouter
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/completions"

@app.post("/extract-backlogs/")
async def extract_backlogs(file: UploadFile = File(...)):
    try:
        # Lire le fichier PDF
        with pdfplumber.open(file.file) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text()

        # Limiter le texte pour éviter les problèmes de longueur
        text = text[:4000]  # Limite à 4000 caractères (modifiable)
        
        # Le prompt pour OpenRouter
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

        # Envoyer le prompt à OpenRouter
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "shisa-ai/shisa-v2-llama3.3-70b:free",  # Utilise le modèle de ton choix
                    "prompt": prompt,
                    "max_tokens": 800,
                    "temperature": 0.7
                }
            )

        # Afficher la réponse pour le débogage
        print("Réponse OpenRouter:", response.text)

        # Vérifier la réponse de OpenRouter
        if response.status_code == 200:
            result = response.json()
            generated_text = result.get("choices")[0].get("text", "").strip()
            return json.loads(generated_text)  # Retourner directement la réponse JSON générée par OpenRouter

        else:
            return {"error": f"Erreur OpenRouter: {response.text}"}

    except json.JSONDecodeError:
        return {"error": "La réponse de OpenRouter n'est pas un JSON valide."}
    except Exception as e:
        return {"error": str(e)}
