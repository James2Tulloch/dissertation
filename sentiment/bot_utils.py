import requests
import time

RAPIDAPI_HOST = "botometer-pro.p.rapidapi.com"   # from the docs
RAPIDAPI_URL = f"https://{RAPIDAPI_HOST}/4/check_account"

def check_bot_account(
    screen_name: str,
    rapidapi_key: str,
    sleep_seconds=1
):
    """
    Calls the Botometer Pro (RapidAPI) endpoint to check if a Twitter account
    is a bot. Returns a dict with relevant bot scores or an error message.

    Note: This example calls the "Check Account" (v4) endpoint:
    https://rapidapi.com/OSoMe/api/botometer-pro/
    """
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
        "Content-Type": "application/json"
    }
    payload = {
        "user": {
            "screen_name": screen_name
        }
    }

    try:
        response = requests.post(RAPIDAPI_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

    # Respect rate limits or courtesy sleep
    time.sleep(sleep_seconds)

    return data


def bulk_check_bot_accounts(
    screen_names,
    rapidapi_key: str,
    sleep_seconds=1
):
    """
    Checks multiple Twitter screen_names. Returns a list of results.
    """
    results = []
    for name in screen_names:
        result = check_bot_account(name, rapidapi_key, sleep_seconds)
        results.append({"screen_name": name, "botometer_result": result})
    return results

