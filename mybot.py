from ctypes.wintypes import MSG
import os   # for environment variables
from binance.client import Client
from binance.exceptions import BinanceAPIException

#from binance.client import Client   # For Binance API and websockets
from datetime import date, datetime, timedelta    #
import time                                 # for dates
from itertools import count     # To repeatedly execute the code
import json     #to store trades and sell asstes
import sys
from colorama import init
import threading
import importlib
import glob


sys.path.insert(1, r'C:\Users\valen\Desktop\stuff\mybot\handle_creds.py')
sys.path.insert(2, r'C:\Users\valen\Desktop\stuff\mybot\parameters.py')


from handle_creds import load_correct_creds, Test_api_key


from parameters import parse_args, load_config



global session_profit
session_profit = 0




init()


class txcolors:
    BUY = '\033[92m'
    WARNING = '\033[93m'
    SELL_LOSS = '\033[91m'
    SELL_PROFIT = '\033[32m'
    DIM = '\033[2m\033[35m'
    DEFAULT = '\033[39m'

TESTNET = True

api_key_test = str('FkXHkYaBQXr4gElLiqxMZRbZ22DwdE4lpCYO3zUlGE6mReYEAbvtRj5YAOWtayMK')
api_secret_test = str('0eEz8yicKdY7nLB34ZxdMwYLeS9XqXsTrym7P0rEiJ1cHiUEqft69nXUbJh1S0mD')

api_key_live = os.getenv('binance_api_stalkbot_live')
api_secret_live = os.getenv('binance_secret_stalkbot_live')

if TESTNET:
    client = Client(api_key_test, api_secret_test)
    client.API_URL = 'https://testnet.binance.vision/api'
else:
    client = Client(api_key_live, api_secret_live)


Pair_with = 'USDT'
#qty = 10 # tamaño de las compras realizadas en cada trade
#FIATS = ['EURUSDT', 'GBPUSDT', 'JPYUSDT', 'USDUSDT', 'DOWN', 'UP'] # by default we're excluding the most popular fiat pairs
                                                                    # and some margin keywords, as we're only working on the SPOT account


Delta_T = 5  #EL número de minutos para ver la diferencia de precio

Delta_Price = 3 # El cambio porcentual de precio a partir del cual el bot decide comprar.
                # por default, si hay una suba de 3% en 5 minutos, se compra el token.


Stop_loss = 3   # Porcentaje de disminución en que el bot vende para prevenir mayores perdidas
Take_profit = 6 # Porcentaje de suba en que el bot vende para asegurar la ganancia

old_out =  sys.stdout


class st_ampe_dout:

    n1 = True
    def write(self, x):  # Juiced up write function 
        
        if x == '\n':
            old_out.write(x)
            self.n1 = True
        elif self.n1:
            old_out.write(f'{txcolors.DIM}[{str(datetime.now().replace(microsecond=0))}]{txcolors.DEFAULT} {x}')
            self.n1 = False
        else:
            old_out.write(x)

    def flush(self):
        pass


sys.stdout = st_ampe_dout()


def get_price(add_to_historical = True): # Return the current price for all coins on Binance

    global historical_prices, hsp_head

    initial_price = {}
    prices = client.get_all_tickers()

    for coin in prices:

        if Custom_list:
            if any(item + Pair_with == coin['symbol'] for item in tickers ) and all(item not in coin['symbol'] for item in FIATS):
                initial_price[coin['symbol']] = { 'price': coin['price'], 'time': datetime.now() }
            else:
                if Pair_with in coin['symbol'] and all(item not in coin['symbol'] for item in FIATS):
                    initial_price[coin['symbol']] = { 'price': coin['price'], 'time': datetime.now()}

    if add_to_historical:
        hsp_head += 1

        if hsp_head == Recheck_interval:
            hsp_head = 0

        historical_prices[hsp_head] = initial_price

    return initial_price


