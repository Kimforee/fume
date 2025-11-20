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


## Deployment to Google Cloud Platform (Cloud Run)

> **Note:** Detailed deployment instructions with connection strings are kept in `GCP_DEPLOYMENT.md` outside the repository to avoid committing sensitive information. Refer to that file for step-by-step deployment instructions.

### Prerequisites

- Google Cloud Platform account with billing enabled (free tier available)
- GitHub repository with your code
- Google Cloud SDK installed (optional, for manual deployment)

### Step-by-Step Deployment via GitHub Integration

#### 1. Set Up GCP Project

1. **Create a GCP Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Note your Project ID

2. **Enable Required APIs**:
   ```bash
   # Using gcloud CLI (or enable via Console)
   gcloud services enable cloudbuild.googleapis.com
   gcloud services enable run.googleapis.com
   gcloud services enable sqladmin.googleapis.com
   gcloud services enable redis.googleapis.com
   ```

#### 2. Set Up Database (Neon PostgreSQL)

**Using Neon PostgreSQL** (Recommended - Free tier available):
- Create account at [Neon](https://neon.tech)
- Create a new project and database
- Get connection string from Neon dashboard
- Connection string format: `postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require`

**Note:** For async operations, use `postgresql+asyncpg://` prefix. The application automatically handles this conversion.

**Alternative: Cloud SQL** (if preferred):
- Go to Cloud SQL in GCP Console
- Create PostgreSQL instance
- Get connection string from instance details

#### 3. Set Up Redis (Memorystore or Managed Redis)

**Option A: Memorystore (Recommended for GCP)**
```bash
# Create Memorystore Redis instance
gcloud redis instances create product-importer-redis \
  --size=1 \
  --region=us-central1 \
  --redis-version=redis_6_x
```

**Option B: Use External Redis Service** (e.g., Redis Cloud, Upstash)
- Sign up for a managed Redis service
- Get the connection URL

#### 4. Connect GitHub to Cloud Build

1. **Connect Repository**:
   - Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers)
   - Click "Connect Repository"
   - Select GitHub and authorize
   - Select your repository

2. **Create Build Trigger**:
   - Click "Create Trigger"
   - Name: `deploy-product-importer`
   - Event: Push to branch (e.g., `main` or `master`)
   - Configuration: Cloud Build configuration file
   - Location: `cloudbuild.yaml`
   - Click "Create"

#### 5. Configure Environment Variables

1. **Set Secrets in Secret Manager** (Recommended):
   ```bash
   # Create secrets
   echo -n "your-secret-key-here" | gcloud secrets create secret-key --data-file=-
   echo -n "your-database-url" | gcloud secrets create database-url --data-file=-
   echo -n "your-redis-url" | gcloud secrets create redis-url --data-file=-
   ```

2. **Set Environment Variables in Cloud Run**:
   - Go to Cloud Run → Select your service
   - Edit & Deploy New Revision
   - Under "Variables & Secrets", add:
     - `DATABASE_URL`: Your Neon PostgreSQL connection string (use `postgresql+asyncpg://` prefix for async)
     - `DATABASE_URL_SYNC`: Standard `postgresql://` connection string (for migrations)
   
   **Important:** For Neon PostgreSQL, ensure `sslmode=require` is in the connection string.
     - `REDIS_URL`: Your Redis connection URL
     - `CELERY_BROKER_URL`: Same as REDIS_URL
     - `CELERY_RESULT_BACKEND`: Same as REDIS_URL
     - `SECRET_KEY`: Generate with `python -c 'import secrets; print(secrets.token_hex(32))'`
     - `ENVIRONMENT`: `production`
     - `DEBUG`: `False`
     - `PORT`: `8080` (Cloud Run sets this automatically)

#### 6. Initial Deployment

1. **First Deploy via Cloud Build**:
   - Push your code to the connected GitHub branch
   - Cloud Build will automatically trigger
   - Monitor build in Cloud Build console

