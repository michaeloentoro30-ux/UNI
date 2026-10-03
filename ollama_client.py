import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "gemma3:4b"


class OllamaError(Exception):
    pass


def ask_ai(message, history=None):
    """
    Normal standalone chatbot.
    Does NOT use the UniScout database.
    """

    if history is None:
        history = []

    messages = [
        {
            "role": "system",
            "content": """You are UniScout AI.

You are a friendly, helpful general-purpose AI assistant.

You can talk about:
- universities
- education
- programming
- computers
- technology
- school subjects
- careers
- applications
- everyday questions
- general knowledge

You are NOT restricted to the UniScout university database.

Answer naturally like a normal chatbot.

You can speak English or Indonesian depending on the user's language.

Do not say:
"That information is not available in UniScout's database."

If you don't know something, simply say that you are not sure.

Keep answers reasonably concise unless the user asks for a detailed explanation.
"""
        }
    ]

    # Add previous conversation
    for item in history[-20:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if role in ("user", "assistant") and content:
            messages.append({
                "role": role,
                "content": str(content)
            })

    # Current message
    messages.append({
        "role": "user",
        "content": message
    })

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.7
                }
            },
            timeout=180
        )

        response.raise_for_status()

        data = response.json()

        if "message" not in data:
            raise OllamaError("Ollama returned an invalid response.")

        answer = data["message"].get("content", "").strip()

        if not answer:
            raise OllamaError("Ollama returned an empty response.")

        return answer

    except requests.exceptions.ConnectionError:
        raise OllamaError(
            "Cannot connect to Ollama. Make sure Ollama is running."
        )

    except requests.exceptions.Timeout:
        raise OllamaError(
            "Gemma took too long to respond. Please try again."
        )

    except requests.exceptions.HTTPError as e:
        raise OllamaError(
            f"Ollama HTTP error: {e}"
        )

    except Exception as e:
        raise OllamaError(
            f"Ollama error: {e}"
        )