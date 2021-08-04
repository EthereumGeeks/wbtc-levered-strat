import brownie
from brownie import *
import pytest


@pytest.fixture
def live_vault(pm):
    Vault = pm(config["dependencies"][0]).Vault
    vault = Vault.at("0xA696a63cc78DfFa1a63E9E50587C197387FF6C7E")
    yield vault

@pytest.fixture
def live_strat(live_vault, gov):
  strat = Strategy.at("0xDD387F2fe0D9B1E5768fc941e7E48AA8BfAf5e41")
  live_vault.addStrategy(strat, 1000, 0, 2 ** 256 - 1, 1_000, {"from": gov}) ## 10% debt ratio
  yield strat


@pytest.fixture
def amount(accounts, token, user, gov, management):
    amount = 1_000 * 10 ** token.decimals()
    # In order to get some funds for the token you are about to use,
    # it impersonate an exchange address to use it's funds.
    reserve = accounts.at("0x9ff58f4ffb29fa2266ab25e75e2a8b3503311656", force=True)
    token.transfer(user, amount, {"from": reserve})

    ## Also send a little bit to gov for test_manual_operation
    token.transfer(gov, 100 * 10 ** token.decimals(), {"from": reserve})
    token.transfer(management, 100 * 10 ** token.decimals(), {"from": reserve})
    yield amount

@pytest.fixture
def live_keeper(live_strat):
  return accounts.at(live_strat.keeper(), force=True)

def test_deposit_load(user, token, amount, live_vault, live_strat, live_keeper):
  token.approve(live_vault, amount, {"from": user})
  live_vault.deposit(amount, {"from": user})

  assert live_strat.estimatedTotalAssets() == 0

  live_strat.harvest({"from": live_keeper})
  assert live_strat.estimatedTotalAssets() > 0
  

def test_profitable_harvest(user, token, amount, live_vault, live_strat, live_keeper, gov):
  ## Load funds
  token.approve(live_vault, amount, {"from": user})
  live_vault.deposit(amount, {"from": user})

  live_strat.harvest({"from": live_keeper})
  prev_estimate = live_strat.estimatedTotalAssets()

  print("live_strat.valueOfRewards() 1")
  print(live_strat.valueOfRewards())

  ## Funds are loaded, we have some leverage, increase it
  live_strat.manualLeverUp({"from": gov})

  ## Wait a day
  chain.sleep(3600)
  chain.mine()

  print("live_strat.valueOfRewards() 2")
  print(live_strat.valueOfRewards())

  ## Harvest Profits
  live_strat.harvest({"from": live_keeper})

  ## Event had profit > 0
  harvest_event = history[-1].events["Harvested"]
  profit_result = harvest_event["profit"]
  assert profit_result > 0

  print("We profited in a day")
  print(profit_result)


def test_repay_partial_revoke(user, token, amount, live_vault, live_strat, live_keeper, gov):
  initial_balance = token.balanceOf(live_vault)
  ## Load funds
  token.approve(live_vault, amount, {"from": user})
  live_vault.deposit(amount, {"from": user})

  deposited = initial_balance + amount

  live_strat.harvest({"from": live_keeper})

  ## Funds are loaded, we have some leverage, increase it
  live_strat.manualLeverUp({"from": gov})

  ## Take 1 day of interest
  chain.sleep(3600) 

  ## We reduce debt ratio by half, shows the fix in reporting profits
  live_vault.updateStrategyDebtRatio(live_strat.address, 500, {"from": gov})
  chain.sleep(1)
  live_strat.harvest({"from": live_keeper})

  ## Event had profit > 0
  harvest_event = history[-1].events["Harvested"]
  profit_result = harvest_event["profit"]
  repay_result = harvest_event["debtPayment"]
  assert profit_result > 0
  assert repay_result > 0

  ## We made a profit, got amount / 2 back
  end_difference = token.balanceOf(live_vault.address) - initial_balance
  assert end_difference > amount / 2 ## Needs to be half (repaid) + profit

def test_repay_revoke(user, token, amount, live_vault, live_strat, live_keeper, gov):
  ## Load funds
  token.approve(live_vault, amount, {"from": user})
  live_vault.deposit(amount, {"from": user})

  live_strat.harvest({"from": live_keeper})

  ## Funds are loaded, we have some leverage, increase it
  live_strat.manualLeverUp({"from": gov})

  ## Take 1 day of interest
  chain.sleep(3600) 
  chain.mine()

  ## We revoke the strat
  # In order to pass this tests, you will need to implement prepareReturn.
  live_vault.revokeStrategy(live_strat.address, {"from": gov})
  chain.sleep(1)
  chain.mine()
  live_strat.harvest({"from": live_keeper})

  ## We made a profit
  assert token.balanceOf(live_vault.address) > amount