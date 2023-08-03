import math
import pandas as pd
from statistics import mean
from config import *
from network_utils import *
import datetime
from datetime import date

def to_normal_float(decimal_bigNumber):
    # return float(web3_ARB.from_wei(decimal_bigNumber, "ether"))
    return float(decimal_bigNumber/1e18)

def get_market_precompute(
        market_state,
        SY_index,
        timestamp
):
    time_to_expiry = market_state['expiry'] - timestamp
    market_precompute = {}
    market_precompute["rate_scalar"] = to_normal_float(market_state["scalarRoot"]*IMPLIED_RATE_TIME/time_to_expiry)
    market_precompute["total_asset"] = to_normal_float(market_state["totalSy"])*SY_index

    market_precompute["rate_anchor"] = get_rate_anchor(
        to_normal_float(market_state["totalPt"]), 
        to_normal_float(market_state["lastLnImpliedRate"]),
        market_precompute["total_asset"],
        market_precompute["rate_scalar"],
        time_to_expiry
    )
    
    return market_precompute

def get_rate_anchor(total_PT, last_ln_implied_rate, total_asset, rate_scalar, time_to_expiry):
    ln_rate = last_ln_implied_rate*time_to_expiry/IMPLIED_RATE_TIME
    new_exchange_rate = math.exp(ln_rate)
    proportion = total_PT/(total_PT + total_asset)
    ln_proportion = math.log(proportion/(1-proportion))
    rate_anchor = new_exchange_rate - ln_proportion/rate_scalar

    return rate_anchor

def get_exchange_rate(total_PT, total_asset, rate_scalar, rate_anchor):
    return math.log(total_PT/total_asset)/rate_scalar + rate_anchor

def average_boost_factor(market_contract, block_number):
    return market_contract.functions.totalActiveSupply().call(block_identifier=block_number)/market_contract.functions.totalSupply().call(block_identifier=block_number)*2.5

def get_info(SY_contract, YT_contract, market_contract, timestamp, chain = 'arb'):
    date = datetime.datetime.fromtimestamp(timestamp).strftime('%d-%m-%y')
    if chain == 'arb':
        block_number = int(get_block_by_timestamp_arb(int(timestamp)))
        PENDLE_reward_index = to_normal_float(market_contract.functions.rewardState(PENDLE_ADDRESS_ARB).call(block_identifier=block_number)[0])
    elif chain == 'eth':
        block_number = int(get_block_by_timestamp_eth(int(timestamp)))
        PENDLE_reward_index = to_normal_float(market_contract.functions.rewardState(PENDLE_ADDRESS_ETH).call(block_identifier=block_number)[0])
    else:
        raise Exception("Invalid chain!")

    try:
        X_reward_index = to_normal_float(
            SY_contract.functions.rewardIndexesCurrent().call(block_identifier=block_number)[0]
        )
    except:
        X_reward_index = 0
        print("This SY has no reward.")

    SY_index = to_normal_float(
        YT_contract.functions.pyIndexStored().call(block_identifier=block_number)
    )

    market_state_values = market_contract.functions.readState(constants.ADDRESS_ZERO).call(block_identifier=block_number)

    market_state_keys = [
        "totalPt",
        "totalSy",
        "totalLp",
        "treasury",
        "scalarRoot",
        "expiry",
        "lnFeeRateRoot",
        "reserveFeePercent",
        "lastLnImpliedRate"
    ]
    #     struct MarketState {
    #     int256 totalPt;
    #     int256 totalSy;
    #     int256 totalLp;
    #     address treasury;
    #     /// immutable variables ///
    #     int256 scalarRoot;
    #     uint256 expiry;
    #     /// fee data ///
    #     uint256 lnFeeRateRoot;
    #     uint256 reserveFeePercent; // base 100
    #     /// last trade data ///
    #     uint256 lastLnImpliedRate;
    # }
    market_state = {market_state_keys[i]: market_state_values[i] for i in range(len(market_state_keys))}
    market_precompute = get_market_precompute(market_state, SY_index, timestamp)

    # time_to_expiry = market_state["expiry"] - timestamp

    data_onchain = {}
    data_onchain["date"] = date
    data_onchain["asset"] = market_precompute["total_asset"]
    data_onchain["PT"] = to_normal_float(market_state["totalPt"])
    data_onchain["LP"] = to_normal_float(market_state["totalLp"])
    data_onchain["SY"] = to_normal_float(market_state["totalSy"])
    data_onchain["exchange_rate"] = get_exchange_rate(data_onchain["PT"], data_onchain["asset"], market_precompute["rate_scalar"], market_precompute["rate_anchor"])
    data_onchain["X_reward_index"] = X_reward_index
    data_onchain["PENDLE_reward_index"] = PENDLE_reward_index
    data_onchain["average_boost_factor"] = average_boost_factor(market_contract, block_number)
    data_onchain["SY_index"] = SY_index
    
    return data_onchain