2. **Run Database Migrations**:
   ```bash
   # Using Cloud Run Jobs (recommended)
   gcloud run jobs create run-migrations \
     --image gcr.io/PROJECT_ID/product-importer-web:latest \
     --region us-central1 \
     --command alembic \
     --args upgrade,head \
     --set-env-vars DATABASE_URL_SYNC="YOUR_DATABASE_URL_SYNC"
   
   # Execute the job
   gcloud run jobs execute run-migrations --region us-central1
   ```

   Or manually (if you have local access):
   ```bash
   export DATABASE_URL_SYNC="postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require"
   alembic upgrade head
   ```

#### 7. Verify Deployment

1. **Check Services**:
   - Go to Cloud Run console
   - Verify both `product-importer-web` and `product-importer-worker` are deployed
   - Click on web service URL to test

2. **Check Logs**:
   ```bash
   # View logs
   gcloud run services logs read product-importer-web --region us-central1
   gcloud run services logs read product-importer-worker --region us-central1
   ```

### GCP Configuration

The application is configured to work with GCP:

- **DATABASE_URL**: Neon PostgreSQL or Cloud SQL connection string (supports SSL connections)
- **REDIS_URL**: Memorystore or external Redis connection URL
- **PORT**: Automatically set by Cloud Run (default: 8080)
- **DATABASE_URL_SYNC**: Auto-generated from DATABASE_URL if not set
- **Cloud Build**: Automatically builds and deploys on git push

### Cloud Run Services

- **product-importer-web**: FastAPI application (publicly accessible)
- **product-importer-worker**: Celery worker (private, scales to zero when idle)

### Monitoring and Logs

```bash
# View application logs
gcloud run services logs read product-importer-web --region us-central1 --tail

# View worker logs
gcloud run services logs read product-importer-worker --region us-central1 --tail

# Check service status
gcloud run services describe product-importer-web --region us-central1

# View in Console
# Go to Cloud Run → Select service → Logs tab
```

### Scaling

Cloud Run automatically scales based on traffic:
- **Web service**: Scales from 0 to configured max instances
- **Worker service**: Can scale from 0 (saves costs when idle)

Configure in Cloud Run console or via CLI:
```bash
# Set min/max instances
gcloud run services update product-importer-web \
  --min-instances=1 \
  --max-instances=10 \
  --region us-central1
```

### Cost Optimization (Free Tier)

- Use Cloud SQL Sandbox (free tier eligible)
- Use Memorystore basic tier or external Redis free tier
- Set worker min-instances to 0 (scales to zero when idle)
- Cloud Run free tier: 2 million requests/month

### Troubleshooting

1. **Database connection issues**:
   - Verify database is accessible (Neon or Cloud SQL)
   - Check connection string format (SSL required for Neon)
   - Ensure `sslmode=require` is in connection string for Neon
   - For Cloud SQL: Ensure Cloud Run service account has Cloud SQL Client role

2. **Redis/Celery issues**:
   - Verify Redis instance is running
   - Check Redis URL format
   - Ensure worker service is deployed and running
   - Check worker logs for connection errors

3. **Build/Deployment issues**:
   - Check Cloud Build logs
   - Verify `cloudbuild.yaml` syntax
   - Ensure Dockerfiles are correct
   - Check service account permissions

4. **Migration issues**:
   - Run migrations manually via Cloud Shell or Cloud Run Jobs
   - Verify DATABASE_URL_SYNC is set correctly
   - Check Cloud SQL connection from Cloud Shell

### Manual Deployment (Alternative to GitHub Integration)

If you prefer manual deployment:

```bash
# Build and push images
gcloud builds submit --config cloudbuild.yaml

# Or deploy individually
gcloud run deploy product-importer-web \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL=YOUR_URL,REDIS_URL=YOUR_URL
```

## License

(To be specified)
