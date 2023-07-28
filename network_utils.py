import json
import requests
from web3 import Web3, constants
from config import *
import math
import os
from dotenv import load_dotenv
load_dotenv()

INFURA_KEY = os.environ.get('INFURA_KEY')
ARB_NODE_URL = f"https://arbitrum-mainnet.infura.io/v3/{INFURA_KEY}"
web3_ARB = Web3(Web3.HTTPProvider(ARB_NODE_URL))

def get_block_by_timestamp_arb(timestamp):
    res = requests.get(f'https://api.arbiscan.io/api?module=block&action=getblocknobytime&timestamp={timestamp}&closest=before&apikey={os.environ.get("ARBISCAN_API_KEY")}')
    response = json.loads(res.text)['result']
    return int(response)

def get_contract_arb(address):
    abi_url = f"https://api.arbiscan.io/api?module=contract&action=getabi&address={address}&format=raw"
    abi = requests.get(abi_url).text

    contract = web3_ARB.eth.contract(Web3.to_checksum_address(address), abi=abi)
    return contract

ALCHEMY_KEY = os.environ.get('ALCHEMY_KEY')
ETH_NODE_URL = "https://rpc.ankr.com/eth"
web3_ETH = Web3(Web3.HTTPProvider(ETH_NODE_URL))

def get_block_by_timestamp_eth(timestamp):
    res = requests.get(f'https://api.etherscan.io/api?module=block&action=getblocknobytime&timestamp={timestamp}&closest=before&apikey={os.environ.get("ETHERSCAN_API_KEY")}')
    response = json.loads(res.text)['result']
    return int(response)

def get_contract_eth(address):
    abi_url = f"https://api.etherscan.io/api?module=contract&action=getabi&address={address}&format=raw"
    abi = requests.get(abi_url).text

    contract = web3_ETH.eth.contract(Web3.to_checksum_address(address), abi=abi)
    return contract
