import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["ZAI_API_KEY"],
    base_url="https://api.z.ai/api/paas/v4/"
)

news = """
Jean-Philippe Mateta is challenging the validity of the final 10 months
on his Crystal Palace contract.
"""

prompt = f"""
تو یک ویراستار حرفه‌ای اخبار فوتبال برای یک کانال خبری فارسی هستی.

متن خبر:
{news}

خبر را به فارسی روان و طبیعی بازنویسی کن.

قوانین:
- فقط اطلاعات موجود در متن را بیان کن.
- هیچ اطلاعاتی از خودت اضافه نکن.
- متن کوتاه و خبری باشد.
- نام بازیکنان و باشگاه‌ها را درست بنویس.
- ابتدا یک تیتر کوتاه و جذاب بنویس.
- سپس یک پاراگراف خبری 2 تا 4 جمله‌ای بنویس.
- از ایموجی استفاده نکن.
- هیچ توضیحی درباره فرایند بازنویسی نده.

فرمت خروجی:

تیتر

متن خبر
"""

response = client.chat.completions.create(
    model="glm-4.7-flash",
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ]
)

print("========== نتیجه بازنویسی ==========")
print(response.choices[0].message.content)
print("====================================")
