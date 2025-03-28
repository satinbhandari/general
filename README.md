9If you want to override both the default headers and model in your derived class while extending ChatOpenAI, you can modify the headers and model attributes inside the subclass constructor.


---

✅ Solution:

from langchain_openai import ChatOpenAI

class CustomChatOpenAI(ChatOpenAI):
    def __init__(self, model_name="gpt-4-turbo", **kwargs):
        super().__init__(model_name=model_name, **kwargs)  # Pass updated model to parent
        self.headers = {  # Override default headers
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Custom-Header": "MyValue"  # Example custom header
        }

# Usage
chat = CustomChatOpenAI(api_key="your_api_key")
print(chat.model_name)  # Output: gpt-4-turbo
print(chat.headers)     # Output: Custom headers dictionary


---

🔹 How It Works

1. Extends ChatOpenAI → Inherits all functionality.


2. Overrides Default Model → The model_name is set to "gpt-4-turbo" by default but can be overridden.


3. Modifies Headers → Overrides self.headers with custom values.


4. Passes Arguments Properly → Uses super().__init__(model_name=model_name, **kwargs) to initialize ChatOpenAI correctly.




---

🔍 Key Benefits

✔️ Default model (gpt-4-turbo) is predefined but can be changed.
✔️ Default headers are customized with additional values.
✔️ The class remains flexible and supports extra arguments via **kwargs.

Would you like to further customize behavior (e.g., dynamic model selection, extra logging)?






To check if a word exists in another string as an exact match (without being part of another word), you can use regular expressions (re module) in Python.


---

Solution: Use re.search() with Word Boundaries (\b)

The \b ensures that SATIN is treated as a whole word, not part of another word like NOSATIN or SATINIZED.

import re

def contains_exact_word(text, word):
    pattern = rf"\b{re.escape(word)}\b"  # \b ensures exact word match
    return bool(re.search(pattern, text))

# Examples
print(contains_exact_word("This is a SATIN fabric.", "SATIN"))    # ✅ True
print(contains_exact_word("This is NOSATIN fabric.", "SATIN"))    # ❌ False
print(contains_exact_word("This is SATINIZED fabric.", "SATIN"))  # ❌ False
print(contains_exact_word("SATIN is great.", "SATIN"))            # ✅ True


---

Explanation:

\b → Word boundary (ensures SATIN is a separate word).

re.escape(word) → Escapes special characters if any.

re.search() → Checks if the pattern exists in the text.


✅ This method ensures that only exact whole-word matches are found.

Would you like this customized further for specific cases?

