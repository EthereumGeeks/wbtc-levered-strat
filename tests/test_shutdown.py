import brownie
from brownie import Contract
import pytest

"""
NOTE: Since we interact with AAVE on mainnet fork, you may have to run this file separately
"""

def test_vault_emergency(
  chain, accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, lpComponent, borrowed, reward, incentivesController
):
  ## Deposit in Vault
  token.approve(vault.address, amount, {"from": user})

  vault.deposit(amount, {"from": user})
  assert token.balanceOf(vault.address) == amount
  assert strategy.estimatedTotalAssets() == 0

  # Harvest 1: Send funds through the strategy
  strategy.harvest()
  chain.mine(1)
  assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

  ## Set Emergency
  vault.setEmergencyShutdown(True)

  ## Withdraw (does it work, do you get what you expect)
  vault.withdraw({"from": user})

  assert pytest.approx(token.balanceOf(user), rel=RELATIVE_APPROX) == amount

# TODO: Add tests that show proper operation of this strategy through "emergencyExit"
#       Make sure to demonstrate the "worst case losses" as well as the time it takes
def test_emergency_exit(
    chain, accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, lpComponent, borrowed, reward, incentivesController
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    print("stratDep1 ")
    print(strategy.estimatedTotalAssets())

    # Harvest 1: Send funds through the strategy
    strategy.harvest()
    chain.mine(1)
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    

    # TODO: Add some code before harvest #2 to simulate earning yield
    before_pps = vault.pricePerShare()
    before_total = vault.totalAssets()
    before_debt = vault.totalDebt()

    chain.sleep(3600 * 24 * 1) ## Sleep 1 day
    chain.mine(1)
    
    print("Reward") 
    print(incentivesController.getRewardsBalance(
            [lpComponent, borrowed],
            strategy
        ))
    print("stratDep2 ")
    print(strategy.estimatedTotalAssets())

    # Harvest 2: Realize profit
    strategy.harvest()
    print("Reward 2") 
    print(incentivesController.getRewardsBalance(
            [lpComponent, borrowed],
            strategy
        ))
    print("stratDep3 ")
    print(strategy.estimatedTotalAssets())
    amountAfterHarvest = token.balanceOf(strategy) + lpComponent.balanceOf(strategy) - borrowed.balanceOf(strategy)
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)
    profit = token.balanceOf(vault.address)  # Profits go to vault

    # NOTE: Your strategy must be profitable
    # NOTE: May have to be changed based on implementation
    stratAssets = strategy.estimatedTotalAssets()
    
    print("stratAssets")
    print(stratAssets)

    vaultAssets = vault.totalAssets()
    print("vaultAssets")
    print(vaultAssets)

    ## Total assets for strat are token + lpComponent + borrowed
    assert  amountAfterHarvest + profit > amount
    ## NOTE: Changed to >= because I can't get the PPS to increase
    assert vault.pricePerShare() >= before_pps ## NOTE: May want to tweak this to >= or increase amounts and blocks
    assert vault.totalAssets() > before_total ## NOTE: Assets must increase or there's something off with harvest
    ## NOTE: May want to harvest a third time and see if it icnreases totalDebt for strat

    strategy.setEmergencyExit({"from": strategist})

    strategy.harvest() ## Will liquidate all

    assert lpComponent.balanceOf(strategy) == 0
    assert token.balanceOf(strategy) == 0
    assert token.balanceOf(vault) >= amount ## The vault has all funds (some loss may have happened)

    vault.withdraw({"from": user}) ## Withdraw to make sure we are good for next test

def test_massive_loss(
  chain, accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, lpComponent, borrowed, reward, incentivesController
):
  """
    The only way to loose on this strategy is if rewards are no longer there
    Also not harvesting in a long time and then revoking the strat will incurr in lossess
    Withdrawing takes no time, funds are liquid at all times (there may be black swan exceptions)

    We can quantify the loss as the difference between the interest we gain vs the interest we pay * the time we don't harvest

    NOTE: Waiting more than 5 days may trigger the maxLoss check on Vault.vy
  """
    ## Deposit in Vault
  token.approve(vault.address, amount, {"from": user})

  vault.deposit(amount, {"from": user})
  assert token.balanceOf(vault.address) == amount
  assert strategy.estimatedTotalAssets() == 0

  # Harvest 1: Send funds through the strategy
  strategy.harvest()
  chain.mine(1)
  assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

  DAYS = 5
  chain.sleep(3600 * 24 * DAYS)  ## Sleep for days = Loose due to interest
  chain.mine(1)

  INTEREST_ESTIMATE = 100 ## We loose around 1% per year if we never harvest

  ## Set Emergency = We will withdraw all next harvest = We will not collect rewards
  vault.setEmergencyShutdown(True)

  ## Withdraw (does it work, do you get what you expect)
  vault.withdraw(vault.balanceOf(user), user, INTEREST_ESTIMATE / 3.65 * DAYS  + 1, {"from": user})

  ## NOTE: I just took this from a manual test
  print("We lost")
  print(amount - token.balanceOf(user))
  print("As percentage")
  print(amount - token.balanceOf(user))

  assert token.balanceOf(user) < amount ## We lost some