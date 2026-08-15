& "C:\Program Files\Microsoft Visual Studio\18\Community\Common7\Tools\Launch-VsDevShell.ps1"

Set-Location "C:\project\Melawai-Test"

.\.venv\Scripts\Activate.ps1

uvicorn app:app --host 0.0.0.0 --port 8000