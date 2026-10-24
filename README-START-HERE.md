# TraceLens bundle
Contains four independent directories: tracelens-sdk, tracelens-backend, rag-project-1, rag-project-2.

1. Run `docker compose up -d mongodb` from the extracted root.
2. Start backend from `tracelens-backend` using its README-equivalent steps: create venv, install requirements, copy `.env.example` to `.env`, then `uvicorn app.main:app --reload`.
3. In each RAG project, create a venv, install its requirements, then `pip install -e ..\\tracelens-sdk` and run `python main.py`.
