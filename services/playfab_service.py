import json
import requests
from config.settings import PLAYFAB_TITLE_ID, PLAYFAB_SECRET_KEY
from config.constants import CURRENCY_PACKS, COIN_MODELS, MEMBERSHIPS, ACTIVE_MEMBERSHIP_ID

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


def get_models():
    API_URL = f"https://{PLAYFAB_TITLE_ID}.playfabapi.com/Server/GetTitleData"

    headers = {
        "Content-Type": "application/json",
        "X-SecretKey": PLAYFAB_SECRET_KEY
    }

    request_body = {
        "Keys": [COIN_MODELS]
    }

    try:
        response = requests.post(API_URL, headers=headers, data=json.dumps(request_body))
        response.raise_for_status()

        result = response.json()

        if result.get("code") == 200:
            title_data = result.get("data", {}).get("Data", {})
            models_json = title_data.get(COIN_MODELS)
            if models_json:
                try:
                    models_dict = json.loads(models_json)
                    return models_dict
                except Exception as e:
                    return {"error": f"Failed to parse COIN_MODELS: {e}"}
            else:
                return {"error": "COIN_MODELS not found in title data"}
        else:
            return {"error": result.get('errorMessage')}

    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def get_memberships():
    API_URL = f"https://{PLAYFAB_TITLE_ID}.playfabapi.com/Server/GetTitleData"

    headers = {
        "Content-Type": "application/json",
        "X-SecretKey": PLAYFAB_SECRET_KEY
    }

    request_body = {
        "Keys": [MEMBERSHIPS]
    }

    try:
        response = requests.post(API_URL, headers=headers, data=json.dumps(request_body))
        response.raise_for_status()

        result = response.json()

        if result.get("code") == 200:
            title_data = result.get("data", {}).get("Data", {})
            memberships_json = title_data.get(MEMBERSHIPS)
            if memberships_json:
                try:
                    return json.loads(memberships_json)
                except Exception as e:
                    return {"error": f"Failed to parse MEMBERSHIPS: {e}"}
            else:
                return {"error": "MEMBERSHIPS not found in title data"}
        else:
            return {"error": result.get("errorMessage")}

    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def get_active_membership_id(playfab_id: str):
    get_data_url = f"https://{PLAYFAB_TITLE_ID}.playfabapi.com/Admin/GetUserData"

    try:
        response = requests.post(get_data_url, headers={
            "X-SecretKey": PLAYFAB_SECRET_KEY
        }, json={"PlayFabId": playfab_id})
        response.raise_for_status()

        user_data = response.json().get("data", {}).get("Data", {})
        return user_data.get(ACTIVE_MEMBERSHIP_ID, {}).get("Value", "")

    except Exception as e:
        print(f"Error getting active membership for user {playfab_id}: {e}")
        return ""


def set_active_membership(playfab_id: str, membership_id: str):
    update_data_url = f"https://{PLAYFAB_TITLE_ID}.playfabapi.com/Admin/UpdateUserData"

    try:
        update_response = requests.post(update_data_url, headers={
            "X-SecretKey": PLAYFAB_SECRET_KEY
        }, json={
            "PlayFabId": playfab_id,
            "Data": {
                ACTIVE_MEMBERSHIP_ID: membership_id
            }
        })
        update_response.raise_for_status()
        return update_response.ok

    except Exception as e:
        print(f"Error setting active membership {membership_id} for user {playfab_id}: {e}")
        return False

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


def update_playfab_points(playfab_id: str, points_to_add: int):
    get_data_url = f"https://{PLAYFAB_TITLE_ID}.playfabapi.com/Admin/GetUserData"
    get_response = requests.post(get_data_url, headers={
        "X-SecretKey": PLAYFAB_SECRET_KEY
    }, json={"PlayFabId": playfab_id})

    current_points = 0
    try:
        current_points = int(get_response.json()["data"]["Data"]["Points"]["Value"])
    except:
        current_points = 0

    new_points = current_points + points_to_add

    update_data_url = f"https://{PLAYFAB_TITLE_ID}.playfabapi.com/Admin/UpdateUserData"
    update_response = requests.post(update_data_url, headers={
        "X-SecretKey": PLAYFAB_SECRET_KEY
    }, json={
        "PlayFabId": playfab_id,
        "Data": {"Points": str(new_points)}
    })

    return update_response.ok


def get_playfab_points(playfab_id: str) -> int:
    get_data_url = f"https://{PLAYFAB_TITLE_ID}.playfabapi.com/Admin/GetUserData"
    try:
        get_response = requests.post(get_data_url, headers={
            "X-SecretKey": PLAYFAB_SECRET_KEY
        }, json={"PlayFabId": playfab_id})
        get_response.raise_for_status()
        return int(get_response.json()["data"]["Data"].get("Points", {}).get("Value", 0))
    except Exception as e:
        print(f"Error getting points for user {playfab_id}: {e}")
        return 0


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



def unlock_coin_model(playfab_id: str, model_id: str):
    get_data_url = f"https://{PLAYFAB_TITLE_ID}.playfabapi.com/Admin/GetUserData"
    update_data_url = f"https://{PLAYFAB_TITLE_ID}.playfabapi.com/Admin/UpdateUserData"

    headers = {
        "X-SecretKey": PLAYFAB_SECRET_KEY
    }

    try:
        
        get_response = requests.post(get_data_url, headers=headers, json={"PlayFabId": playfab_id})
        get_response.raise_for_status()

        user_data = get_response.json().get("data", {}).get("Data", {})
        unlocked_models_json = user_data.get("UNLOCKED_COINS", {}).get("Value", "{}")

        # Parse it (or initialize an empty dict)
        unlocked_models = json.loads(unlocked_models_json) if unlocked_models_json else {}

        
        unlocked_models[model_id] = True

        
        update_response = requests.post(update_data_url, headers=headers, json={
            "PlayFabId": playfab_id,
            "Data": {
                "UNLOCKED_COINS": json.dumps(unlocked_models)
            }
        })
        update_response.raise_for_status()

        return update_response.ok

    except Exception as e:
        print(f"Error unlocking model {model_id} for user {playfab_id}: {e}")
        return False
