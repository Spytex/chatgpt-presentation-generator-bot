import config

import openai

openai.api_key = config.openai_api_key

OPENAI_COMPLETION_OPTIONS = {
    "temperature": 0.75,
    "max_tokens": 3072,
    "top_p": 1,
    "frequency_penalty": 0,
    "presence_penalty": 0,
}


async def process_prompt(message):
    answer = None
    while answer is None:
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": message}
                ],
                **OPENAI_COMPLETION_OPTIONS
            )
            answer = response['choices'][0]['message']['content']
            n_used_tokens = response.usage.total_tokens
        except openai.error.InvalidRequestError as e:  # too many tokens
            raise ValueError("Too many tokens to make completion") from e
        except openai.error.RateLimitError as e:
            raise OverflowError("That model is currently overloaded with other requests.") from e
        except openai.error.APIError as e:
            raise RuntimeError("HTTP code 502 from API") from e
    return answer, n_used_tokens
