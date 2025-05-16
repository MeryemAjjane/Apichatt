    
import re
import json
#Framework rapide pour construire les api web avec python
from fastapi import FastAPI, File, UploadFile
#bibliotheque pour extraire du text du pdf
import pdfplumber
#Client HTTP asynchrone pour effectuer des requêtes API pour interagir avec OpenRouter
import httpx

app = FastAPI()

OPENROUTER_API_KEY = "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"
#URL de l'API OpenRouter pour l'interaction avec le modèle LLM
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/completions"
#Cette fonction extrait un objet JSON valide d'une chaîne de caractères.
#Cherche la première { (début du JSON).
#Utilise une variable depth pour suivre l'équilibre des { et }.
#Lorsqu'elle atteint un équilibre (depth == 0), elle extrait le JSON.
#Tente de convertir ce texte en JSON avec json.loads().
#Si aucune structure JSON n'est trouvée, elle retourne None
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
#Méthode POST : Reçoit un fichier PDF envoyé par l'utilisateur
@app.post("/extract-backlogs/")
async def extract_backlogs(file: UploadFile = File(...)):
    try:
        with pdfplumber.open(file.file) as pdf:
            text = "".join(page.extract_text() or "" for page in pdf.pages)
        text = text[:2000]  # Limiter à 2000 caractères pour meilleure compréhension

        # Forcer l'extraction du titre (1ère ligne)
        lines = text.splitlines()
        title = lines[0].strip() if lines else "Titre du projet"
        #Crée un prompt clair et structuré pour guider l'IA sur ce qu'elle doit générer.
        # Demande à l'IA de :
        # Identifier le titre du projet.
        # Générer les backlogs sous forme de JSON.


        prompt = f"""
        Voici un texte extrait d'un cahier de charges : {text}.
        Ton objectif est de générer des backlogs clairs pour ce projet, en identifiant les tâches, objectifs et fonctionnalités mentionnés dans le texte sous forme de liste JSON, avec chaque backlog contenant 'title' et 'description'.
        Un backlog est une tâche spécifique qui doit être réalisée dans le cadre du projet.
        Voici comment tu dois procéder :
        1. Lis attentivement le texte et identifie les phrases décrivant des actions, des fonctionnalités ou des objectifs.
        2. Transforme chacune de ces phrases en un backlog avec un titre clair et une description.
        3. Le titre doit résumer la tâche (par exemple : "Automatisation des tâches"), et la description doit expliquer ce qui doit être fait.
        4. Ne copie pas simplement les titres de section comme "1. Cadre du projet". Analyse le contenu et identifie les tâches.
        5. Identifie le titre du projet et affiche-le clairement dans la réponse JSON.

        Répond uniquement avec un JSON valide, comme ceci :
        {{
            "title": "Titre du projet",
            "backlogs": [
                {{"title": "Backlog 1", "description": "Description 1"}},
                {{"title": "Backlog 2", "description": "Description 2"}}
            ]
        }}
        """

        #Envoi de la requete a l'api openrouter
        # Utilise httpx (client HTTP asynchrone) pour interagir avec OpenRouter.
        # Utilise le modèle meta-llama/llama-3.3-8b-instruct.
        # Contrôle les paramètres de génération :
        # max_tokens : Limite de 800 tokens pour la réponse.
        # temperature : Contrôle la créativité (0.5 = modérée).
            
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "meta-llama/llama-3.3-8b-instruct:free",
                    "prompt": prompt,
                    "max_tokens": 800,
                    "temperature": 0.5
                }
            )

        if response.status_code != 200:
            return {"error": f"Erreur OpenRouter: {response.text}"}
        # Extrait le texte généré par l'IA.
        result = response.json()
        # Nettoie ce texte pour enlever les espaces inutiles.
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
        # Si l'IA ne fournit pas de backlogs, 
        # il les crée automatiquement en cherchant les mots-clés ("objectif", "but", "tâche") dans le texte.
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


 