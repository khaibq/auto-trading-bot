import os
import asyncio
import json
import random
import logging

from dydx_v4_client import MAX_CLIENT_ID, OrderFlags
from v4_proto.dydxprotocol.clob.order_pb2 import Order
from dydx_v4_client.indexer.rest.constants import OrderType
from dydx_v4_client.indexer.rest.indexer_client import IndexerClient
from dydx_v4_client.node.client import NodeClient
from dydx_v4_client.node.market import Market
from dydx_v4_client.wallet import Wallet
from dydx_v4_client.network import TESTNET

from utils import(
    subaccount_info,
    get_secret,
    get_ssm_parameter
)
from send_message import send_message

logger = logging.getLogger(__name__)

# Set minimum fund able to trade
FREE_COLLATERAL_MIN = 10.0
# Set price range for ETH-USD pair
PRICE_RANGE = [0, 4000]
# Get SECRET_NAME, MESSAGE_NAME & REGION_NAME from Lambda main function
secret_name = os.environ['SECRET_NAME']
message_name = os.environ['MESSAGE_NAME']
region_name = os.environ['REGION_NAME']
# Retrieve secret from Secret Manager
dydx_secret = asyncio.run(get_secret(secret_name, region_name))
trade_address = dydx_secret["address"]
seed_phrase = dydx_secret["mnemonic"]
# Retrieve id and token for message
message_config = asyncio.run(get_ssm_parameter(message_name, region_name))
message_webhook_id = message_config["message_webhook_id"]
message_webhook_token = message_config["message_webhook_token"]

async def place_market_order(market_pair: str, side: str, order_size: float):
    node = await NodeClient.connect(TESTNET.node)
    indexer = IndexerClient(TESTNET.rest_indexer)
    market = Market(
        (await indexer.markets.get_perpetual_markets(market_pair))["markets"][market_pair]
    )
    wallet = await Wallet.from_mnemonic(node, seed_phrase, trade_address)
    order_id = market.order_id(
        trade_address, 0, random.randint(0, MAX_CLIENT_ID), OrderFlags.SHORT_TERM
    )
    current_block = await node.latest_block_height()
    order_side = Order.Side.SIDE_SELL if side == "sell" else Order.Side.SIDE_BUY
    order_price = PRICE_RANGE[1] if order_side == Order.Side.SIDE_BUY else PRICE_RANGE[0]
    new_order = market.order(
        order_id=order_id,
        order_type=OrderType.MARKET,
        side=order_side,
        size=order_size,
        price=order_price,  # Set to 0 for market orders
        time_in_force=Order.TimeInForce.TIME_IN_FORCE_UNSPECIFIED,
        reduce_only=False,
        good_til_block=current_block + 10,
    )
    transaction = await node.place_order(
        wallet=wallet,
        order=new_order,
    )
    print(transaction)
    wallet.sequence += 1

def handler(event, context):
    order_strategy = ""
    market_pair = ""
    signal_time = ""
    signal_price = ""
    order_side = ""
    order_size = ""
    try:
        if (event['queryStringParameters']) and (event['queryStringParameters']['order_side']) and (
                event['queryStringParameters']['order_side'] is not None):
            order_strategy = event['queryStringParameters']['order_strategy']
            signal_time = event['queryStringParameters']['signal_time']
            signal_price = event['queryStringParameters']['signal_price']
            order_side = event['queryStringParameters']['order_side']
            order_size = float(event['queryStringParameters']['order_size'])
            market_pair = event['queryStringParameters']['market_pair']
            market_pair = market_pair.replace("USD.P", "")
            market_pair = market_pair + "-USD"
    except KeyError:
        print('No input parameter data')

    if (event['body']) and (event['body'] is not None):
        body = json.loads(event['body'])
        try:
            if (body['order_side']) and (body['order_side'] is not None):
                order_strategy = body['order_strategy']
                signal_time = body['signal_time']
                signal_price = body['signal_price']
                order_side = body['order_side']
                order_size = float(body['order_size'])
                market_pair = body['market_pair']
                market_pair = market_pair.replace("USD.P", "")
                market_pair = market_pair + "-USD"
        except KeyError:
            print('No body input data')
    if (order_side == "sell") or (order_side == "buy"):
        subaccount = asyncio.run(subaccount_info(trade_address, 0))
        free_collateral = float(subaccount["freeCollateral"])
        if free_collateral > FREE_COLLATERAL_MIN:
            asyncio.run(place_market_order(market_pair, order_side, order_size))
        else:
            logger.info(f"Free Collateral: {free_collateral} is lower than FREE_COLLATERAL_MIN: {FREE_COLLATERAL_MIN}")
            print(f"Free Collateral: {free_collateral} is lower than FREE_COLLATERAL_MIN: {FREE_COLLATERAL_MIN}")
    res_data = {
        "order_strategy": order_strategy,
        "signal_time": signal_time,
        "signal_price": signal_price,
        "market_pair": market_pair,
        "order_side": order_side,
        "order_size": str(order_size)
    }
    message = {
        "username": "TradingView Webhook",
        "content": "Trading signal receiving from webhook",
        "embeds": [
            {
                "fields": [
                    {
                        "name": "Strategy",
                        "value": res_data["order_strategy"],
                        "inline": True
                    },
                    {
                        "name": "Time",
                        "value": res_data["signal_time"],
                        "inline": True
                    },
                    {
                        "name": "Market",
                        "value": res_data["market_pair"]
                    },
                    {
                        "name": "Price",
                        "value": res_data["signal_price"]
                    },
                    {
                        "name": "Order Side",
                        "value": res_data["order_side"].upper()
                    },
                    {
                        "name": "Order Size",
                        "value": res_data["order_size"]
                    }
                ]
            }
        ]
    }
    # Send the notification to message service
    send_message(message_webhook_id, message_webhook_token, message)
    res = {
        "statusCode": 200,
        "headers": {
            "Content-Type": "*/*"
        },
        "body": json.dumps(res_data)
    }
    return res