def IL(data_df, case, PENDLE_incentive, asset_price, X_price, PENDLE_price=PENDLE):
    n = len(data_df)
    IL = [[pd.NA for _ in range(n)] for _ in range(n)]

    # Implementing https://www.notion.so/pendle/IL-2-047e0ede69e94de28caa2c6bde13dc60?pvs=4
    # Compare from timestamp i to timestamp j
    for i in range(n):  
        for j in range(i, n):             
            BOOST_FACTOR = data_df.loc[j, "average_boost_factor"]
            PENDLE_reward_value = (data_df.loc[j, "PENDLE_reward_index"] - data_df.loc[i, "PENDLE_reward_index"])*BOOST_FACTOR*PENDLE_price/asset_price
            X_reward = (data_df.loc[j, "X_reward_index"] - data_df.loc[i, "X_reward_index"])*X_price/asset_price
            # asset per SY
                
            # At timestamp j
            PT_in_pool = data_df.loc[j, "PT"]/data_df.loc[j, "LP"]  # x_j
            PT_in_pool_value = PT_in_pool/data_df.loc[j, "exchange_rate"]  # value unit is asset
            mean_SY_in_pool = mean(data_df.loc[i:j, "SY"]/data_df.loc[i:j, "LP"])  # y_{i,j}
            SY_in_pool_value = data_df.loc[j, "asset"]/data_df.loc[j, "LP"]  # y_j*SYindex_j
            X_reward_in_pool_value = mean_SY_in_pool*X_reward*BOOST_FACTOR  # Assume reward received based on the final amount of SY only

            in_pool_value = PT_in_pool_value + SY_in_pool_value + X_reward_in_pool_value + (PENDLE_reward_value if PENDLE_incentive else 0)
            
            if case == 'A':  # User holds PT + SY
                PT_out_pool_value = data_df.loc[i, "PT"]/(data_df.loc[j, "exchange_rate"]*data_df.loc[i, "LP"])
                SY_out_pool = data_df.loc[i, "SY"]/data_df.loc[i, "LP"]  # y_i
                SY_out_pool_value = SY_out_pool*data_df.loc[j, "SY_index"]
                X_reward_out_pool_value = SY_out_pool*X_reward
                out_pool_value =  PT_out_pool_value + SY_out_pool_value + X_reward_out_pool_value
            
            elif case == 'B': # User holds SY only
                SY_out_pool = (data_df.loc[i, "PT"]/(data_df.loc[i, "exchange_rate"]*data_df.loc[i, "SY_index"]) + data_df.loc[i, "SY"])/data_df.loc[i, "LP"]
                X_reward_out_pool_value = SY_out_pool*X_reward
                out_pool_value =  SY_out_pool*data_df.loc[j, "SY_index"] + X_reward_out_pool_value
            
            elif case =='C': 
                YT_holding = data_df.loc[i, "PT"]/data_df.loc[i, "LP"]  # x_i
                YT_value = YT_holding*(1-1/data_df.loc[j, "exchange_rate"])
                YT_reward_X = YT_holding/data_df.loc[j, "SY_index"] 
                YT_reward_SY = YT_holding*(1/data_df.loc[i, "SY_index"]-1/data_df.loc[j, "SY_index"])
                in_pool_value = in_pool_value + YT_value + YT_reward_X*X_reward + YT_reward_SY*data_df.loc[j, "SY_index"]

                SY_out_pool = (data_df.loc[i, "PT"]/data_df.loc[i, "SY_index"] + data_df.loc[i, "SY"])/data_df.loc[i, "LP"]
                out_pool_value =  SY_out_pool*(data_df.loc[j, "SY_index"] + X_reward)

            IL[i][j] = in_pool_value/out_pool_value

    return IL

def write_array_to_csv(array, file_name, timestamp_start):
    date_column = [date.fromtimestamp(timestamp_start) + datetime.timedelta(days=DAY_DELTA*i) for i in range(len(array))]
    for i in range(len(array)):
        array[i].insert(0, date_column[i])

    date_row = [''] + date_column
    array.insert(0, date_row)

    df = pd.DataFrame(array)
    df.to_csv(file_name, header=False, index=False)