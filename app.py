from flask import Flask, request, jsonify
import os
import json
import math
from binance.client import Client
from binance.enums import *

app = Flask(__name__)

# API anahtarlarınız
binance_api_key    = os.getenv("BINANCE_API_KEY",    "YOUR_API_KEY")
binance_api_secret = os.getenv("BINANCE_API_SECRET", "YOUR_API_SECRET")

client = Client(binance_api_key, binance_api_secret, testnet=False)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_data().decode('utf-8')
        if not data:
            return jsonify({"error": "Boş veri alındı"}), 400

        webhook_data = json.loads(data)
        action   = webhook_data.get('action')
        symbol   = webhook_data.get('symbol')
        quantity = float(webhook_data.get('quantity', 0))
        label    = webhook_data.get('label')
        kademe   = webhook_data.get('kademe')
        reason   = webhook_data.get('reason')

        # Sembol validasyonu
        symbol_info = client.futures_exchange_info()
        valid_symbols = [s['symbol'] for s in symbol_info['symbols']]
        if symbol not in valid_symbols:
            return jsonify({"error": f"Geçersiz symbol: {symbol}"}), 400

        # Lot ve hassasiyet hesabı
        ticker = client.futures_symbol_ticker(symbol=symbol)
        price  = float(ticker['price'])

        step_size = 1.0
        for s in symbol_info['symbols']:
            if s['symbol'] == symbol:
                for f in s['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        step_size = float(f['stepSize'])
                        break
                break

        precision = int(round(-math.log10(step_size), 0)) if step_size else 8
        quantity = round(quantity, precision)

        # Emir gönderme
        if action == "buy":
            order = client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=quantity,
                positionSide='LONG'
            )
            print(f"Buy LONG: {order}")
            return jsonify({"status": "success"}), 200

        elif action == "sell":
            order = client.futures_create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantity,
                positionSide='SHORT'
            )
            print(f"Sell SHORT: {order}")
            return jsonify({"status": "success"}), 200

        elif action == "close_all":
            client.futures_cancel_all_open_orders(symbol=symbol)
            account_info = client.futures_account()
            for position in account_info['positions']:
                if position['symbol'] == symbol and float(position['positionAmt']) != 0:
                    side = SIDE_SELL if float(position['positionAmt']) > 0 else SIDE_BUY
                    pos_qty  = abs(float(position['positionAmt']))
                    pos_side = 'LONG' if float(position['positionAmt']) > 0 else 'SHORT'
                    client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type=ORDER_TYPE_MARKET,
                        quantity=pos_qty,
                        positionSide=pos_side
                    )
            print("Tüm pozisyonlar kapatıldı.")
            return jsonify({"status": "success"}), 200

        else:
            return jsonify({"error": f"Bilinmeyen action: {action}"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
