# NYC 311 Scout

NYC residents can use Scout to explore recent 311 reports by ZIP code (maximum lookback of 90 days from today). It does 3 main things:
1. Generates a 311 report summary for a given ZIP code
2. Compares two ZIP codes' reports
3. Checks trends for a selected concern group (Noise, Housing, Parking, Sanitation, Rodents)

## Tools

- `get_zip_report`: Summarizes 311 reports for a ZIP code and time period (max 90 day lookback from today).
- `compare_zip_priorities`: Compares two ZIP codes' concerns such as noise or rodents.
- `get_concern_trend`: Compares reports for one concern across two time periods.

## How to use it

Enter a ZIP code in the form or ask Scout a question in the chat. For comparisons, provide two ZIP codes and the issues you care about. For trends, name a ZIP, concern, and time period; the default is 30 days. Tool calls appear above each answer. The live app is at [NYC 311 Scout](https://nyc-311-data-agent-git-248198644776.us-east1.run.app).

To run locally run `uv sync --locked`. Then run `uv run app.py` and open http://localhost:8000. NYC 311 lookups are public and need no API key.

Try these queries:

1. “Summarize 311 reports in 10027 over the last 30 days.”
2. “Compare 10027 and 10025. I care about noise and rodents.”
3. “Has noise reporting in 10027 increased over the last 30 days compared with the previous 30?”

311 reports are resident submissions, may repeat, and are not verified measurements of neighborhood conditions. Concern groups are approximate keyword matches; counts are not adjusted for population or reporting habits. Source: [NYC Open Data 311](https://data.cityofnewyork.us/d/erm2-nwe9).
