
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
# pyinstaller --onefile --name "my_script_$timestamp" my_script.py

pyinstaller --add-data "settings.json;." --add-data "assets/*;assets" --onefile sfs.py --name "StarfieldStorm_$timestamp"