def wait_for_price():
    # Calls the initial price and ensures the correct amount of time has passed
    # before reading it again

    global historical_prices, hsp_head, volatility_cooloff

    volatile_coins = {}
    externals = {}

    coins_up = 0
    coins_down = 0
    coins_unchanged = 0

    pause_bot()

    if historical_prices[hsp_head]['BNB' + Pair_with]['time'] > datetime.now() - timedelta(minutes= float( Delta_T / Recheck_interval)):
        # sleep for the amount of time required
        time.sleep( (timedelta(minutes= float(Delta_T / Recheck_interval)) - (datetime.now() - historical_prices[hsp_head]['BNB' + Pair_with]['time']) ).total_seconds() )

    print(f'Working --- Session profit:{session_profit:.2f}% Est:${(Qty * session_profit) / 100:.2f}')

    
    # retrieve latest prices
    get_price()


    # Calculate the price change
    for coin in historical_prices[hsp_head]:

        # Min and Max prices in the period
        Min_p = min( historical_prices, key = lambda x: float('inf') if x is None else float(x[coin]['price']))
        Max_p = max( historical_prices, key = lambda x: -1 if x is None else float(x[coin]['price']) )

        threshhold_check = ( -1.0 if Min_p[coin]['time'] > Max_p[coin]['time'] else 1.0 ) * ( float( Min_p[coin]['price'])- float(Min_p[coin]['price']) )/ float(Min_p[coin]['price'])  *100.0

        if threshhold_check > Change_in_price: 
            coins_up += 1

            if coin not in volatility_cooloff:
                volatility_cooloff[coin] = datetime.now() - timedelta(minutes=Delta_T)

            # Include coin as volatile only if it hasn't been picked up in the last Delta_T minutes already
            if datetime.now() >= volatility_cooloff[coin] + timedelta(minutes=Delta_T):
                volatility_cooloff[coin] = datetime.now()

                if len(coins_bought) + len(volatile_coins) < Max_coins or Max_coins == 0:
                    volatile_coins[coin] = round(threshhold_check, 3)
                    print(f'{coin} has gained {volatile_coins[coin]}% within the last {Delta_T} minutes, calculating volume in {Pair_with} ')

                else:
                    print(f'{txcolors.WARNING}{coin} has gained {round(threshhold_check, 3)}% within the last {Delta_T} minutes but the maximun number of coins is already held.')

        elif threshhold_check < Change_in_price :
            coins_down +=1

        else:
            coins_unchanged +=1


    externals = external_signals()
    exnumber = 0

    for excoin in externals:
        if excoin not in volatile_coins and excoin not in coins_bought and (len(coins_bought) + exnumber) < Max_coins:
            volatile_coins[excoin] = 1
            exnumber += 1
            print(f'External signal received on {excoin}, calculating volume in {Pair_with}')

    return volatile_coins, len(volatile_coins), historical_prices[hsp_head]

    
def external_signals():
    external_list = {}
    signals = {}

    #Check directory and load pairs from files into external_list
    signals = glob.glob('signals/*.exs')
    for filename in signals:
        for line in open (filename):
            symbol = line.strip()
            external_list[symbol] = symbol

        try: 
            os.remove(filename)
        except:
            if DEBUG: print(f'{txcolors.WARNING} Could not remove external signalling file {txcolors.DEFAULT}')

    return external_list


def pause_bot():
    # Pause the script when external indicators detect a bearish trend in the market
    global bot_paused, session_profit, hsp_head

    # Start counting for how long the bot's been paused
    Start_time = time.perf_counter()

    while os.path.isfile('signals/paused.exc'):

        if bot_paused == False:
            print(f'{txcolors.WARNING} Pause buying due to change in market conditions, stop loss and take profit will continue to work...{txcolors.DEFAULT}')
            bot_paused == True

        # Sell function has to work even while in a pause
        coins_sold = sell_coins()
        remove_from_portfolio(coins_sold)
        get_price(True)

        # pausing here
        if hsp_head == 1: print(f'Paused... Session profit:{session_profit:.2f}% Est:${(Qty * session_profit) / 100:.2f}')
        time.sleep((Delta_T * 60) / Recheck_interval)

    else:
        # Stop the count of paused time
        stop_time = time.perf_counter()
        time_elapsed = timedelta(seconds= int(stop_time - Start_time))

        # Resume the bot and set bot_paused = False
        if bot_paused == True:
            print(f'{txcolors.WARNING} Resuming the buy due to change in market conditions, total sleep time: {time_elapsed}{txcolors.DEFAULT}')
            bot_paused = False

    return


