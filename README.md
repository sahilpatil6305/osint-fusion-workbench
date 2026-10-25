# OSINT Fusion Workbench — Sarvam AI

A human-in-the-loop Streamlit tool for analyzing analyst-supplied news reports, incident documents, and security advisories. Sarvam AI structures the supplied text; it does not independently verify claims or collect external data.

## Features

- Analyze pasted text and multiple PDF, TXT, or Markdown documents together.
- Preview extracted text and exclude or replace uploaded files before analysis.
- Track source IDs, filenames, and reliably extracted PDF page numbers.
- Flag encrypted, unreadable, empty, scanned, or partly text-readable PDFs. Scanned pages are not OCR-processed.
- Review a dark analyst dashboard with entity, timeline, relationship, claim, lead, and question views.
- Download PDF, JSON, and Markdown reports from the latest successful analysis without another model request.
- Preserve the prior successful analysis when a subsequent request fails.

Uploaded documents are untrusted input and are processed in memory. The app does not execute document content. Per-file uploads are limited to 10 MB, with up to 10 files and 30 MB total; combined extracted text is limited to 100,000 characters. The app does not silently truncate submitted text.

## Requirements

- Python 3.12 is recommended for Streamlit Community Cloud deployments. The project was also checked locally with Python 3.14.6.
- A Sarvam AI API key for live analysis. Synthetic tests and report generation do not require an API key or network request.

## Run locally

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Provide `SARVAM_API_KEY` using either a local `.env` file (keep it untracked) or the environment. The `.env` format is:

```dotenv
SARVAM_API_KEY=your_key_here
```

Then start the app:

```bash
python -m streamlit run app.py
```

## Run tests

```bash
python -m unittest -v test_reports test_source_documents
python -m unittest -v test_sarvam_client
python -m py_compile app.py sarvam_client.py reports.py source_documents.py
```

These tests use synthetic documents and do not call Sarvam.

## Deploy to Streamlit Community Cloud

1. Push this project to a GitHub repository you control. Keep `.env`, `.streamlit/secrets.toml`, credentials, and private keys out of the repository.
2. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) with GitHub and choose **Create app**.
3. Select the repository, branch, and `app.py` entrypoint. Choose Python 3.12 in Advanced settings.
4. In the deployment **Secrets** field, set the key as TOML (enter your actual key only in the provider’s secret field):

   ```toml
   SARVAM_API_KEY = "your_key_here"
   ```

5. Deploy, wait for the build to complete, and open the generated `*.streamlit.app` URL. Test an analysis in the deployed app to verify the cloud secret and Sarvam API access.

The app checks `st.secrets["SARVAM_API_KEY"]` first, then falls back to the environment and local `.env` for development. A deployed page loading successfully does not by itself verify Sarvam API connectivity.

See the official [Community Cloud deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) and [secrets management guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management) for current provider steps.
