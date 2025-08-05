import json
import requests
from config.settings import PLAYFAB_TITLE_ID, PLAYFAB_SECRET_KEY
from config.constants import CURRENCY_PACKS

def get_currency_packs():
    API_URL = f"https://{PLAYFAB_TITLE_ID}.playfabapi.com/Server/GetTitleData"

    headers = {
        "Content-Type": "application/json",
        "X-SecretKey": PLAYFAB_SECRET_KEY
    }

    
    request_body = {
        "Keys": [CURRENCY_PACKS] 
    }

    try:
        response = requests.post(API_URL, headers=headers, data=json.dumps(request_body))
        response.raise_for_status()  # Raise an exception for bad status codes

        result = response.json()

        if result.get("code") == 200:
            title_data = result.get("data", {}).get("Data", {})
            # Expecting something like {'CURRENCY_PACKS': '{...json string...}'}
            packs_json = title_data.get(CURRENCY_PACKS)
            if packs_json:
                try:
                    packs_dict = json.loads(packs_json)
                    return packs_dict
                except Exception as e:
                    return {"error": f"Failed to parse CURRENCY_PACKS: {e}"}
            else:
                return {"error": "CURRENCY_PACKS not found in title data"}
        else:
            return {"error": result.get('errorMessage')}

    except requests.exceptions.RequestException as e:
        return {"error": str(e)}




def update_playfab_cash(playfab_id: str, cash_to_add: int):
    get_data_url = f"https://{PLAYFAB_TITLE_ID}.playfabapi.com/Admin/GetUserData"
    get_response = requests.post(get_data_url, headers={
        "X-SecretKey": PLAYFAB_SECRET_KEY
    }, json={"PlayFabId": playfab_id})

    current_cash = 0
    try:
        current_cash = int(get_response.json()["data"]["Data"]["Cash"]["Value"])
    except:
        current_cash = 0

    new_cash = current_cash + cash_to_add

    update_data_url = f"https://{PLAYFAB_TITLE_ID}.playfabapi.com/Admin/UpdateUserData"
    update_response = requests.post(update_data_url, headers={
        "X-SecretKey": PLAYFAB_SECRET_KEY
    }, json={
        "PlayFabId": playfab_id,
        "Data": {"Cash": str(new_cash)}
    })

    return update_response.ok


def update_playfab_coins(playfab_id: str, coins_to_add: int):
    get_data_url = f"https://{PLAYFAB_TITLE_ID}.playfabapi.com/Admin/GetUserData"
    headers = {
        "X-SecretKey": PLAYFAB_SECRET_KEY
    }

    current_coins = 0
    try:
        get_response = requests.post(get_data_url, headers=headers, json={"PlayFabId": playfab_id})
        get_response.raise_for_status()
        current_coins = int(get_response.json()["data"]["Data"].get("Coins", {}).get("Value", 0))
    except Exception as e:
        print(f"Error getting current coins: {e}")

    new_coins = current_coins + coins_to_add

    update_data_url = f"https://{PLAYFAB_TITLE_ID}.playfabapi.com/Admin/UpdateUserData"
    update_response = requests.post(update_data_url, headers=headers, json={
        "PlayFabId": playfab_id,
        "Data": {
            "Coins": str(new_coins)
        }
    })

    return update_response.ok

