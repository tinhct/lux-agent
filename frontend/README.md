# LUX Researcher Portal Manager Dashboard

This is a standalone manager dashboard and API middleware for the LUX Search Compliance Agent running on Google Cloud Vertex AI Agent Runtime.

## Dependencies

The project uses:
- **FastAPI** & **Uvicorn** for the web server and API endpoints.
- **Google ADK** & **Google Cloud AI Platform** for querying Vertex AI Agent Engine session services and predictions.

## Running the Dashboard

To launch the dashboard locally:

1.  Make sure your Application Default Credentials (ADC) are configured:
    ```bash
    gcloud auth application-default login
    ```

2.  Run the application with `uv`:
    ```bash
    uv run --project frontend python frontend/main.py
    ```

3.  Open [http://localhost:8081](http://localhost:8081) in your browser.
