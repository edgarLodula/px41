import os
import requests
import time

def gerar_roteiro(texto, disciplina, token, modelo="llama-3.3-70b-versatile"):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": modelo,
        "max_tokens": 2000,
        "temperature": 0.7,
        "messages": [
            {
                "role": "system",
                "content": f"Você é um professor especialista em {disciplina}"
            },
            {
                "role": "user",
                "content": f"""
Explique como uma aula falada:

{texto[:5000]}
"""
            }
        ]
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload
    )

    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]