def convert_volume():   # Convert the volume given in Qty from USDT to each of the coin's volume

    volatile_coins, number_of_coins, last_price = wait_for_price()
    lot_size = {}
    volume = {}

    for coin in volatile_coins:
        # Find the correct step size for each coin
        # max accuracy for BTC for example is 6 decimal points
        # while XRP is only 1
        try:
            info = client.get_symbol_info(coin)
            step_size = info['filters'][2]['stepSize']
            if lot_size[coin] < 0 :
                lot_size = 0
        
        except:
            pass

        # Calculate the volume in coin from Qty in USDT
        volume[coin] = float(Qty / float(last_price[coin]['price']))

        # Define the volume with the correct step size 
        if coin not in lot_size:
            volume[coin] = float('{:.1f}'.format(volume[coin]))

        else:
            # if lot size has no decimal points, make the volume an integer
            if lot_size[coin] == 0:
                volume[coin] = int(volume[coin])
            else:
                volume[coin] = float('{:.{}f}'.format(volume[coin], lot_size[coin]))

    return volume, last_price


def buy():      # Place buy orders for each volatile coin found
    volume, last_price = convert_volume()
    orders = {}

    for coin in volume:

        # Buy if there aren't already active trades on the coin
        if coin not in coins_bought:
            print(f'{txcolors.BUY} Preparing to buy {volume[coin]} {coin}{txcolors.DEFAULT} ')

            if Test_mode:
                orders[coin] = [{
                    'symbol': coin,
                    'orderId': 0,
                    'time': datetime.now().timestamp()
                }]

                # Log trade
                if Log_trades:
                    write_log(f"Buy : {volume[coin]} {coin} - {last_price[coin]['price']}")


                continue

            try:
                buy_limit = client.create_order(
                    symbol = coin,
                    side = 'BUY',
                    type = 'MARKET',
                    quantity = volume[coin]
                )

            # Handle any error in case the position cannot be placed
            except Exception as e:
                print(e)

            # Run the else block if the position has been placed and return order info
            else:
                orders[coin] = client.get_all_orders( symbol = coin, limit = 1 )

                # Binance sometimes returns an empty list, the code is never gonna give you up
                # and will wait here until Binance returns the order
                while orders[coin] == []:
                    print('Binance is kinda slow returning the order, calling the API again...')
                    orders[coin] = client.get_all_orders( symbol = coin, limit = 1 )
                    time.sleep(1)

                else: 
                    print('Order returned, saving order to file')

                    # Log trade
                    if Log_trades:
                        write_log(f"Buy: {volume[coin]}{coin} - {last_price[coin]['price']} ")

        else:
            print(f'Signal detected, but there is already an active trade on {coin}')

    return orders, last_price, volume


