# Task Tracker Agent

A Mac desktop app prototype for turning plain English task notes into structured,
prioritized tasks with AI-generated next steps.

## Step 1: Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Step 2: Install dependencies

```bash
pip install PySide6 openai python-dotenv
```

## Step 3: Configure your OpenAI API key

```bash
cp .env.example .env
```

Then edit `.env` and replace `your_api_key_here` with your real API key.

## Step 4: Run the app

```bash
python -m task_tracker_agent.app
```

If `OPENAI_API_KEY` is missing, the app still runs with a small local fallback parser
so you can test the UI without making API calls.
