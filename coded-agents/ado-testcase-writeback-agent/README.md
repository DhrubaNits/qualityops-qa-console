# QualityOps ADO TestCase WriteBack Agent

UiPath coded agent that reads a single `question` JSON string, creates one Azure DevOps Test Case work item per generated QA scenario, and links each Test Case as a child of the source User Story.

Required UiPath Orchestrator Assets:

- `ADO_ORGANIZATION`
- `ADO_PROJECT`
- `ADO_PAT`

The agent reads these Orchestrator Assets first. For local testing, it falls back to environment variables with the same names. Do not store the PAT in source control.

Local smoke test:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

UiPath setup after dependencies are installed:

```powershell
cmd /c ".venv\Scripts\activate.bat && uip.cmd codedagent setup --force && uip.cmd codedagent init"
```
