# Kalawad Enterprise

A responsive, single-page front end introducing Kalawad Enterprise's three service areas:
Premium Watches, Transport, and Consultation.

The FastAPI backend serves the page, reads service details from Oracle, and stores customer
enquiries in Oracle Database.

## Run locally

1. Install the Python dependencies:

   ```sh
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set unique local values for `ORACLE_PASSWORD` and
   `ORACLE_SYS_PASSWORD`. Keep `.env` private; it is excluded from Git.

3. To run a local Oracle Database Free instance with Docker:

   ```sh
   set -a
   . ./.env
   set +a
   docker run --name kalawad-oracle -d \
     -p 127.0.0.1:1521:1521 \
     -e ORACLE_PASSWORD="$ORACLE_SYS_PASSWORD" \
     -e APP_USER="$ORACLE_USER" \
     -e APP_USER_PASSWORD="$ORACLE_PASSWORD" \
     -v kalawad-oracle-data:/opt/oracle/oradata \
     gvenzl/oracle-free:23-slim-faststart
   ```

   Wait for the database container to finish initializing, then create the tables and service
   records as the application user:

   ```sh
   docker exec -i kalawad-oracle sqlplus -S \
     "$ORACLE_USER/$ORACLE_PASSWORD@//localhost:1521/FREEPDB1" \
     < backend/schema.sql
   ```

   The database files are kept in the persistent `kalawad-oracle-data` Docker volume.
   `ORACLE_DSN` can instead point to an existing Oracle instance or Autonomous Database.

4. Start the website and API with the local environment file:

   ```sh
   uvicorn backend.main:app --reload --env-file .env
   ```

   Visit <http://localhost:8000>. The API documentation is at <http://localhost:8000/docs>.

The service routes are `GET /api/services` and `POST /api/inquiries`; `GET /api/health` is a
database-independent health check. Without an Oracle connection configured and initialized,
the site and health check still load, while database-backed routes return a clear service error.

To preview just the static page without the backend:

```sh
python3 -m http.server 8000 --directory .
```
