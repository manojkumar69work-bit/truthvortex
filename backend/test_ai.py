import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NVAPI_KEY")
model = os.getenv("AI_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5")
print("API key loaded:", bool(api_key))
print("Model:", model)

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=api_key,
)

response = client.chat.completions.create(
    model=model,
    messages=[
        {
            "role": "system",
            "content": (
                "/no_think\n"
                "You are a Telugu news editor. Output only Telugu script. "
                "No English letters."
            ),
        },
        {
            "role": "user",
            "content": (
                "Write one short Telugu headline and exactly 5 Telugu summary lines "
                "for this news. Format as HEADLINE: then SUMMARY:\n\n"
                "India announced a new trade policy focused on manufacturing and exports."
            ),
        },
    ],
    temperature=0,
    top_p=0.95,
    max_tokens=200,
    stream=False,
)

print("RAW MESSAGE:", response.choices[0].message)
print("CONTENT:", response.choices[0].message.content)
