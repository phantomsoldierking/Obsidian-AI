from __future__ import annotations

import logging

from transformers import pipeline

logger = logging.getLogger(__name__)


class LocalLLMService:
    def __init__(self, model_name: str, max_new_tokens: int):
        logger.info("Loading local LLM: %s", model_name)
        self.generator = pipeline("text-generation", model=model_name)
        self.max_new_tokens = max_new_tokens

    def generate(self, prompt: str) -> str:
        out = self.generator(
            prompt,
            max_new_tokens=self.max_new_tokens,
            do_sample=True,
            top_p=0.9,
            temperature=0.3,
            num_return_sequences=1,
            pad_token_id=self.generator.tokenizer.eos_token_id,
        )
        generated = out[0]["generated_text"]
        if generated.startswith(prompt):
            generated = generated[len(prompt) :]
        return generated.strip()