def sell_coins():       # Sell coins that have reached the stop loss or take profit threshold

    global hsp_head, session_profit
    
    last_price = get_price(False)
    coins_sold = {}

    for coin in list(coins_bought):
        TP = float(coins_bought[coin]['bought_at']) + (float(coins_bought[coin]['bought_at']) * coins_bought[coin]['take_profit'] ) / 100
        SL = float(coins_bought[coin]['bought_at']) + (float(coins_bought[coin]['bought_at']) * coins_bought[coin]['stop_loss'] ) / 100

        last_price = float(coins_bought[coin]['price'])
        Buy_price = float(coins_bought[coin]['bought_at'])
        Price_change = float((last_price - Buy_price) / Buy_price *100)

        # Check that the price is above the take profit and readjust the SL and TP accordingly if trailing stop loss employed
        if last_price > TP and Use_trailing_stop_loss:

            # Increasing the TP by Trailing_take_profit (essentially next time to readjust SL)
            coins_bought[coin]['take_profit'] = Price_change + Trailing_take_profit
            coins_bought[coin]['stop_loss'] = coins_bought[coin]['take_profit'] - Trailing_stop_loss
            if DEBUG: print(f"{coin} TP reached, adjusting TP {coins_bought[coin]['take_profit']:.2f} and SL {coins_bought[coin]['stop_loss']:.2f} accordingly to lock-in profit ")
            continue

        #check that the price is below the stop loss or above the take profit (if trailling stop loss not used) and sell if this is the case
        if last_price < SL or last_price > TP and not Use_trailing_stop_loss: 
            print(f" {txcolors.SELL_PROFIT if Price_change >= 0. else txcolors.SELL_LOSS}TP or SL reached, selling {coins_bought[coin]['volume']} {coin} - {Buy_price} - {last_price} : {Price_change-(Trading_fee*2):.2f}% Est:${(Qty*(Price_change - (Trading_fee*2)))/100:.2f}{txcolors.DEFAULT}")

            # Try and create a real order
            try:
                if not Test_mode:
                    sell_coins_limit = client.create_order(
                        symbol = coin,
                        side = 'SELL',
                        type = 'MARKET',
                        quantity = coins_bought[coin]['volume']
                    )

            # Handle an eventual unability to place a position
            except Exception as e:
                print(e)

            # run the else block if coin has been sold and create a dict for each coin sold
            else:
                coins_sold[coin] = coins_bought[coin]

                # Prevent system from buying this coin for the next Delta_T minutes
                volatility_cooloff[coin]= datetime.now()

                if Log_trades :
                    profit = ((last_price - Buy_price) * coins_sold[coin]['volume']) * (1 - (Trading_fee*2)) 
                    write_log(f"Sell: {coins_sold[coin]['volume']}{coin} - {Buy_price} - {last_price}  Profit: {profit:.2f} {Price_change - (Trading_fee*2):.2f}% ")
                    session_profit = session_profit + (Price_change - (Trading_fee*2) )
            continue
            

        # no action; just print once every Delta_T
        if hsp_head == 1:
            if len(coins_bought) > 0:
                print(f"TP or SL not yet reached, not selling {coin} for now. {Buy_price} - {last_price}: {txcolors.SELL_PROFIT if Price_change >=0. else txcolors.SELL_LOSS}{Price_change - (Trading_fee*2):.2f}% Est:${(Qty*(Price_change - (Trading_fee*2)))/100:.2f}{txcolors.DEFAULT}")


    if hsp_head == 1 and len(coins_bought) == 0: print(f"Not HODLING any coins")

    return coins_sold


def update_portfolio(orders, last_price, volume):   # Add every coin bought to our portfolio for tracking/selling later

    if DEBUG: print(orders)
    for coin in orders:

        coins_bought[coin] = {
            'symbol' : orders[coin][0]['symbol'],
            'orderid': orders[coin][0]['orderId'],
            'timestamp': orders[coin][0]['time'],
            'bought_at': last_price[coin]['price'],
            'volume': volume[coin],
            'stop_loss': -Stop_loss,
            'take_profit': Take_profit, 
        }

        # Save the coins in a json file in the same directory
        with open(Coins_bought_file_path, 'w') as file:
            json.dump(coins_bought, file, indent= 4)

        print (f"Order with id {orders[coin][0]['orderId']} placed and saved to file")


def remove_from_portfolio(coins_sold):    # Remove coins sold due to SL or TP from portfolio

    for coin in coins_sold:
        coins_bought.pop(coin)

    with open(Coins_bought_file_path, 'w') as file:
        json.dump(coins_bought, file, indent= 4)


def write_log(logline):
    timestamp = datetime.now().strftime('%d %m %H:%M::%S')
    with open(Log_file, 'a+') as f:
        f.write(timestamp + ' ' + logline + '\n')


