import urllib.request, json, urllib.parse
token="8875604424:AAF6hwE59a_A91ZrOyyLAkqtTuS8_FY5pNA"
url=f"https://api.telegram.org/bot{token}/getMe"
try:
    with urllib.request.urlopen(url) as resp:
        data=json.loads(resp.read().decode())
        print(data)
except Exception as e:
    print("Error:", e)