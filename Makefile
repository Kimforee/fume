.PHONY: help install migrate upgrade run worker test

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make migrate     - Create a new migration"
	@echo "  make upgrade     - Apply database migrations"
	@echo "  make run         - Run the FastAPI server"
	@echo "  make worker      - Run Celery worker"
	@echo "  make test        - Run tests (when implemented)"

install:
	pip install -r requirements.txt

migrate:
	@read -p "Enter migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

upgrade:
	alembic upgrade head

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	celery -A app.tasks.celery_app worker --loglevel=info

test:
	@echo "Tests not yet implemented"

