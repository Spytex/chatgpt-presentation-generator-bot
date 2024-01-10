# AI Presentation Generator

This project is a bot that generates presentations and abstracts using AI. It uses OpenAI API or your processed messages to generate content and various presentation templates to create visually appealing slides.

## Setup

1. Get your [OpenAI API](https://openai.com/api/) key

2. Get your Telegram bot token from [@BotFather](https://t.me/BotFather)

3. Edit `config/config.example.yml` to set your tokens and run 2 commands below (*if you're advanced user, you can also edit* `config/config.example.env`):
    ```bash
    mv config/config.example.yml config/config.yml
    mv config/config.example.env config/config.env
    ```

4. 🔥 And now **run**:
    ```bash
    docker-compose --env-file config/config.env up --build
    ```

## References

1. [*Build ChatGPT from GPT-3*](https://learnprompting.org/docs/applied_prompting/build_chatgpt)
2. [*ChatGPT Telegram Bot*](https://github.com/father-bot/chatgpt_telegram_bot)
