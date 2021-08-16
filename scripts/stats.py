import brownie
from brownie import *

AT = "0xDD387F2fe0D9B1E5768fc941e7E48AA8BfAf5e41"

def main():

  strat = Strategy.at(AT)
  vault = interface.VaultAPI(strat.vault())

  [performanceFee, activation, debtRatio, minDebtPerHarvest, maxDebtPerHarvest, lastReport, totalDebt, totalGain, totalLoss] = vault.strategies(strat)

  
  print("Reporting for wBTC Strat")
  print(strat.name())

  print("Address")
  print(AT)

  print("Total Assets Estimated")
  print(strat.estimatedTotalAssets())

  print("Of which rewards")
  print(strat.valueOfRewards())

  print("Total deposited")
  print(strat.deposited())

  print("Total borrowed")
  print(strat.borrowed())

  print("Total Underlying tokens, i.e. totalDebt")
  print(totalDebt)
  

  leverage_ratio = strat.deposited() / totalDebt

  print("Leverage Ratio")
  print(leverage_ratio)

  print("LTV")
  print(strat.borrowed() / strat.deposited())

  print("Can lever up with another")
  print(strat.canBorrow())


  """
    TODO
    Expected Profit: 26,620.334323
    Time to liquidation: 101.72 weeks
  """
  lending_pool = interface.ILendingPool(strat.LENDING_POOL())

  [configuration, liquidityIndex, variableBorrowIndex, currentLiquidityRate, currentVariableBorrowRate, currentStableBorrowRate, lastUpdateTimestamp, aTokenAddress, stableDebtTokenAddress, variableDebtTokenAddress, interestRateStrategyAddress, id] = lending_pool.getReserveData(strat.want())

  print("currentVariableBorrowRate")
  print(currentVariableBorrowRate)
  
  print("currentLiquidityRate")
  print(currentLiquidityRate)

  liquidation_amount = strat.deposited() * .75

  debt_to_liquidation = liquidation_amount - strat.borrowed() ## The debt that will liquidate us

  print("debt_to_liquidation")
  print(debt_to_liquidation)

  debt_per_year = strat.borrowed() * currentVariableBorrowRate / (10 ** 27) ## Not compounding so technically underestimate
  years_to_liquidation = debt_to_liquidation / debt_per_year ## The years to liquidation
  days_to_liquidation = years_to_liquidation * 365

  print("days to liquidation")
  print(days_to_liquidation)

  print("Current Rewards")
  print(strat.valueOfRewards())