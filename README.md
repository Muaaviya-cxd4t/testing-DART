# DART | UI/UX Tester

A Flask mini-project that reads a Figma file, extracts rough UI features, and runs four trained Random Forest models against simulated user profiles.

## Project layout

```text
miniproject/
├── app.py
├── requirements.txt
├── .env.example
├── templates/
│   ├── index.html
│   └── results.html
├── static/
│   ├── css/style.css
│   ├── js/main.js
│   └── media/tutorial.mp4   # replace this empty placeholder with your 16:9 tutorial
├── models/                  # put the four trained *_model.pkl files here
└── datasets/                # synthetic training CSVs, for reference
```

## Setup (Windows PowerShell)

```powershell
cd miniproject
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Open `.env` and paste your Figma token. Do not upload `.env` to GitHub.

## Add the trained models

Extract the contents of your trained model ZIP directly into `models/`. It should contain:

- `grandparent_model.pkl`
- `elder_adult_model.pkl`
- `youth_model.pkl`
- `children_model.pkl`

The app expects the model bundles produced by the DART training notebook. If your ZIP contains a `models/` folder, extract that folder's contents into this project's `models/` directory.

## Run

```powershell
python app.py
```

Visit `http://127.0.0.1:5000`.

## Figma permissions

The design must be accessible to the account associated with the token. The API token needs file content read permission. Paste a Figma design/file URL, not a prototype share link.

## Important project limitation

The four user agents and training data are synthetic. Predictions are model-based estimates for a mini-project demonstration, not measured results from real users or validated usability research. The parser also estimates spacing, layout complexity, and interactive elements from the Figma node tree; these are proxies.
