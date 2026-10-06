"""Check job-board labels for one Mantiks company; never prints credentials or job details."""
import json
import os
import sys
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import quote

import requests


BASE_URL = "https://dashboard.mantiks.io/api/v2"
COMPANY_QUERY = os.getenv("MANTIKS_COMPANY_QUERY", "Intermarché")
RACINE = Path(__file__).resolve().parent.parent


def save_mantiks_result(output_root, company_name, result):
    """Enregistre une réponse Mantiks dans un dossier de données dédié."""
    output_root.mkdir(parents=True, exist_ok=True)
    safe_company = "".join(c if c.isalnum() or c in "-._ " else "_" for c in company_name)
    safe_company = safe_company.strip().replace(" ", "-") or "entreprise"
    output_file = output_root / f"{date.today():%Y-%m-%d}_{safe_company}.json"
    payload = {
        "schema": 1,
        "source": "Mantiks",
        "company": company_name,
        "date": date.today().isoformat(),
        "active": result.get("active", 0),
        "returned": result.get("returned", len(result.get("jobs") or [])),
        "jobs": result.get("jobs") or [],
    }
    output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_file


def normaliser(value):
    decomposed = unicodedata.normalize("NFKD", value or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def get_json(session, path):
    response = session.get(f"{BASE_URL}{path}", timeout=30)
    response.raise_for_status()
    return response.json()


def main():
    api_key = os.getenv("MANTIKS_API_KEY")
    if not api_key:
        print("MANTIKS_API_KEY is not configured in GitHub Actions secrets.")
        return 2

    session = requests.Session()
    session.headers.update({"X-API-KEY": api_key, "Accept": "application/json"})

    try:
        companies = get_json(session, f"/companies/search?query={quote(COMPANY_QUERY)}")
        query_tokens = [token for token in normaliser(COMPANY_QUERY).replace("-", " ").split() if token]
        candidates = [
            company for company in companies
            if all(token in normaliser(company.get("name")) for token in query_tokens)
        ]
        exact = [
            company for company in candidates
            if normaliser(company.get("name")) == normaliser(COMPANY_QUERY)
        ]
        selected = exact if len(exact) == 1 else candidates if len(candidates) == 1 else []
        if len(selected) != 1:
            print(f"Could not identify one company matching {COMPANY_QUERY!r}; no credit-consuming request was made.")
            for company in candidates[:10]:
                print(f"Candidate: {company.get('name', 'unknown')}")
            return 2

        locations = get_json(session, "/locations/search?query=France")
        france = [
            location for location in locations
            if location.get("type") == "country" and location.get("country") == "France"
        ]
        if not france:
            print("Mantiks did not return a France location; no credit-consuming request was made.")
            return 2

        company = selected[0]
        payload = {
            "locations": [{"id": france[0]["id"], "radius": None}],
            "job_title_query": None,
            "job_title_include": [],
            "job_title_exclude": [],
            "description_include": [],
            "description_exclude": [],
            "description_query": None,
            "published_date_window_days": 360,
            "volume": {"gte": None, "lte": None},
            "is_reposting": False,
        }
        response = session.post(
            f"{BASE_URL}/companies/{quote(company['id'], safe='')}/jobs",
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as error:
        status = getattr(getattr(error, "response", None), "status_code", None)
        print(f"Mantiks request failed{f' (HTTP {status})' if status else ''}; response details omitted.")
        return 1
    finally:
        session.close()

    saved = save_mantiks_result(RACINE / "data" / "mantiks", company.get("name", COMPANY_QUERY), result)
    jobs = result.get("jobs") or []
    boards = Counter(job.get("job_board") or "(missing)" for job in jobs)
    print(f"Company: {company.get('name', 'Intermarché')}")
    print(f"Active jobs: {result.get('active', 0)}; returned: {result.get('returned', len(jobs))}")
    print(f"Saved result: {saved.relative_to(RACINE)}")
    print("job_board counts in the returned sample:")
    for board, count in boards.most_common():
        print(f"  {board}: {count}")

    wttj_count = sum(
        count for board, count in boards.items()
        if "welcometothejungle" in normaliser(board).replace(" ", "")
        or "wttj" in normaliser(board).replace(" ", "")
    )
    print(f"WTTJ-labelled jobs in this sample: {wttj_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())