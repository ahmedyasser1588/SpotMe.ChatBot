# SpotMe ChatBot

A FastAPI-based scouting chatbot that answers questions about players using the Groq LLM (llama-3.3-70b-versatile) with function calling and retrieval over player data.

## Overview

This API combines a scouting dataset (`data/players.json`) with the Groq LLM. It parses user questions, retrieves relevant players (including fuzzy name matching), computes talent-score percentiles, and answers in natural language. A tool-calling loop lets the model fetch structured data. It also exposes a player search endpoint and a chat endpoint with per-session history.

## Features

- Player profile display (basic info, AI score, stats)
- Player search with fuzzy name matching
- Talent-score percentile ranking
- `/api/chat` endpoint using Groq function calling with session memory

## Tech Stack

- Python
- FastAPI
- Groq (llama-3.3-70b-versatile)
- Pydantic

## Project Structure

```text
SpotMe.ChatBot/
├── main.py            # API + retrieval + Groq tool calling
├── chat.ipynb         # Jupyter notebook experiment
├── data/players.json  # Player dataset
├── requirements.txt
└── .env.example
```

## Installation

```bash
git clone https://github.com/ahmedyasser1588/SpotMe.ChatBot.git
cd SpotMe.ChatBot
pip install -r requirements.txt
cp .env.example .env   # add GROQ_API_KEY
```

## Usage

```bash
uvicorn main:app --reload
```

## Project Status

Experimental — a chatbot prototype over scouting data.

## Future Improvements

- Move retrieval into a dedicated module
- Add tests for the parsing/percentile logic
- Add authentication and rate limiting
