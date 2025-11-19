# Product Importer

A FastAPI-based application for importing and managing products from CSV files with async processing, webhook support, and real-time progress tracking.

## Features

- **CSV Import**: Upload and process large CSV files (500k+ records) asynchronously
- **Product Management**: Full CRUD operations for products with filtering and pagination
- **Webhook System**: Configure webhooks to receive notifications on product events
- **Real-time Progress**: Track CSV import progress in real-time
- **Case-insensitive SKU**: Unique product SKUs with case-insensitive matching

## Tech Stack

- **Framework**: FastAPI (async support)
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Task Queue**: Celery with Redis
- **Migrations**: Alembic
- **Language**: Python 3.10+

## Project Structure

```
fume/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── database.py          # Database configuration and session management
│   ├── models/              # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── product.py       # Product model
│   │   └── webhook.py       # Webhook model
│   ├── api/                 # API endpoints
│   ├── tasks/               # Celery task definitions
│   │   ├── __init__.py
│   │   └── celery_app.py    # Celery configuration
│   └── utils/               # Utility functions (CSV parsing, validation)
├── alembic/                 # Database migrations
├── static/                  # Frontend assets
├── templates/               # HTML templates
├── requirements.txt         # Python dependencies
├── alembic.ini              # Alembic configuration
└── README.md
```

## Setup Instructions

### Prerequisites

- Python 3.10 or higher
- PostgreSQL 12 or higher
- Redis (for Celery task queue)

### Installation

1. **Clone the repository** (if applicable):
   ```bash
   git clone <repository-url>
   cd fume
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Create a `.env` file in the project root (copy from `.env.example` if available):
   ```env
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/product_importer
   DATABASE_URL_SYNC=postgresql://user:password@localhost:5432/product_importer
   REDIS_URL=redis://localhost:6379/0
   CELERY_BROKER_URL=redis://localhost:6379/0
   CELERY_RESULT_BACKEND=redis://localhost:6379/0
   SECRET_KEY=your-secret-key-here
   DEBUG=True
   ENVIRONMENT=development
   ```

5. **Set up PostgreSQL database**:
   ```bash
   createdb product_importer
   # Or using psql:
   # psql -U postgres
   # CREATE DATABASE product_importer;
   ```

6. **Run database migrations**:
   ```bash
   alembic upgrade head
   ```

7. **Start Redis** (if not already running):
   ```bash
   redis-server
   # Or using Docker:
   # docker run -d -p 6379:6379 redis
   ```

### Running the Application

1. **Start the FastAPI server**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Start Celery worker** (in a separate terminal):
   ```bash
   celery -A app.tasks.celery_app worker --loglevel=info
   ```

3. **Access the API**:
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

### Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:
```bash
alembic upgrade head
```

Rollback migration:
```bash
alembic downgrade -1
```

## Development

### Running Tests

(To be implemented)

### Code Style

(To be configured)

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Async PostgreSQL connection URL | `postgresql+asyncpg://user:password@localhost:5432/product_importer` |
| `DATABASE_URL_SYNC` | Sync PostgreSQL connection URL (for Alembic) | `postgresql://user:password@localhost:5432/product_importer` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery result backend URL | `redis://localhost:6379/0` |
| `SECRET_KEY` | Secret key for application | (required) |
| `DEBUG` | Debug mode | `True` |
| `ENVIRONMENT` | Environment name | `development` |

## API Endpoints

(To be documented in Step 2)

## License

(To be specified)
