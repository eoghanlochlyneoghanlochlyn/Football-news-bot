import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["ZAI_API_KEY"],
    base_url="https://api.z.ai/api/paas/v4/"
)

response = client.chat.completions.create(
    model="glm-4.7-flash",
    messages=[
        {
            "role": "user",
            "content": "به فارسی و در یک جمله بگو: فوتبال چیست؟"
        }
    ]
)

print("پاسخ Z.AI:")
print(response.choices[0].message.content)