if __name__ == '__main__' : 

    #Load arguments, then parse settings
    args = parse_args()
    mymodule = {}

    global bot_paused
    bot_paused = False

    DEFAULT_CONFIG_FILE = r'C:\Users\valen\Desktop\stuff\mybot\config.yml'
    DEFAULT_CREDENTIALS = r'C:\Users\valen\Desktop\stuff\Binance-volatility-trading-bot-main\creds.yml'

    config_file = args.config if args.config else DEFAULT_CONFIG_FILE
    creds_file = args.creds if args.creds else DEFAULT_CREDENTIALS
    parsed_config = load_config(config_file)
    parsed_creds = load_config(creds_file)


    # By default, no debugging
    DEBUG = False 

    # System Variables
    Test_mode = parsed_config['script_opt']['Test_mode']
    Log_trades = parsed_config['script_opt'].get('Log_trades')
    Log_file = parsed_config['script_opt'].get('Log_file')
    Debug_setting = parsed_config['script_opt'].get('Debug')
    American_usr = parsed_config['script_opt'].get('American_usr')

    # Trading variables
    Pair_with = parsed_config['trading_opt']['Pair_with']
    Qty = parsed_config['trading_opt']['Qty']
    Max_coins = parsed_config['trading_opt']['Max_coins']
    FIATS = parsed_config['trading_opt']['FIATS']
    Delta_T = parsed_config['trading_opt']['Detla_T']
    Recheck_interval = parsed_config['trading_opt']['Recheck_interval']
    Change_in_price = parsed_config['trading_opt']['Change_in_price']
    Stop_loss = parsed_config['trading_opt']['Stop_loss']
    Take_profit = parsed_config['trading_opt']['Take_profit']
    Custom_list = parsed_config['trading_opt']['Custom_list']
    Tickers_list = parsed_config['trading_opt']['Tickers_list']
    Use_trailing_stop_loss = parsed_config['trading_opt']['Use_trailing_stop_loss']
    Trailing_stop_loss = parsed_config['trading_opt']['Trailing_stop_loss']
    Trailing_take_profit = parsed_config['trading_opt']['Trailing_stop_loss']
    Trading_fee = parsed_config['trading_opt']['Trading_fee']
    Signaling_modules = parsed_config['trading_opt']['Signaling_modules']

    if Debug_setting or args.debug :
        DEBUG = True


    # Load credentials for correct environment
    Access_key, Secret_key = load_correct_creds(parsed_creds)

    # Avisa si está prendida la Debugneta
    if DEBUG:
        print(f'Loaded config below \n{json.dumps(parsed_config, indent= 4) }' )
        print(f'Your credentials were loaded from {creds_file}')


    # Authenticate with the client and ensure API key is good before moving on
    if American_usr :
        client = Client(Access_key, Secret_key, tld='us')
    else :
        client = Client(Access_key, Secret_key)

    # If the user provided incorrect API key this will
    # stop the script execution and display a helpful error.

    api_ready, msg = Test_api_key(client, BinanceAPIException)

    if api_ready is not True:
        exit(f'{txcolors.SELL_LOSS}{msg}{txcolors.DEFAULT}')

    # Use Custom_list symbols if it is set to True
    if Custom_list: tickers= [line.strip() for line in open(Tickers_list)]

    # Try and load all the coins bought by the bot if the file exists and is not empty
    coins_bought = {}

    Coins_bought_file_path = 'coins_bought.json'


    # Rolling window of prices; cyclical queue                      (copy-paste, no entiendo bien que hace)
    historical_prices = [None] * (Delta_T * Recheck_interval)
    hsp_head = -1

    # Prevent including in volatile_coins if it has already been featured there less than Delta_t minutes ago
    volatility_cooloff = {}

    # Separate files for testing and live trade
    if Test_mode :
        Coins_bought_file_path = 'Test_' + Coins_bought_file_path
    
    # if saved coins_bought json file exists and it's not empty, then load it 
    if os.path.isfile(Coins_bought_file_path) and os.stat(Coins_bought_file_path).st_size != 0:
        with open(Coins_bought_file_path) as file:
            coins_bought = json.load(file)

    print('Press Ctrl-Q to stop the script')

    if not Test_mode:
        if not args.notimeout:  # If no timeout, skip this (fast for dev tests)
            print('WARNING: You\'re about to use the mainnet and live funds. 30 seconds are acting as a buffer')
            time.sleep(30)

    signals = glob.glob('signals/*.exs')
    for filename in signals:
        for line in open(filename):
            try:
                os.remove(filename)
            except:
                if DEBUG: print(f'{txcolors.WARNING} Could not remove external signaling file {filename}{txcolors.DEFAULT}')

    if os.path.isfile('signals/paused.exc'):
        try:
            os.remove('signals/paused.exc')
        except:
            if DEBUG: print(f'{txcolors.WARNING} Could not remove external signaling file {filename}{txcolors.DEFAULT}')


    # Load signalling modules
    try:
        if len(Signaling_modules) > 0:
            for module in Signaling_modules:
                print(f'Starting {module}')
                mymodule[module] = importlib.import_module(module)
                t = threading.Thread(target= mymodule[module].do_work , args=())
                t.daemon = True
                t.start()
                time.sleep(2)
        else:
            print(f'No modules to load {Signaling_modules}')
    except Exception as e:
        print(e)

    get_price()
    while True:
        orders, last_price, volume = buy()
        update_portfolio(orders, last_price, volume)
        coins_sold = sell_coins()
        remove_from_portfolio(coins_sold)
