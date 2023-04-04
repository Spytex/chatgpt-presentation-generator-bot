import config

import openai
openai.api_key = config.openai_api_key

CHAT_MODES = config.chat_modes

OPENAI_COMPLETION_OPTIONS = {
    "temperature": 0.7,
    "max_tokens": 1000,
    "top_p": 1,
    "frequency_penalty": 0,
    "presence_penalty": 0
}


class ChatGPT:
    def __init__(self, use_chatgpt_api=True):
        self.use_chatgpt_api = use_chatgpt_api
    
    async def send_message(self, messages):
        answer = None
        while answer is None:
            try:
                if self.use_chatgpt_api:
                    r = await openai.ChatCompletion.acreate(
                        model="gpt-3.5-turbo",
                        messages=messages,
                        **OPENAI_COMPLETION_OPTIONS
                    )
                    answer = r.choices[0].message["content"]

                answer = self._postprocess_answer(answer)
                n_used_tokens = r.usage.total_tokens
                
            except openai.error.InvalidRequestError as e:  # too many tokens
                raise ValueError("Too many tokens") from e

        return answer, n_used_tokens

    def _generate_prompt_message_for_presentation(self, topic: str, slides: int):     ###   slides???
        message = f"Write a presentation on {slides} slides on the topic: {topic}, according to the formula for presentations: \nSlide: ...\nTitle: ...\nImage: ...\nText: ..."
               # Send message after generation prompt
        return message

    def _postprocess_answer(self, answer):
        answer = answer.strip()
        return answer
