def load_correct_creds (creds):
    return creds['prod']['access_key'], creds['prod']['secret_key']


def test_api_key(client, BinanceAPIException):  # Checks to see if API keys supplied returns error

#    Args : 
#        client(class): binance client class
#        BinanceAPIException (class): binance exception class
#        
#    Returns: 

    try:
        client.get_account()
        return True, "API key validated succesfully"
    except BinanceAPIException as e:

        if e.code in [-2015, 2014]:
            bad_key = "Your API key is not formated correctly"
            america = "If you are in America, you will have to update the config to set AMERICAN_USER: True"
            ip_b = "If you set an IP on block your keys make sure this IP address is allowed. Check ipinfo.io/ip"

            msg = f"Your API key is either incorrect, IP blocked, or incorrect tld/permissions... \n most likely: {bad_key}\n {america}\n {ip_b}\n "
        
        elif e.code == -2021:
            issue = "https://github.com/CyberPunkMetalHead/Binance-volatility-trading-bot/issues/28"
            desc = "Ensure your OS is time synced with a timeserver. See issue." # what???
            msg = f"Timestamp for this request was 1000 ms ahead of the server's time. {issue}\n {desc} "

        else :
            msg = "Encountered an API error code that left you with the ass pointing North. Open issue... \n "
            msg += e

        return False, msg

    except Exception as e: 
        return False, f"Fallback exception occured: \n{e}"