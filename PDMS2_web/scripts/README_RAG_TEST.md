# RAG Testing & Evaluation Guide

This directory contains the `rag_tester.py` script, designed to evaluate the performance of the PDMS-2 RAG Advisor.

## Features
- **Mock Data Support**: Test the advisor without needing a live MySQL connection or real child data.
- **Retrieval Inspection**: Logs which chunks from the `RAG` directory were retrieved for each scenario.
- **Heuristic Evaluation**: Automatically scores the generated advice based on:
    - Markdown formatting (headers, lists).
    - Relevance (mentioning the specific weak tasks).
    - Completeness (providing 3-4 activities).
- **Markdown Reporting**: Generates a detailed report with timestamps for each test run.

## Prerequisites
Ensure the following packages are installed in your Python environment:
```bash
pip install langchain langchain-openai langchain-huggingface chromadb chromadb chromadb pypdf python-dotenv
```

## Configuration
Make sure your `PDMS2_web/.env` file contains the following AI settings:
```env
AI_API_KEY=your_openai_api_key
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-3.5-turbo
```

## How to Run
From the `PDMS2_web` directory:
```powershell
python scripts/rag_tester.py
```

## Customizing Tests
You can add more test cases in the `run_tests()` function within `scripts/rag_tester.py`. Each case defines a `uid` and a list of task scores.

## Output
- **Console**: Live progress and summary scores.
- **Report**: A file named `scripts/rag_test_report_YYYYMMDD_HHMMSS.md` will be created with detailed retrieval and generation results.
